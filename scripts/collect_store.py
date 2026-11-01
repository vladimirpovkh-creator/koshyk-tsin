#!/usr/bin/env python3
"""Collect a single retailer independently; write only this retailer's artifacts."""
import argparse, asyncio, datetime as dt, json
from pathlib import Path
from playwright.async_api import async_playwright
from collect_prices import SOURCES, scrape
ROOT=Path(__file__).resolve().parents[1]
async def main(store):
 now=dt.datetime.now(dt.timezone.utc).isoformat()
 url=SOURCES[store]
 items=[];error=""
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=["--no-sandbox"])
  page=await browser.new_page(locale="uk-UA",viewport={"width":1350,"height":900})
  try:
   items=await scrape(page,store,url)
   if store=="atb" and not items:
    title=(await page.title()).lower()
    body=(await page.locator("body").inner_text(timeout=3000)).lower()
    if "перевірка безпеки" in body or "cloudflare" in body or "трохи зачекайте" in title:
     error="ATB Cloudflare challenge: public catalog not accessible to automated runner"
  except Exception as exc:error=str(exc)[:500]
  finally:
   diagnostics={}
   if not items:
    try:
     diagnostics=await page.evaluate("""() => ({finalUrl:location.href,title:document.title,bodyLength:(document.body?.innerText||"").length,priceMentions:(document.body?.innerText||"").match(/(?:грн|₴)/g)?.length||0,productNodes:document.querySelectorAll("[class*=product],[class*=Product],article").length,sample:(document.body?.innerText||"").slice(0,350)})""")
    except Exception as exc:diagnostics={"error":str(exc)[:180]}
   if store=="fora" and not items:
    try:
     samples=await page.evaluate(r"""() => {
       const anchors=[...document.querySelectorAll('a[href]')];
       const product=anchors.filter(a=>{try{return /\\/(product|products|tovar|goods|p)\\//.test(new URL(a.href).pathname)}catch{return false}});
       const withDiscount=product.filter(a=>{let n=a;for(let i=0;i<5&&n;i++,n=n.parentElement){if(/[-−]\\s*\\d{1,2}\\s*%/.test(n.innerText||''))return true}return false});
       return {totalLinks:anchors.length,productLinks:product.length,productLinksWithDiscount:withDiscount.length,samples:(withDiscount.length?withDiscount:product).slice(0,8).map(a=>({href:a.getAttribute('href'),text:(a.closest('article')?.innerText||a.parentElement?.parentElement?.innerText||'').slice(0,380)}))};
     }""")
     diagnostics["cardSamples"]=samples
    except Exception as exc:diagnostics["sampleError"]=str(exc)[:180]
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
