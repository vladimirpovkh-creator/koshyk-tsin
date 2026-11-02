#!/usr/bin/env python3
"""Collect a single retailer independently; write only this retailer's artifacts."""
import argparse, asyncio, datetime as dt, json
from pathlib import Path
from playwright.async_api import async_playwright
from collect_prices import SOURCES, scrape
from silpo_partner_feed import collect_partner_feed
from silpo_public_announcements import collect_public_announcements
ROOT=Path(__file__).resolve().parents[1]
async def main(store):
 now=dt.datetime.now(dt.timezone.utc).isoformat()
 url=SOURCES[store]
 items=[];error=""
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=["--no-sandbox"])
  page=await browser.new_page(locale="uk-UA",viewport={"width":1350,"height":900})
  try:
   if store=="silpo" and __import__("os").environ.get("SILPO_FEED_URL"):
    items=await asyncio.to_thread(collect_partner_feed)
    url="Licensed Silpo partner feed"
    if not items:
     error="Silpo partner feed returned no current, verified discount offers"
   elif store=="silpo":
    # Free official announcements; no auth, no payment and no Cloudflare bypass.
    # May legitimately yield zero offers if no current priced promo was posted.
    try:
     items=await collect_public_announcements(page)
     print("Silpo public official announcements:",len(items),flush=True)
     if items:url="https://t.me/s/silposilpo"
    except Exception as exc:
     print("Silpo Telegram feed unavailable:",str(exc)[:160],flush=True)
    if not items:
     # Preserve the existing direct-site diagnostic if Telegram has no priced
     # current offers; do NOT mark the blocked store as successfully scraped.
     items=await scrape(page,store,url)
   else:
    items=await scrape(page,store,url)
   if store in ("atb","silpo") and not items:
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
 state={"store":store,"checkedAt":now,"source":url,"count":len(items),"status":"ok" if items else "error" if error else "no_data","error":error,"diagnostics":diagnostics if not items else {}}
 if items and not error:
  (path/(store+".json")).write_text(json.dumps(items,ensure_ascii=False,indent=2)+"\n")
 (path/(store+"-status.json")).write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(state,ensure_ascii=False))
if __name__=="__main__":
 a=argparse.ArgumentParser();a.add_argument("--store",required=True,choices=list(SOURCES))
 asyncio.run(main(a.parse_args().store))
