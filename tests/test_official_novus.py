#!/usr/bin/env python3
"""Small browser fixture for official NOVUS card grouping and price validation."""
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import datetime as dt
import collect_prices
from collect_prices import official_novus, normalize, SOURCES

HTML = """<ul>
<li class="product-item"><div class="product-item-info">
  <span>з 29.10 по 11.11</span><span>-16%</span>
  <span class="old-price"><span class="price">319.00</span></span>
  <span class="special-price"><span class="price">269.00</span></span>
  <a class="product-item-link" href="https://novus.ua/stejk-test.html">Стейк свинний тестовий охолоджений ваг</a>
  <a href="https://novus.zakaz.ua/uk/products/123/">Купити онлайн</a>
</div></li>
<li class="product-item"><div class="product-item-info">
  <span>з 29.10 по 11.11</span>
  <span class="old-price"><span class="price">289.00</span></span>
  <span class="special-price"><span class="price">269.00</span></span>
  <a class="product-item-link" href="https://novus.ua/stegno-test.html">Стегно індички охолоджене ваг</a>
</div></li>
<li class="product-item"><div class="product-item-info">
  <span>з 31.10 по 01.11</span><span>-30%</span>
  <span class="old-price"><span class="price">169.00</span></span>
  <span class="special-price"><span class="price">119.00</span></span>
  <a class="product-item-link" href="https://novus.ua/granat-test.html">Гранат тестовий ваговий</a>
</div></li>
<li class="product-item"><div class="product-item-info">
  <span>з 29.10 по 11.11</span><span>-98%</span>
  <span class="old-price"><span class="price">319.00</span></span>
  <span class="special-price"><span class="price">269.00</span></span>
  <a class="product-item-link" href="https://novus.ua/invalid-test.html">Неправильна знижка тестовий товар</a>
</div></li>
</ul>"""

async def test():
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(headless=True,args=["--no-sandbox"])
  page=await browser.new_page()
  await page.set_content(HTML)
  rows=await official_novus(page)
  await browser.close()
 assert len(rows)==3,(len(rows),rows)
 keyed={r["url"].split("/")[-1]:r for r in rows}
 assert keyed["stejk-test.html"]["price"]==269.0
 assert keyed["stegno-test.html"]["oldPrice"]==289.0
 collect_prices.today=dt.date(2026,11,2)
 normalized=[normalize("novus_official",SOURCES["novus_official"],r) for r in rows]
 active=[r for r in normalized if r is not None]
 assert len(active)==2,(collect_prices.today,normalized)
 assert all(r["channel"]=="official" and r["url"].startswith("https://novus.ua/") for r in active)
 print("PASS official NOVUS: card separation, two-decimal prices, offline/online source separation, discount and expiration checks")

if __name__=="__main__":
 asyncio.run(test())
