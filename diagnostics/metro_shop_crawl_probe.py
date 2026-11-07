#!/usr/bin/env python3
"""Read-only METRO Shop full-category crawl smoke test; no catalog writes."""
import asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from playwright.async_api import async_playwright
from metro_shop import collect_shop_promotions

async def run():
    stats={}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=["--no-sandbox"])
        page=await browser.new_page(locale="uk-UA",viewport={"width":1350,"height":900})
        try:
            rows=await collect_shop_promotions(page,stats=stats,max_pages=420)
        finally:
            await browser.close()
    print("METRO_CRAWL_DIAGNOSTICS",json.dumps(stats,ensure_ascii=False),flush=True)
    print("METRO_CRAWL_OFFERS",len(rows),"OF_WHICH_UNIQUE",len({r["id"] for r in rows}),flush=True)
    print("METRO_CRAWL_SAMPLES",json.dumps([{"name":r["name"],"price":r["price"],"oldPrice":r["oldPrice"]} for r in rows[:12]],ensure_ascii=False),flush=True)
    assert stats.get("httpStatus")==200,stats
    assert stats.get("pagesVisited",0)>3,stats
    assert stats.get("categoryPages",0)>0,stats
    assert all(r["priceVerified"] is True and 0<r["price"]<r["oldPrice"] for r in rows)
    assert stats["fullCatalog"] is False
    print("PASS: read-only category discovery with strict promotional filter")
asyncio.run(run())
