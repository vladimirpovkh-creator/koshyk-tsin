#!/usr/bin/env python3
"""METRO public catalog navigation diagnostics: no production writes."""
import asyncio,json
from urllib.parse import urlparse
from playwright.async_api import async_playwright

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=["--no-sandbox"])
  page=await browser.new_page(locale="uk-UA",viewport={"width":1350,"height":900})
  try:
   resp=await page.goto("https://shop.metro.ua/",wait_until="domcontentloaded",timeout=25000)
   await page.wait_for_timeout(12000)
   print("HOME",resp.status,page.url,flush=True)
   links=await page.locator("a[href]").evaluate_all("""els=>els.map(a=>({
     text:(a.innerText||a.getAttribute('aria-label')||'').trim().replace(/\\s+/g,' ').slice(0,75),
     href:a.href
   })).filter(x=>x.href.startsWith('https://shop.metro.ua/'))""")
   uniq={x['href']:x for x in links}
   print("PUBLIC_LINKS",json.dumps(list(uniq.values())[:115],ensure_ascii=False),flush=True)
   print("LINK_TOTAL",len(uniq),flush=True)
   nav=[x for x in uniq.values() if x['text'] and ('каталог' in x['text'].lower() or 'продукти' in x['text'].lower() or 'молочн' in x['text'].lower() or 'м’яс' in x['text'].lower() or 'риб' in x['text'].lower() or 'свіж' in x['text'].lower())]
   print("NAV_CANDIDATES",json.dumps(nav[:60],ensure_ascii=False),flush=True)
   for x in nav[:4]:
    if x['href'].rstrip('/')=="https://shop.metro.ua":continue
    url=x['href'];u=urlparse(url)
    if u.scheme!="https" or u.hostname!="shop.metro.ua":continue
    try:
     r=await page.goto(url,wait_until="domcontentloaded",timeout=22000)
     await page.wait_for_timeout(7500)
     body=await page.locator("body").inner_text(timeout=8000)
     print("CATEGORY",json.dumps({"url":url,"status":r.status if r else None,"length":len(body),"priceMentions":body.count("Ціна з ПДВ"),"promoLabels":body.count("АкціяДіє"),"store":"Київ, Позняки. ТЦ №10" in body,"anchors":await page.locator("a[href]").count(),
       "pageLinks":(await page.locator("a[href]").evaluate_all("""els=>els.map(a=>({t:(a.innerText||'').trim().slice(0,45),h:a.href})).filter(x=>x.h.includes('page=')||x.h.includes('/category/')||x.h.includes('/pv/')||x.h.includes('/storelist/')).slice(0,50)""")),
       "buttonLabels":(await page.locator("button").evaluate_all("""els=>els.map(x=>(x.innerText||x.getAttribute('aria-label')||'').trim()).filter(Boolean).slice(0,45)"""))},ensure_ascii=False),flush=True)
    except Exception as e:print("NAV_ERROR",url,type(e).__name__,flush=True)
  finally:await browser.close()
asyncio.run(main())
