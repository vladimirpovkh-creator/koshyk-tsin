#!/usr/bin/env python3
"""Offline regression tests: public METRO Shop promotions must be unambiguous."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from metro_shop import parse_shop_promotions

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
