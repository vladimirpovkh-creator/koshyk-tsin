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
 if not prices and store not in ("fora","novus_official"):return None
 reduction=PERCENT.search(text)
 if store=="atb" and len(prices)==1:
  # ATB shows the old price without a repeated currency suffix.
  tail=re.search(r"(?:грн|₴)(?:/\\s*(?:шт|кг|100г))?[^\\d]{0,50}(\\d{1,5}[.,]\\d{2})(?!\\d)",text,re.I)
  if tail:
   other=amount(tail.group(1))
   if other and other>prices[0]:prices.append(other)
 if store=="novus_official":
  old=row.get("oldPrice");price=row.get("price")
  if not isinstance(old,(int,float)) or not isinstance(price,(int,float)) or not old>price>0:return None
  badge=row.get("discount")
  if badge is not None and abs(100*(old-price)/old-badge)>2:return None
  day=row.get("validToDay");month=row.get("validToMonth")
  if day is not None and month is not None:
   try:
    valid=dt.date(today.year,int(month),int(day))
    if valid<today-dt.timedelta(days=30):valid=valid.replace(year=today.year+1)
    if valid<today:return None
   except (ValueError,TypeError):return None
 elif store=="fora":
  # Prices come from a single isolated /product/ card in fora_cards().
  old=row.get("oldPrice")
  price=row.get("price")
  badge=row.get("discount")
  if not isinstance(old,(int,float)) or not isinstance(price,(int,float)) or not isinstance(badge,(int,float)):return None
  if price<=0 or old<=price or abs(100*(old-price)/old-badge)>1.2:return None
  if not "/product/" in (row.get("url") or ""):return None

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
 if store=="novus_official" and row.get("validToDay") is not None:
  data["validTo"]=valid.isoformat()
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
 """Read Fora's actual /product/ cards once, with explicit currency and discount validation."""
 return await page.evaluate(r"""() => {
  const out=[],seen=new Set();
  for(const a of document.querySelectorAll('a[href*="/product/"]')){
   let u;try{u=new URL(a.href)}catch{continue}
   if(u.hostname!==location.hostname||!u.pathname.startsWith('/product/'))continue;
   if(seen.has(u.pathname))continue;
   let node=a,raw='',match=null;
   for(let i=0;i<5&&node;i++,node=node.parentElement){
    const t=(node.innerText||'').trim();
    if(t.length<25||t.length>430)continue;
    // Example: "63,90 грн -22% 49 90 грн".
    const m=t.replace(/\s+/g,' ').match(/(\d{1,5}[.,]\d{2})\s*грн\s*[-−]\s*(\d{1,2})\s*%\s*(\d{1,5})\s+(\d{2})\s*грн/i);
    if(m){match=m;raw=t;break}
   }
   if(!match)continue;
   const old=Number(match[1].replace(',','.'));
   const price=Number(match[3]+'.'+match[4]),badge=Number(match[2]);
   if(!(old>price&&price>0&&badge>0&&Math.abs(100*(old-price)/old-badge)<=1.2))continue;
   const lines=raw.split(/\n/).map(x=>x.trim()).filter(Boolean);
   const name=lines.find(x=>x.length>=7&&!/^(?:\d|купити|в наявності|акція|[-−])/i.test(x))||'';
   if(name.length<7||name.length>190)continue;
   seen.add(u.pathname);
   out.push({name,priceText:old.toFixed(2)+' грн -'+badge+'% '+price.toFixed(2)+' грн',oldPrice:old,price,discount:badge,url:u.href});
  }
  return out;
 }""")

async def official_novus(page):
 """Extract official NOVUS sale prices from isolated product cards on novus.ua.

 Do not use Zakaz checkout links as product identifiers or combine neighboring
 cards' prices. Require a genuine official product URL and one old/new pair.
 """
 return await page.evaluate(r"""() => {
  const result=[],seen=new Set();
  const numberRx=/(?<![\d.,])\d{1,5}[.,]\d{2}(?![\d.,])/g;
  const detailsUrl=(a)=>{
    try {
      const u=new URL(a.href);
      if(u.hostname!=='novus.ua'||!u.pathname.endsWith('.html'))return null;
      if(/^\/(sales|catalog|catalogsearch|search|category)\//.test(u.pathname))return null;
      return u;
    } catch {return null}
  };
  const normalizeText=(s)=>(s||'').replace(/\s+/g,' ').trim();
  const amounts=(s)=>[...normalizeText(s).matchAll(numberRx)].map(m=>Number(m[0].replace(',','.')));
  const anchors=[...document.querySelectorAll('a[href]')].filter(a=>detailsUrl(a));
  for(const a of anchors){
    const u=detailsUrl(a);
    if(!u||seen.has(u.pathname))continue;
    let card=a;
    let picked=null;
    for(let depth=0;depth<9&&card;depth++,card=card.parentElement){
      // Match one independent product, not a carousel or a section of products.
      const productUrls=[...card.querySelectorAll('a[href]')]
        .map(x=>detailsUrl(x)?.pathname).filter(Boolean);
      if(new Set(productUrls).size>1)break;
      const raw=normalizeText(card.innerText);
      if(raw.length<20||raw.length>650)continue;
      const pctMatch=raw.match(/[-−]\s*(\d{1,2})\s*%/);
      const dateMatch=raw.match(/з\s*(\d{1,2})\s*[.]\s*(\d{1,2})\s*по\s*(\d{1,2})\s*[.]\s*(\d{1,2})/i);
      // Dates like "29.10" and "11.11" must not be interpreted as prices.
      const withoutPeriods=raw.replace(/з\s*\d{1,2}\s*[.]\s*\d{1,2}\s*по\s*\d{1,2}\s*[.]\s*\d{1,2}/gi,' ');
      const pairs=amounts(withoutPeriods);
      let old=null,price=null;
      // Prefer explicit Magento product price nodes when present.
      const oldEl=card.querySelector('.old-price .price,[data-price-type="oldPrice"] .price');
      const newEl=card.querySelector('.special-price .price,[data-price-type="finalPrice"] .price');
      const oldAmount=amounts(oldEl?.textContent||'');
      const newAmount=amounts(newEl?.textContent||'');
      if(oldAmount.length===1&&newAmount.length===1){
        old=oldAmount[0];price=newAmount[0];
      } else if(pairs.length===2){
        old=pairs[0];price=pairs[1];
      } else continue;
      if(!(Number.isFinite(old)&&Number.isFinite(price)&&old>price&&price>0))continue;
      if(pctMatch&&Math.abs(Number(pctMatch[1])-100*(old-price)/old)>2)continue;
      const nameEl=card.querySelector('a.product-item-link,[class*="product-item-name"] a,[class*="product-name"] a');
      const name=normalizeText(nameEl?.textContent||a.getAttribute('title')||
         a.textContent?.trim()||a.querySelector('img[alt]')?.alt||
         card.querySelector('img[alt]')?.alt);
      if(name.length<7||name.length>180)continue;
      picked={name,url:u.href,oldPrice:old,price,
        discount:pctMatch?Number(pctMatch[1]):null,
        validToDay:dateMatch?Number(dateMatch[3]):null,
        validToMonth:dateMatch?Number(dateMatch[4]):null};
      break;
    }
    if(!picked)continue;
    seen.add(u.pathname);
    result.push(picked);
  }
  return result;
 }""")

async def scrape(page,store,url):
 await page.goto(url,wait_until="domcontentloaded",timeout=45000)
 if store=="fora":
  # Fora hydrates offer cards after the initial DOM has loaded.
  # Never interpret an unhydrated navigation-only page as an empty catalog.
  try:
   await page.locator('a[href*="/product/"]').first.wait_for(state="attached",timeout=30000)
   await page.wait_for_timeout(1200)
  except Exception:
   pass
 else:
  try:await page.wait_for_timeout(2500)
  except Exception:pass
 if store=="fora":
  # Fora's own expanded catalog URL uses from=1&to=N.
  # A single expanded load avoids rescanning earlier cards on every page.
  gathered={}
  for target in (36,):
   try:
    await page.goto(url+"?to="+str(target)+"&from=1",wait_until="domcontentloaded",timeout=45000)
    await page.locator('a[href*="/product/"]').first.wait_for(state="attached",timeout=25000)
    await page.wait_for_timeout(1500)
   except Exception as exc:
    print("Fora expanded catalog unavailable:",str(exc)[:160],flush=True)
    continue
   rows=await fora_cards(page)
   for row in rows:
    item=normalize(store,url,row)
    if item:gathered[item["id"]]=item
   print("Fora expanded catalog",target,"verified",len(gathered),flush=True)
  if gathered:return list(gathered.values())
  # If expanded catalog fails, still retain the first verified page.
  rows=await fora_cards(page)
  return [item for row in rows if (item:=normalize(store,url,row))]

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
   rows = await fora_cards(page)
  if store in ('silpo','atb'):
   rows += await targeted_cards(page,store)
  if store=='novus_official':
   rows = await official_novus(page)
  before=len(gathered)
  for row in rows:
   item=normalize(store,url,row)
   if item:gathered[item["id"]]=item
  empty=empty+1 if len(gathered)==before else 0
  if store=='fora':break  # Fora's page already contains the full list; avoid 35 expensive DOM scans.
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
