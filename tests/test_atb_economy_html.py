#!/usr/bin/env python3
"""No-network ATB HTML tile extraction regression."""
import datetime as dt
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from atb_economy_html import extract_html,collect_html

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

for invalid in (0,7):
    try:collect_html(max_pages=invalid,today=DAY)
    except ValueError:pass
    else:raise AssertionError("Unbounded ATB pages accepted")

print("PASS ATB HTML: only isolated current discount cards with valid old/new prices")
