#!/usr/bin/env python3
"""Collect a single retailer independently; write only this retailer's artifacts."""
import argparse, asyncio, datetime as dt, json
from pathlib import Path
from playwright.async_api import async_playwright
from collect_prices import SOURCES, scrape
from silpo_app_probe import probe_catalog
from silpo_app_catalog import collect_public_catalog, ROOT as SILPO_API
from silpo_catalog_quality import audit as audit_silpo
from atb_public_probe import probe as probe_atb
from atb_economy import collect_public_economy, SOURCE as ATB_ECONOMY
ROOT=Path(__file__).resolve().parents[1]
async def main(store):
 now=dt.datetime.now(dt.timezone.utc).isoformat()
 url=SOURCES[store]
 items=[];error=""
 silpo_coverage={}
 silpo_quality={}
 atb_html_error=""
 atb_html_stats={}
 fora_stats={}
 zakaz_stats={}
 novus_quality={}
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=["--no-sandbox"])
  page=await browser.new_page(locale="uk-UA",viewport={"width":1350,"height":900})
  try:
   if store=="silpo":
    url=SILPO_API
    items=await asyncio.to_thread(collect_public_catalog,stats=silpo_coverage)
    if items:
     silpo_quality=audit_silpo(items)
     if silpo_quality["errors"]:
      error="Silpo QA failed: "+"; ".join(silpo_quality["errors"][:3])
      items=[] # Do not publish an unverified batch.
    else:
     error="No items with verified displayed old/new prices in bounded Silpo listing"
   elif store=="atb":
    # Prefer freely served HTML. A normal browser is a fallback, not a
    # Cloudflare bypass. Do not use accounts or private session tokens.
    url=ATB_ECONOMY
    try:
     # BeautifulSoup is an ATB-only dependency. Keep the import here so a
     # missing optional parser cannot prevent other retailer jobs starting.
     from atb_economy_html import collect_html as collect_atb_html
     items=await asyncio.to_thread(collect_atb_html,stats=atb_html_stats,expand_promo=True)
     print("ATB public Economy HTML verified",len(items),flush=True)
    except Exception as html_exc:
     atb_html_error=str(html_exc)[:200]
     print("ATB public HTML unavailable:",atb_html_error[:160],flush=True)
     items=await collect_public_economy(page,max_pages=2)
    if not items:error="ATB Economy page yielded no verified current product cards"
   else:
    items=await scrape(page,store,url,stats=fora_stats if store=="fora" else zakaz_stats if store in ("novus","metro") else None)
   if store=="fora" and items and fora_stats.get("hasUnresolvedFailures"):
    if fora_stats.get("publishablePartial"):
     print("Fora verified partial listing accepted:",len(items),flush=True)
    else:
     error="Fora incomplete catalog rejected: "+fora_stats.get("stopReason","unresolved page windows")
     items=[] # No trustworthy contiguous prefix: keep cached valid results.
   if store=="metro" and items and not zakaz_stats.get("listingPagesComplete"):
    error="METRO partial catalog rejected: "+zakaz_stats.get("stopReason","pagination incomplete")
    items=[] # Preserve last verified snapshot through merge; do not publish as freshly checked.
   if store=="novus" and items:
    from audit_catalog import audit as audit_novus
    novus_quality=audit_novus(items,"novus")
    if not novus_quality["ok"]:
     error="NOVUS quality gate rejected catalog: "+ "; ".join(novus_quality["errors"][:3])
     items=[] # Keep last previously verified catalog; do not publish bad data.
   if store=="atb" and not items:
    title=(await page.title()).lower()
    body=(await page.locator("body").inner_text(timeout=3000)).lower()
    if "перевірка безпеки" in body or "cloudflare" in body or "трохи зачекайте" in title:
     error=store.upper()+" Cloudflare challenge: public catalog not accessible to automated runner"
  except Exception as exc:error=str(exc)[:500]
  finally:
   diagnostics={}
   if not items:
    try:
     diagnostics=await page.evaluate("""() => ({finalUrl:location.href,title:document.title,bodyLength:(document.body?.innerText||"").length,priceMentions:(document.body?.innerText||"").match(/(?:грн|₴)/g)?.length||0,productNodes:document.querySelectorAll("[class*=product],[class*=Product],article").length,sample:(document.body?.innerText||"").slice(0,350)})""")
    except Exception as exc:diagnostics={"error":str(exc)[:180]}
   if store=="fora":diagnostics["pagination"]=fora_stats
   if store in ("novus","metro"):diagnostics["pagination"]=zakaz_stats
   if store=="novus" and novus_quality:diagnostics["catalogQuality"]=novus_quality
   if store=="atb" and items:diagnostics["publicHtmlStats"]=atb_html_stats
   if store=="atb" and not items:
    diagnostics["publicHtmlError"]=atb_html_error
    diagnostics["publicHtmlStats"]=atb_html_stats
    try:
     diagnostics["atbEconomyCardProbe"]=await page.evaluate("""() => ({
       productAnchors:document.querySelectorAll('a[href*="/product/"]').length,
       discountMentions:(document.body?.innerText||'').match(/[-−]\\s*\\d{1,2}%/g)?.length||0,
       sampleProducts:[...document.querySelectorAll('a[href*="/product/"]')].slice(0,3).map(a=>({
         href:a.getAttribute('href'),name:(a.innerText||a.querySelector('img[alt]')?.alt||'').trim().slice(0,100),
         context:(a.closest('article,[class*=product],[class*=card]')?.innerText||a.parentElement?.parentElement?.innerText||'').slice(0,270)
       }))
     })""")
    except Exception as exc:
     diagnostics["atbEconomyCardProbe"]={"error":type(exc).__name__}
   if store=="atb" and not items:
    # Diagnose two public pages without login, proxies or bypasses.
    try:
     diagnostics["publicCatalogProbe"]=await asyncio.to_thread(probe_atb)
    except Exception as exc:
     diagnostics["publicCatalogProbe"]={"error":type(exc).__name__}
   if store=="silpo":diagnostics["catalogCoverage"]=silpo_coverage
   if store=="silpo" and silpo_quality:diagnostics["catalogQuality"]=silpo_quality
   if store=="silpo" and not items:
    # Public app interfaces: two bounded requests. Never attempt auth bypass.
    try:
     diagnostics["appCatalogProbe"]=await asyncio.to_thread(probe_catalog)
    except Exception as exc:
     diagnostics["appCatalogProbe"]={"error":type(exc).__name__}
   if store=="fora" and not items:
    try:
     samples=await page.evaluate("""() => {
       const anchors=[...document.querySelectorAll('a[href]')];
       const parts=['/product/','/products/','/tovar/','/goods/','/p/'];
       const product=anchors.filter(a=>parts.some(p=>(a.getAttribute('href')||'').includes(p)));
       const promo=product.filter(a=>{let n=a;for(let i=0;i<5&&n;i++,n=n.parentElement){if((n.innerText||'').includes('%'))return true}return false});
       return {totalLinks:anchors.length,productLinks:product.length,productLinksWithPercent:promo.length,samples:(promo.length?promo:product).slice(0,10).map(a=>({href:a.getAttribute('href'),text:(a.closest('article')?.innerText||a.parentElement?.parentElement?.innerText||'').slice(0,380)}))};
     }""")
     diagnostics["cardSamples"]=samples
    except Exception as exc:diagnostics["sampleError"]=str(exc)[:180]
   if store=="novus_official" and not items:
    try:
     diagnostics["officialPriceProbe"]=await page.evaluate(r"""() => {
       const cards=[...document.querySelectorAll('.product-item-info')];
       const decimal=/(?<![\d.,])\d{1,5}[.,]\d{2}(?![\d.,])/g;
       return {cardCount:cards.length,samples:cards.slice(0,6).map(c=>{
         const t=(c.innerText||'').replace(/\s+/g,' ').trim();
         const text=t.replace(/з\s*\d{1,2}\s*[.]\s*\d{1,2}\s*по\s*\d{1,2}\s*[.]\s*\d{1,2}/gi,' ');
         return {raw:t.slice(0,190),prices:[...text.matchAll(decimal)].map(m=>m[0]),officialLinks:[...c.querySelectorAll('a[href]')].map(a=>a.href).filter(h=>h.startsWith('https://novus.ua/')&&h.includes('.html')).slice(0,4)};
       })};
     }""")
    except Exception as exc:diagnostics["officialPriceProbeError"]=str(exc)[:160]
    try:
     diagnostics["officialCardSamples"]=await page.evaluate("""() => {
       const links=[...document.querySelectorAll('a[href]')].filter(a=>{
         try{const u=new URL(a.href);return u.hostname==='novus.ua' && u.pathname.endsWith('.html') && !u.pathname.startsWith('/sales/')}
         catch{return false}
       });
       return {candidateLinks:links.length,samples:links.slice(0,8).map(a=>{
         const node=a.closest('.product-item,li.product,article,[class*="product-item-info"]')||a.parentElement?.parentElement?.parentElement;
         return {url:a.href,name:(a.textContent||a.querySelector('img[alt]')?.alt||'').trim().slice(0,110),
           classes:node?.className?.toString().slice(0,130)||'',
           text:(node?.innerText||'').slice(0,480)};
       })};
     }""")
    except Exception as exc:
     diagnostics["officialCardError"]=str(exc)[:200]
   await page.close()
   await browser.close()
 path=ROOT/"data"/"stores"
 path.mkdir(parents=True,exist_ok=True)
 state={"store":store,"checkedAt":now,"source":url,"count":len(items),
        "status":("partial_verified" if store=="fora" and items and fora_stats.get("publishablePartial")
                  else "ok" if items else "error" if error else "no_data"),
        "error":error,
        "warning":("Verified prices from accessible listing pages; full coverage not confirmed"
                   if store=="fora" and items and fora_stats.get("publishablePartial") else ""),
        "diagnostics":diagnostics if (not items or store in ("silpo","atb","fora","metro","novus")) else {}}
 if items and not error:
  (path/(store+".json")).write_text(json.dumps(items,ensure_ascii=False,indent=2)+"\n")
 (path/(store+"-status.json")).write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(state,ensure_ascii=False))
if __name__=="__main__":
 a=argparse.ArgumentParser();a.add_argument("--store",required=True,choices=list(SOURCES))
 asyncio.run(main(a.parse_args().store))
