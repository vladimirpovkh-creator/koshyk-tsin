#!/usr/bin/env python3
"""Fora: retry large failed windows in small chunks and report unverified coverage."""
import asyncio
import sys
import types
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
if "playwright.async_api" not in sys.modules:
 sys.modules["playwright"]=types.ModuleType("playwright")
 p=types.ModuleType("playwright.async_api")
 p.async_playwright=None
 sys.modules["playwright.async_api"]=p
from collect_prices import FORA_MAX_PAGE,FORA_PAGE_WINDOW,fora_catalog

BASE="https://fora.ua/all-offers"
def row(slug):
 return {"name":"Молоко тестове 1л "+slug,"url":"https://fora.ua/product/"+slug,
  "priceText":"50.00 грн -20% 40.00 грн","oldPrice":50,"price":40,"discount":20}

class Page:
 def __init__(self):self.urls=[]
 async def goto(self,url,**kwargs):self.urls.append(url)
 def locator(self,selector):return self
 @property
 def first(self):return self
 async def wait_for(self,**kwargs):pass
 async def wait_for_timeout(self,ms):pass

async def verify():
 # Smaller range returns offers despite the original 61-90 page failing.
 page=Page()
 async def recover(p):
  url=p.urls[-1]
  if "from=1&" in url:return [row("initial")]
  if "from=31&" in url:return [row("later")]
  if "from=61&to=70" in url:return [row("recovered")]
  return []
 stats={}
 with patch("collect_prices.fora_cards",side_effect=lambda p: recover(p)):
  result=await fora_catalog(page,BASE,max_page=90,stats=stats)
 assert len(result)==3,result
 assert stats["hasUnresolvedFailures"] is False,stats
 assert stats["listingPagesComplete"] is True,stats
 assert stats["windowsChecked"][-1]["recoveredBySmallerWindows"] is True
 assert any("from=61&to=70" in u for u in page.urls),page.urls

 # Even when product cards have failed to load everywhere, do not describe
 # a truncated offer list as freshly verified complete.
 page=Page()
 async def no_tail(p):
  return [row("first")] if "from=1&" in p.urls[-1] else []
 stats={}
 with patch("collect_prices.fora_cards",side_effect=lambda p:no_tail(p)):
  result=await fora_catalog(page,BASE,max_page=90,stats=stats)
 assert len(result)==1,result
 assert stats["hasUnresolvedFailures"] is True,stats
 assert stats["listingPagesComplete"] is False,stats
 assert stats["unresolvedWindows"][0]["from"]==31,stats
 assert stats["unresolvedWindows"][1]["from"]==61,stats
 assert stats["stopReason"]=="two consecutive empty or repeated page windows"
 assert await fora_catalog(Page(),BASE,max_page=FORA_MAX_PAGE+1)==[]
 assert await fora_catalog(Page(),BASE,page_window=FORA_PAGE_WINDOW+1)==[]

asyncio.run(verify())
print("PASS: Fora retries empty windows in smaller ranges and flags partial coverage")
