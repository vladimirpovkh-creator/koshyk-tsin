#!/usr/bin/env python3
"""No-network ATB HTML tile extraction regression."""
import datetime as dt
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from atb_economy_html import extract_html

DAY=dt.date(2026,11,2)
html='''<!doctype html><html><head><title>Акція Економія</title></head><body>
<div class="products">
 <div class="product-card"><span>-33% до 03.11</span>
  <a href="/product/korm-friskies-300g">Корм 300г Friskies сухий Курка з овочами</a>
  <span>39.40 грн/шт</span><del>58.90</del>
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
assert all(x["store"]=="atb" and x["validTo"]=="2026-11-03" for x in rows)
assert len({x["id"] for x in rows})==2
try:
 extract_html('<title>Just a moment</title><body>Cloudflare</body>',DAY)
except RuntimeError:pass
else:raise AssertionError("Challenge page was accepted")
print("PASS ATB HTML: only isolated current discount cards with valid old/new prices")
