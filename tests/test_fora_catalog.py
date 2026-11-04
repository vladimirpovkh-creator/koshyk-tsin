#!/usr/bin/env python3
"""Fora collection must continue beyond the old 36-page cutoff."""
import sys
import types
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
if "playwright.async_api" not in sys.modules:
 sys.modules["playwright"]=types.ModuleType("playwright")
 async_api=types.ModuleType("playwright.async_api")
 async_api.async_playwright=None
 sys.modules["playwright.async_api"]=async_api
from collect_prices import FORA_MAX_PAGE,FORA_PAGE_WINDOW,fora_catalog

BASE="https://fora.ua/all-offers"

def row(name,slug,old,price,discount):
 return {"name":name,"url":f"https://fora.ua/product/{slug}",
  "priceText":f"{old:.2f} грн -{discount}% {price:.2f} грн",
  "oldPrice":old,"price":price,"discount":discount}

class Locator:
 async def wait_for(self,**kwargs):pass

class Page:
 def __init__(self):self.urls=[]
 async def goto(self,url,**kwargs):self.urls.append(url)
 def locator(self,selector):return self
 @property
 def first(self):return Locator()
 async def wait_for_timeout(self,ms):pass

async def test():
 page=Page()
 first=[row("Молоко тестове 1л","moloko-test",50,40,20)]
 later=[row("Пиво Corona Zero світле безалкогольне, 0,33л",
            "pyvo-corona-zero-svitle-bezalkogolne-957511",79.3,65.9,17)]
 coverage={}
 with patch("collect_prices.fora_cards",side_effect=[first,later,[],[]]):
  items=await fora_catalog(page,BASE,max_page=90,page_window=30,stats=coverage)
 assert len(items)==2,items
 assert coverage["listingPagesComplete"] is False,coverage
 assert coverage["stopReason"]=="page limit reached",coverage
 assert any("Corona Zero" in item["name"] for item in items)
 assert page.urls==[
  BASE+"?from=1&to=30",
  BASE+"?from=31&to=60",
  BASE+"?from=61&to=90",
  BASE+"?from=61&to=90",  # retry an empty window once
 ]
 assert await fora_catalog(Page(),BASE,max_page=FORA_MAX_PAGE+1)==[]
 assert await fora_catalog(Page(),BASE,page_window=FORA_PAGE_WINDOW+1)==[]

def run(coroutine):
 try:
  while True:coroutine.send(None)
 except StopIteration as done:return done.value

run(test())
print("PASS: Fora catalog continues through bounded page windows beyond page 36")
