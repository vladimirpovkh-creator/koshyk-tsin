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
 "novus_official":"https://novus.ua/",
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
 # Separate validation for Fora: mixed units and neighboring cards can create false 90% discounts.
 text=row.get("priceText","")
 prices=[amount(p) for p in PRICE.findall(text)]
 prices=[v for v in prices if v is not None]
 if not prices and store!="fora":return None
 reduction=PERCENT.search(text)
 if store=="atb" and len(prices)==1:
  # ATB shows the old price without a repeated currency suffix.
  tail=re.search(r"(?:грн|₴)(?:/\\s*(?:шт|кг|100г))?[^\\d]{0,50}(\\d{1,5}[.,]\\d{2})(?!\\d)",text,re.I)
  if tail:
   other=amount(tail.group(1))
   if other and other>prices[0]:prices.append(other)
 if store=="fora":
  # Require old/new numbers from the SAME card matching its actual discount badge.
  # Fora may render 14.90 as "14 90" or as "14,90".
  disc=re.search(r"[-−]\s*(\d{1,2})\s*%",text)
  if not disc:return None
  badge=int(disc.group(1))
  if badge<=0:return None
  amounts=[]
  # Detect decimal amounts as well as hryvnia/kopeck separated by whitespace.
  for m in re.finditer(r"(?<![\d.,])(?:\d{1,5}[.,]\d{1,2}|\d{1,5}\s+\d{2})(?![\d.,])",text):
   v=amount(re.sub(r"\s+",".",m.group(0)))
   if v is not None:amounts.append((m.start(),v))
  choices=[]
  for i,(pos_old,old_candidate) in enumerate(amounts):
   for j,(pos_new,new_candidate) in enumerate(amounts):
    if i==j or old_candidate<=new_candidate:continue
    computed=100*(old_candidate-new_candidate)/old_candidate
    if abs(badge-computed)<=1.2:
     choices.append((abs(pos_old-disc.start())+abs(pos_new-disc.end()),old_candidate,new_candidate))
  if not choices:return None
  choices.sort()
  if len(choices)>1 and choices[0][0]==choices[1][0] and choices[0][1:]!=choices[1][1:]:return None
  _,old,price=choices[0]
  if re.match(r"^(купити|додати|ціна)\b",name,re.I):return None
 else:
  price=min(prices)
  old=max(prices) if len(prices)>=2 and max(prices)>price else None
  if old is None and not reduction:return None
  if store in ("silpo","novus_official") and old and reduction:
   if abs(int(reduction.group(1))-100*(old-price)/old)>3:return None
 link=row.get("url") or url
 if not link.startswith("http"):link=urljoin(url,link)
 if urlparse(link).netloc != urlparse(url).netloc:return None
 key=hashlib.sha256((store+"|"+link+"|"+name).encode()).hexdigest()[:18]
 data={"id":store+"-"+key,"name":name,"store":store,"price":price,"category":"Акційні товари","date":today.isoformat(),"url":link,"locationKey":"kyiv","location":"Онлайн-каталог; наявність у конкретному магазині не перевірена","sourceType":"live-promo"}
 if store=="novus_official":
  data["store"]="novus"
  data["channel"]="official"
  data["sourceLabel"]="NOVUS.ua — офіційні акції (умови за посиланням)"
 elif store=="novus":
  data["channel"]="online"
  data["sourceLabel"]="NOVUS Zakaz.ua — онлайн"
 if old and old>price:data["oldPrice"]=old
 if store=="fora":data["priceVerified"]=True
 expiry=expires(row.get("priceText",""))
 if expiry:
  if expiry<today.isoformat():return None
  data["validTo"]=expiry
 return data

async def targeted_cards(page, store):
 """Read isolated retailer product cards; avoid invalid JS regex and mixed prices."""
 return await page.evaluate(r"""(store) => {
   const out=[],seen=new Set();
   const selectors=store==='atb'
     ? "[class*='product-card'],[class*='product_card'],[class*='catalog-item'],[class*='product-item'],article"
     : "[class*='product-card'],[class*='productCard'],[class*='offer-card'],article";
   const money=/\d{1,5}(?:[.,]\d{2})?\s*(?:грн|₴)/gi;
   for(const card of document.querySelectorAll(selectors)){
     const text=(card.innerText||'').replace(/\s+/g,' ').trim();
     if(text.length<20||text.length>500)continue;
     const badge=text.match(/[-−]\s*(\d{1,2})\s*%/);
     const nums=[...text.matchAll(money)].map(m=>parseFloat(m[0].replace(/\s*(грн|₴)/i,'').replace(',','.')));
     if(!badge||nums.length<2)continue;
     const price=Math.min(...nums),old=Math.max(...nums);
     if(!(price>0&&old>price&&Math.abs(100*(1-price/old)-Number(badge[1]))<=2))continue;
     const anchor=card.querySelector("a[href*='/product'],a[href*='/catalog'],a[href*='/p/'],a[href*='/goods']");
     if(!anchor)continue;
     const url=anchor.href;
     if(new URL(url).hostname!==location.hostname)continue;
     const title=card.querySelector("[class*='name'],[class*='title'],img[alt]");
     const name=(title?.getAttribute('alt')||title?.textContent||anchor.getAttribute('title')||anchor.innerText||'').replace(/\s+/g,' ').trim();
     if(name.length<7||name.length>180||seen.has(url))continue;
     seen.add(url);
     out.push({name,priceText:old.toFixed(2)+" грн "+price.toFixed(2)+" грн -"+badge[1]+"%",url});
   }
   return out;
 }""",store)

async def fora_cards(page):
 """Read individual Fora product tiles; never treat category navigation as offers."""
 return await page.evaluate(r"""() => {
  const out=[],seen=new Set();
  const links=[...document.querySelectorAll('a[href]')].filter(a=>{
   let u;try{u=new URL(a.href)}catch{return false}
   if(u.hostname!==location.hostname)return false;
   if(/^\/(category|all-offers|search|cart|checkout|brand|brands)(\/|$)/.test(u.pathname))return false;
   return /\/(product|products|tovar|goods|p)\//.test(u.pathname);
  });
  for(const a of links){
   let card=a;
   for(let depth=0;depth<6&&card.parentElement;depth++){
    card=card.parentElement;
    const raw=(card.innerText||'').replace(/\s+/g,' ').trim();
    if(raw.length<20||raw.length>600)continue;
    const badges=[...raw.matchAll(/[-−]\s*(\d{1,2})\s*%/g)];
    if(badges.length!==1)continue;
    const otherProductLinks=[...card.querySelectorAll('a[href]')].filter(x=>{
      try{return /\/(product|products|tovar|goods|p)\//.test(new URL(x.href).pathname)}catch{return false}
    });
    if(new Set(otherProductLinks.map(x=>x.href)).size>1)break;
    const image=a.querySelector('img[alt]')||card.querySelector('img[alt]');
    const title=card.querySelector("[class*='product-name'],[class*='productName'],[class*='product-title'],[class*='productTitle']");
    const name=(image?.alt||title?.textContent||a.getAttribute('title')||a.innerText||'').replace(/\s+/g,' ').trim();
    if(name.length<6||name.length>190||/^(купити|додати|акції)/i.test(name))continue;
    const key=a.href+'|'+name;
    if(seen.has(key))break;
    seen.add(key);out.push({name,priceText:raw,url:a.href});
    break;
   }
  }
  return out;
 }""")

async def official_novus(page):
 """Extract verified old/new prices from one isolated NOVUS product tile."""
 return await page.evaluate(r"""() => {
  const result=[],seen=new Set();
  const anchors=[...document.querySelectorAll('a[href]')].filter(a=>{
   try {const u=new URL(a.href);return u.hostname==='novus.ua' && /\/[^/]+\.html(?:$|\?)/.test(u.pathname) && !/catalog|search|category/.test(u.pathname)}
   catch{return false}
  });
  for(const a of anchors){
   const name=(a.getAttribute('title')||a.innerText||a.querySelector('img[alt]')?.alt||'').replace(/\s+/g,' ').trim();
   if(name.length<7||name.length>180)continue;
   let card=a,raw='';
   for(let depth=0;depth<6&&card.parentElement;depth++){
    card=card.parentElement;
    const text=(card.innerText||'').replace(/\s+/g,' ').trim();
    const links=[...card.querySelectorAll('a[href]')].filter(x=>{try{return new URL(x.href).hostname==='novus.ua'&&/\.html$/.test(new URL(x.href).pathname)}catch{return false}});
    const prices=[...text.matchAll(/(?<![\d.,])\d{1,5}[.,]\d{2}(?![\d.,])/g)].map(x=>Number(x[0].replace(',','.')));
    if(links.length>2||text.length>390)break;
    if(prices.length===2&&prices[0]>prices[1]&&text.length<300){raw=text;break}
   }
   if(!raw||seen.has(a.href))continue;
   const nums=[...raw.matchAll(/(?<![\d.,])\d{1,5}[.,]\d{2}(?![\d.,])/g)].map(x=>Number(x[0].replace(',','.')));
   if(nums.length!==2||nums[0]<=nums[1]||nums[1]<1)continue;
   const reduction=raw.match(/-\s*(\d{1,2})\s*%/);
   if(reduction&&Math.abs(Number(reduction[1])-100*(1-nums[1]/nums[0]))>3)continue;
   seen.add(a.href);
   result.push({name,priceText:nums[0].toFixed(2)+' грн '+nums[1].toFixed(2)+' грн '+(reduction?'-'+reduction[1]+'%':''),url:a.href});
  }
  return result;
 }""")

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
  if store=='fora':
   rows += await fora_cards(page)
  if store in ('silpo','atb'):
   rows += await targeted_cards(page,store)
  if store=='novus_official':
   rows = await official_novus(page)
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
