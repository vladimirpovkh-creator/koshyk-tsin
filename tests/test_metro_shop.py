#!/usr/bin/env python3
"""Offline regression tests: public METRO Shop promotions must be unambiguous."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from metro_shop import parse_shop_promotions, catalog_url, collect_shop_promotions

def card(name="Candumy Вино Domaine Petit Var сухе рожеве 750мл",
         price="323,00",old="475,24",available=True,marker="АкціяДіє протягом 10 днів",
         prefix="",extra=""):
    availability=("Доступний (за умови наявності в Київ, Позняки. ТЦ №10)"
                  if available else "Наразі недоступно в METRO Київ, Позняки. ТЦ №10")
    return (marker+"\n"+name+"\nТип пакування:\n1 шт\n"+availability+"\n"+
            prefix+"Ціна з ПДВ "+price+" грн\n"+old+" грн\n"+
            "Ціна без ПДВ 256,35 грн\n430,67 грн / 1 Л\n"+extra+"Купуйте в ТЦ")
date="2026-11-07"
one=parse_shop_promotions(card(),checked_date=date)
assert len(one)==1,one
assert one[0]["price"]==323.00 and one[0]["oldPrice"]==475.24
assert one[0]["date"]==date
assert one[0]["sourceType"]=="metro-official-shop-public-promo"
assert one[0]["url"]=="https://shop.metro.ua/"
assert one[0]["priceVerified"] is True
assert one[0]["conditionsVerified"] is False
assert not parse_shop_promotions(card(available=False),checked_date=date)
assert not parse_shop_promotions(card(marker="Цінова перевага"),checked_date=date)
assert not parse_shop_promotions(card(prefix="250,00 грн від 4+\n"),checked_date=date)
assert not parse_shop_promotions(card(old="323,00"),checked_date=date)
assert not parse_shop_promotions(card(price="500,00"),checked_date=date)
assert not parse_shop_promotions(card().replace("Ціна з ПДВ","Ціна без ПДВ"),checked_date=date)
assert not parse_shop_promotions(card().replace("Київ, Позняки. ТЦ №10","Одеса. ТЦ №2"),checked_date=date)
assert not parse_shop_promotions(card().replace("Тип пакування:","Форма продажу:"),checked_date=date)
assert len(parse_shop_promotions(card()+card(),checked_date=date))==1
assert not parse_shop_promotions(card(price="323,00")+card(price="299,00"),checked_date=date)
print("PASS: METRO public shop only accepts explicit, unambiguous VAT-inclusive Kyiv promotions")

# Allow only explicitly linked official pages; prevent arbitrary URLs and
# private endpoints from being fetched by the BFS traversal.
assert catalog_url("https://shop.metro.ua/shop/category/продукти")
assert catalog_url("https://shop.metro.ua/shop/storelist/abc?page=2")
assert catalog_url("https://shop.metro.ua/shop/category/продукти?page=200") is None
assert catalog_url("https://shop.metro.ua.evil.example/shop/category/x") is None
assert catalog_url("http://shop.metro.ua/shop/category/x") is None
assert catalog_url("https://shop.metro.ua/shop/login/") is None
assert catalog_url("https://shop.metro.ua/shop/category/x?token=private") is None

# Integrate the breadth-first traversal without network; verify duplicates,
# incomplete page reporting and rejecting a non-promotion.
import asyncio
from unittest.mock import patch
import metro_shop

class DummyTab:
    async def close(self):pass
class DummyBrowser:
    async def new_page(self,**kwargs):return DummyTab()
class DummyContext:
    browser=DummyBrowser()
class DummyPage:
    context=DummyContext()

A="https://shop.metro.ua/shop/category/продукти"
B="https://shop.metro.ua/shop/category/продукти/молочні"
C="https://shop.metro.ua/shop/storelist/abc"
def card(name,price="323,00",old="475,24"):
    return ("АкціяДіє протягом 10 днів\n"+name+
            "\nТип пакування:\n1 шт\n"
            "Доступний (за умови наявності в Київ, Позняки. ТЦ №10)\n"
            "Ціна з ПДВ "+price+" грн\n"+old+" грн\n"
            "Ціна без ПДВ 256,35 грн\nКупуйте в ТЦ")
fixture={
    "https://shop.metro.ua/":("Київ, Позняки. ТЦ №10\n"+card("Товар Головний 250г"),[A,B],200),
    A:("Київ, Позняки. ТЦ №10\n"+card("Товар Молочний 250г"),[B,C],200),
    B:("Київ, Позняки. ТЦ №10\n"+card("Товар Молочний 250г"),[],200),
    C:("Київ, Позняки. ТЦ №10\n"+card("Товар Без акції 250г").replace("АкціяДіє","Цінова перевага Діє"),[],200),
}
async def fake_render(tab,url,home=False):
    return fixture[url]
stats={}
with patch.object(metro_shop,"_rendered",side_effect=fake_render):
    rows=asyncio.run(collect_shop_promotions(DummyPage(),stats=stats))
assert len(rows)==2,(rows,stats)
assert stats["categoryPages"]==2 and stats["listPages"]==1,stats
assert stats["unvisitedPages"]==0 and stats["listingPagesComplete"],stats
stats={}
with patch.object(metro_shop,"_rendered",side_effect=fake_render):
    limited=asyncio.run(collect_shop_promotions(DummyPage(),stats=stats,max_pages=1))
assert limited and stats["unvisitedPages"]>0 and not stats["listingPagesComplete"],stats
print("PASS: METRO category/link traversal, deduplication, whitelist and incomplete-coverage warnings")
