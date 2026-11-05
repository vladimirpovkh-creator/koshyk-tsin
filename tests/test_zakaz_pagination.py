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

class PageWithoutPagination:
 async def evaluate(self,script):
  return None

async def main():
 url="https://novus.zakaz.ua/uk/custom-categories/promotions/"
 visited=[]
 async def mocked_scrape(page,store,link,single_page=False,stats=None):
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
 async def repeated(page,store,link,single_page=False,stats=None):
  visited.append(link)
  return [{"id":"same-product"}]
 short_stats={}
 with patch("collect_prices.scrape",side_effect=repeated):
  items=await zakaz_catalog(PageWithoutPagination(),"novus",url,stats=short_stats)
 assert len(items)==1 and len(visited)==3,(items,visited)
 assert short_stats["listingPagesComplete"] is False,short_stats
 # Entire middle pages can be out of stock, while later pages have offers.
 visited.clear()
 async def unavailable_middle(page,store,link,single_page=False,stats=None):
  number=int(link.split("page=")[1]) if "page=" in link else 1
  visited.append(number)
  return [] if number in (7,8) else [{"id":f"offer-{number}"}]
 continue_stats={}
 with patch("collect_prices.scrape",side_effect=unavailable_middle):
  items=await zakaz_catalog(Page(),"novus",url,stats=continue_stats)
 assert len(items)==10 and visited==list(range(1,13)),(items,visited)
 assert continue_stats["listingPagesComplete"] is False,continue_stats
 assert continue_stats["stopReason"]=="last numbered page reached",continue_stats
 # Stop ONLY after three consecutive pages whose price cards are ALL
 # explicitly marked unavailable. Two such pages must not stop traversal.
 visited.clear()
 async def stock_pages(page,store,link,single_page=False,stats=None):
  number=int(link.split("page=")[1]) if "page=" in link else 1
  visited.append(number)
  if number in (3,4,6,7,8):
   stats.update({"cardsWithPrice":30,"explicitlyUnavailable":30})
   return []
  stats.update({"cardsWithPrice":30,"explicitlyUnavailable":0})
  return [{"id":f"valid-{number}"}]
 stock_stats={}
 with patch("collect_prices.scrape",side_effect=stock_pages):
  result=await zakaz_catalog(Page(),"novus",url,stats=stock_stats)
 assert visited==list(range(1,9)),visited
 assert len(result)==3,result
 assert stock_stats["stopReason"].startswith("three consecutive pages"),stock_stats
 assert stock_stats["consecutiveUnavailablePagesAtStop"]==3,stock_stats
 assert stock_stats["listingPagesComplete"] is False,stock_stats
 # Empty pages lacking positive evidence of unavailable products are not
 # proof of out-of-stock inventory and must not trigger the new stop condition.
 visited.clear()
 async def empty_unknown(page,store,link,single_page=False,stats=None):
  number=int(link.split("page=")[1]) if "page=" in link else 1
  visited.append(number)
  stats.update({"cardsWithPrice":0,"explicitlyUnavailable":0})
  return [] if number in (3,4,5) else [{"id":f"valid-{number}"}]
 with patch("collect_prices.scrape",side_effect=empty_unknown):
  result=await zakaz_catalog(Page(),"novus",url)
 assert visited==list(range(1,13)),visited
 assert len(result)==9,result
 # METRO retries transient navigation failures rather than dropping tail pages.
 metro_url="https://metro.zakaz.ua/uk/custom-categories/promotions/"
 attempts={}
 async def flaky_metro(page,store,link,single_page=False,stats=None):
  assert store=="metro"
  number=int(link.split("page=")[1]) if "page=" in link else 1
  attempts[number]=attempts.get(number,0)+1
  if number==6 and attempts[number]<3:
   raise TimeoutError("simulated transient browser navigation timeout")
  return [{"id":f"metro-{number}"}]
 metro_stats={}
 with patch("collect_prices.scrape",side_effect=flaky_metro),patch("collect_prices.asyncio.sleep",return_value=None):
  metro_items=await zakaz_catalog(Page(),"metro",metro_url,stats=metro_stats)
 assert len(metro_items)==12 and attempts[6]==3,(metro_items,attempts)
 assert metro_stats["listingPagesComplete"] is True,metro_stats
 # All retries exhausted: mark partial traversal, do not mislabel it complete.
 attempts.clear()
 async def failed_metro(page,store,link,single_page=False,stats=None):
  number=int(link.split("page=")[1]) if "page=" in link else 1
  attempts[number]=attempts.get(number,0)+1
  if number==6:raise TimeoutError("persistent timeout")
  return [{"id":f"metro-{number}"}]
 failure_stats={}
 with patch("collect_prices.scrape",side_effect=failed_metro),patch("collect_prices.asyncio.sleep",return_value=None):
  failed_items=await zakaz_catalog(Page(),"metro",metro_url,stats=failure_stats)
 assert len(failed_items)==5 and attempts[6]==3,attempts
 assert failure_stats["listingPagesComplete"] is False,failure_stats
 assert failure_stats["stopReason"].startswith("page request failed after retries"),failure_stats
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
