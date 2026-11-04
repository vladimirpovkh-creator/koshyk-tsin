#!/usr/bin/env python3
"""Ensure Zakaz promotion URLs cover numbered pages and stop at the last page."""
import asyncio
import sys
import types
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
if "playwright.async_api" not in sys.modules:
 sys.modules["playwright"]=types.ModuleType("playwright")
 p=types.ModuleType("playwright.async_api")
 p.async_playwright=None
 sys.modules["playwright.async_api"]=p

from collect_prices import zakaz_catalog, normalize, ZAKAZ_MAX_PAGES

class Page:
 async def evaluate(self,script):
  return 12

async def main():
 url="https://novus.zakaz.ua/uk/custom-categories/promotions/"
 visited=[]
 async def mocked_scrape(page,store,link,single_page=False):
  assert single_page and store=="novus"
  visited.append(link)
  number=int(link.split("page=")[1]) if "page=" in link else 1
  return [{"id":f"novus-{number}","name":"Test offer"}]
 full_stats={}
 with patch("collect_prices.scrape",side_effect=mocked_scrape):
  items=await zakaz_catalog(Page(),"novus",url,stats=full_stats)
 assert len(items)==12,items
 assert full_stats["listingPagesComplete"] is True,full_stats
 assert full_stats["fullCatalog"] is False,full_stats
 assert visited==[url]+[url+"?page="+str(n) for n in range(2,13)],visited
 visited.clear()
 async def repeated(page,store,link,single_page=False):
  visited.append(link)
  return [{"id":"same-product"}]
 short_stats={}
 with patch("collect_prices.scrape",side_effect=repeated):
  items=await zakaz_catalog(Page(),"novus",url,stats=short_stats)
 assert len(items)==1 and len(visited)==3,(items,visited)
 assert short_stats["listingPagesComplete"] is False,short_stats
 try:
  await zakaz_catalog(Page(),"novus",url,max_pages=ZAKAZ_MAX_PAGES+1)
  raise AssertionError("Unbounded traversal accepted")
 except ValueError:pass

asyncio.run(main())
print("PASS: Zakaz follows numbered pages, rejects repeats and bounds requests")

# A promotion can be priced correctly but explicitly unavailable to purchase.
URL="https://novus.zakaz.ua/uk/custom-categories/promotions/"
basic={"name":"Молоко тестове 1л","priceText":"49.99 грн 39.99 грн до 11.11",
       "url":"https://novus.zakaz.ua/uk/products/moloko-testove--123/"}
accepted=normalize("novus",URL,basic)
assert accepted and accepted["availabilityStatus"]=="unverified",accepted
assert "наявність не підтверджена" in accepted["sourceLabel"]
assert normalize("novus",URL,{**basic,"unavailable":True}) is None
for unavailable_text in ("Немає в наявності","Немає у наявності","Out of stock"):
 assert normalize("novus",URL,{**basic,"availabilityText":unavailable_text}) is None
# Never mark an otherwise valid offer as physically in stock.
assert accepted.get("inStock") is not True
print("PASS: NOVUS excludes explicit out-of-stock cards and does not assert stock")
