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
  try:items=await scrape(page,store,url)
  except Exception as exc:error=str(exc)[:500]
  finally:
   await page.close()
   await browser.close()
 path=ROOT/"data"/"stores"
 path.mkdir(parents=True,exist_ok=True)
 state={"store":store,"checkedAt":now,"source":url,"count":len(items),"status":"ok" if items else "error" if error else "no_data","error":error}
 (path/(store+".json")).write_text(json.dumps(items,ensure_ascii=False,indent=2)+"\n")
 (path/(store+"-status.json")).write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(state,ensure_ascii=False))
if __name__=="__main__":
 a=argparse.ArgumentParser();a.add_argument("--store",required=True,choices=list(SOURCES))
 asyncio.run(main(a.parse_args().store))
