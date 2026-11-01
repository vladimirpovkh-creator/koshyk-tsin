#!/usr/bin/env python3
"""Enumerate public promotional listings with Playwright; never invent offers."""
import asyncio, datetime as dt, hashlib, json, re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
SOURCES={
 "metro":"https://metro.zakaz.ua/uk/custom-categories/promotions/",
 "novus":"https://novus.zakaz.ua/uk/custom-categories/promotions/",
 "fora":"https://fora.ua/all-offers",
 "silpo":"https://silpo.ua/offers/city/kiyiv",
 "atb":"https://www.atbmarket.com/promo/economy",
}
PRICE=re.compile(r"(\d[\d\s]{0,5}[.,]\d{2}|\d{1,5})\s*(?:₴|грн)",re.I)
PERCENT=re.compile(r"-\s*(\d{1,2})\s*%")
DATE=re.compile(r"до\s*(\d{1,2})[.]?(\d{1,2})")
today=dt.date.today()

def amount(v):
 try:
  n=float(v.replace(" ","").replace(",","."))
  return n if .1<=n<=100000 else None
 except ValueError:return None

def expires(text):
 m=DATE.search(text)
 if not m:return None
 try:
  d=dt.date(today.year,int(m[2]),int(m[1]))
  if d<today-dt.timedelta(days=30):d=d.replace(year=d.year+1)
  return d.isoformat()
 except ValueError:return None

def normalize(store,url,row):
 name=re.sub(r"\s+"," ",row.get("name","")).strip()
 if len(name)<6 or len(name)>190:return None
 prices=[amount(p) for p in PRICE.findall(row.get("priceText",""))]
 prices=[v for v in prices if v is not None]
 if not prices:return None
 # Source markup order normally shows old -> new; guard against ambiguous values.
 price=min(prices)
 old=max(prices) if len(prices)>=2 and max(prices)>price else None
 if old is None and not PERCENT.search(row.get("priceText","")):return None
 link=row.get("url") or url
 if not link.startswith("http"):link=urljoin(url,link)
 if urlparse(link).netloc not in {urlparse(url).netloc}:return None
 key=hashlib.sha256((store+"|"+link+"|"+name).encode()).hexdigest()[:18]
 data={"id":store+"-"+key,"name":name,"store":store,"price":price,"category":"Акційні товари","date":today.isoformat(),"url":link,"locationKey":"kyiv","location":"Онлайн-каталог; наявність у конкретному магазині не перевірена","sourceType":"live-promo"}
 if old and old>price:data["oldPrice"]=old
 expiry=expires(row.get("priceText",""))
 if expiry:
  if expiry<today.isoformat():return None
  data["validTo"]=expiry
 return data

async def scrape(page,store,url):
 await page.goto(url,wait_until="domcontentloaded",timeout=45000)
 try:await page.wait_for_timeout(2500)
 except Exception:pass
 gathered={}
 empty=0
 for cycle in range(35):
  rows=await page.evaluate("""() => {
    const out=[];
    const els=[...document.querySelectorAll('a[href]')];
    for(const a of els){
      const href=a.getAttribute('href')||'';
      if(!/(product|tovar|\/p\/|\/goods\/|\/catalog\/)/i.test(href))continue;
      let node=a;
      for(let j=0;j<4 && node.parentElement;j++){
        const p=node.parentElement;
        const t=p.innerText||'';
        if(/(?:₴|грн)/i.test(t) && t.length<1000){node=p;break;}
        node=p;
      }
      const text=(node.innerText||'').replace(/\s+/g,' ').trim();
      const image=node.querySelector('img[alt]');
      const name=(image?.getAttribute('alt')||a.getAttribute('title')||a.innerText||'').replace(/\s+/g,' ').trim();
      if(!name || !/(?:₴|грн)/i.test(text))continue;
      out.push({name,priceText:text,url:a.href});
    }
    // Some stores render product cards without product links.
    return out;
  }""")
  before=len(gathered)
  for row in rows:
   item=normalize(store,url,row)
   if item:gathered[item["id"]]=item
  empty=empty+1 if len(gathered)==before else 0
  # Scroll to reveal infinite lists, then click 'show more' controls where present.
  await page.evaluate("window.scrollTo(0,document.body.scrollHeight)")
  await page.wait_for_timeout(950)
  clicked=False
  for label in ["Показати ще","Показати більше","Завантажити ще","Показать еще","Load more"]:
   try:
    button=page.get_by_text(label,exact=False).last
    if await button.count() and await button.is_visible(timeout=600):
     await button.click(timeout=1500);clicked=True;break
   except Exception:pass
  if not clicked and empty>=3:break
 return list(gathered.values())

async def main():
 DATA.mkdir(parents=True,exist_ok=True)
 now=dt.datetime.now(dt.timezone.utc).isoformat()
 status={};result={}
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,args=["--no-sandbox"])
  for store,url in SOURCES.items():
   page=await browser.new_page(locale="uk-UA",viewport={"width":1350,"height":900})
   try:
    items=await scrape(page,store,url)
    for x in items:result[x["id"]]=x
    status[store]={"status":"ok" if items else "no_data","count":len(items),"checkedAt":now,"url":url}
   except Exception as e:
    status[store]={"status":"error","count":0,"checkedAt":now,"error":str(e)[:220],"url":url}
   finally:await page.close()
  await browser.close()
 # Never use seeded or expired prices as a substitute for fresh promotions.
 offers=list(result.values())
 (DATA/"offers.json").write_text(json.dumps(offers,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (DATA/"status.json").write_text(json.dumps({"generatedAt":now,"total":len(offers),"sources":status},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"total":len(offers),"sources":status},ensure_ascii=False))
if __name__=="__main__":asyncio.run(main())
