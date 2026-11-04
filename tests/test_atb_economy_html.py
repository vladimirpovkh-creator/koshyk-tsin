#!/usr/bin/env python3
"""No-network ATB HTML tile extraction regression."""
import datetime as dt
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from atb_economy_html import extract_html,collect_html,discover_promo_category_urls,PROMO_URL

DAY=dt.date(2026,11,2)
html='''<!doctype html><html><head><title>Акція Економія</title></head><body>
<div class="products">
 <div class="product-card"><span>-33% до 03.11</span>
  <a href="/product/korm-friskies-300g">Купити Корм 300г Friskies сухий Курка з овочами у АТБ Market</a>
  <span>39.</span><span>40</span> грн /шт <del>58.</del><span>90</span>
 </div>
 <div class="product-card"><span>-25% до 03.11</span>
  <a href="/product/molochne-premia-900">Молоко Премія 900 г пастеризоване</a>
  <span>49.90 грн/шт</span><del>66.50</del>
 </div>
 <div class="product-card"><span>-30% до 01.11</span>
  <a href="/product/expired">Печиво шоколадне 200 г</a>
  <span>20.90 грн/шт</span><del>29.90</del>
 </div>
 <div class="product-card"><span>-25% до 03.11</span>
  <a href="/product/mismatch">Цукерки ванільні 250 г</a>
  <span>50.00 грн/шт</span><del>100.00</del>
 </div>
</div></body></html>'''
rows=extract_html(html,DAY)
assert len(rows)==2,rows
assert {x["price"] for x in rows}=={39.4,49.9}
assert any(x["name"]=="Корм 300г Friskies сухий Курка з овочами" for x in rows)
assert all(x["store"]=="atb" and x["validTo"]=="2026-11-03" for x in rows)
assert len({x["id"] for x in rows})==2
try:
 extract_html('<title>Just a moment</title><body>Cloudflare</body>',DAY)
except RuntimeError:pass
else:raise AssertionError("Challenge page was accepted")

page2=html.replace("/product/korm-friskies-300g","/product/korm-friskies-300g-second")
stats={}
with patch("atb_economy_html._fetch_html",side_effect=[html,page2,page2]) as mocked,patch("atb_economy_html.time.sleep"):
    result=collect_html(stats=stats,max_pages=4,today=DAY)
    assert len(result)==3,result
    assert mocked.call_count==3
    assert len(stats["pagesChecked"])==3
    assert stats["stopReason"]=="Empty or repeated ATB page"
    assert stats["fullCatalog"] is False

for invalid in (0,23):
    try:collect_html(max_pages=invalid,today=DAY)
    except ValueError:pass
    else:raise AssertionError("Unbounded ATB pages accepted")


# Discover category URLs only from official, numerically keyed Economy filters.
links_html='''<a href="/promo/economy?category=344">М'ясо</a>
<a href="/promo/economy?category=595&no-redirect=">Риба</a>
<a href="https://evil.example/promo/economy?category=444">Не АТБ</a>
<a href="/promo/economy?category=344">Повтор</a>'''
discovered,total=discover_promo_category_urls(links_html)
assert discovered==[PROMO_URL+"?category=344",PROMO_URL+"?category=595"],discovered
assert total==2
assert discover_promo_category_urls(links_html,limit=1)==([PROMO_URL+"?category=344"],2)

# The optional category collection preserves all baseline products and
# accepts only offers verified by the very same old/new-price extractor.
promo_base=html.replace("/product/korm-friskies-300g","/product/promo-korm-300g")
promo_base+='<a href="/promo/economy?category=344">Категорія</a>'
promo_category=html.replace("/product/korm-friskies-300g","/product/promo-meat-300g")
promo_stats={}
with patch("atb_economy_html._fetch_html",side_effect=[html,html]), \
     patch("atb_economy_html._fetch_public_url",side_effect=[promo_base,promo_category]) as fetch, \
     patch("atb_economy_html.time.sleep"):
    expanded=collect_html(stats=promo_stats,max_pages=4,today=DAY,
                          expand_promo=True,max_categories=3)
assert len(expanded)==4,expanded
assert fetch.call_count==2
assert promo_stats["acceptedOffers"]==4,promo_stats
assert promo_stats["promoEconomy"]["available"] is True
assert promo_stats["promoEconomy"]["addedOffers"]==2
assert len(promo_stats["promoEconomy"]["categoriesChecked"])==1

# A blocked secondary public page must not delete the original 2 offers.
with patch("atb_economy_html._fetch_html",side_effect=[html,html]), \
     patch("atb_economy_html._fetch_public_url",side_effect=RuntimeError("HTTP 403")), \
     patch("atb_economy_html.time.sleep"):
    fallback_stats={}
    expanded=collect_html(stats=fallback_stats,max_pages=4,today=DAY,
                          expand_promo=True)
assert len(expanded)==2,expanded
assert fallback_stats["promoEconomy"]["available"] is False
assert fallback_stats["acceptedOffers"]==2
for invalid in (0,19):
    try:collect_html(max_categories=invalid,today=DAY)
    except ValueError:pass
    else:raise AssertionError("Category scan accepted unbounded limit")

print("PASS ATB HTML: only isolated current discount cards with valid old/new prices")
