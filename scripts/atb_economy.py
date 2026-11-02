#!/usr/bin/env python3
"""Read-only ATB Economy public-page offer extraction.

The ATB website may block automated visitors: in that case report error and
publish no products. No credentials, captcha handling or session replay.
Extract prices only from the same product tile, with discount and expiry QA.
"""
import datetime as dt
import hashlib
import math
import re
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

SOURCE="https://www.atbmarket.com/catalog/economy"
KYIV=ZoneInfo("Europe/Kyiv")
DATE=re.compile(r"\bдо\s*(\d{1,2})[.](\d{1,2})\b",re.I)
BADGE=re.compile(r"[-−]\s*(\d{1,2})\s*%")
EXCLUDE=re.compile(r"(?:сигарет|тютюн|вейп|електронн.*сигарет)",re.I)

def normalize_atb(row,today=None):
    if not isinstance(row,dict):return None
    now=today or dt.datetime.now(KYIV).date()
    name=row.get("name")
    url=row.get("url")
    if not isinstance(name,str) or not 7<=len(name.strip())<=190:return None
    if EXCLUDE.search(name):return None
    if not isinstance(url,str):return None
    u=urlparse(url)
    if u.scheme!="https" or u.hostname!="www.atbmarket.com" or not u.path.startswith("/product/"):return None
    old=row.get("oldPrice")
    price=row.get("price")
    badge=row.get("discount")
    if (any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x)
            for x in (old,price,badge))):return None
    if not .1<=price<old<=100000 or not 1<=badge<100:return None
    if abs(100*(old-price)/old-badge)>2.1:return None
    expiry=row.get("expires")
    if not isinstance(expiry,str):return None
    match=DATE.search(expiry)
    if not match:return None
    try:
        end=dt.date(now.year,int(match[2]),int(match[1]))
        if end<now-dt.timedelta(days=30):end=end.replace(year=now.year+1)
    except ValueError:return None
    if not now<=end<=now+dt.timedelta(days=35):return None
    pack=row.get("pack")
    if pack not in ("шт","кг"):return None
    key="atb-"+hashlib.sha256((u.path+"|"+name.strip()).encode()).hexdigest()[:18]
    return {"id":key,"name":name.strip(),"store":"atb",
            "price":round(float(price),2),"oldPrice":round(float(old),2),
            "pack":"1 "+pack,"category":"Акційні товари",
            "date":now.isoformat(),"validTo":end.isoformat(),"url":url,
            "locationKey":"kyiv",
            "location":"Публічні акції АТБ; магазин/наявність уточнюйте",
            "sourceType":"atb-public-economy",
            "sourceLabel":"АТБ — Економія (офіційний каталог)",
            "priceVerified":True,"conditionsVerified":False}

async def extract_page(page):
    return await page.evaluate(r"""() => {
      const out=[],seen=new Set();
      for(const link of document.querySelectorAll('a[href*="/product/"]')){
        let u;try{u=new URL(link.href)}catch{continue}
        if(u.hostname!=='www.atbmarket.com'||!u.pathname.startsWith('/product/'))continue;
        if(seen.has(u.pathname))continue;
        const name=(link.getAttribute('title')||link.innerText||
          link.querySelector('img[alt]')?.alt||'').replace(/\s+/g,' ').trim();
        if(name.length<7||name.length>190)continue;
        let node=link,parent=null;
        for(let i=0;i<6&&node;i++,node=node.parentElement){
          const raw=(node.innerText||'').replace(/\s+/g,' ').trim();
          if(raw.length<25||raw.length>750)continue;
          if(!/[-−]\s*\d{1,2}%/.test(raw)||!/\bдо\s*\d{1,2}\.\d{1,2}\b/i.test(raw))continue;
          const all=[...node.querySelectorAll('a[href*="/product/"]')];
          const paths=new Set(all.map(a=>{try{return new URL(a.href).pathname}catch{return null}}));
          if(paths.size>1)continue;
          parent=node;break;
        }
        if(!parent)continue;
        const raw=(parent.innerText||'').replace(/\s+/g,' ').trim();
        const discount=raw.match(/[-−]\s*(\d{1,2})\s*%/);
        const dates=raw.match(/\bдо\s*(\d{1,2})[.](\d{1,2})\b/i);
        // Example: 70.50 грн/шт 94.50 (old price has no currency suffix).
        // Use only first explicitly labelled pair in the same card.
        const money=raw.match(/(\d{1,5}[.,]\d{2})\s*грн\s*\/\s*(шт|кг)\s*(?:[₴\s]*)\s*(\d{1,5}[.,]\d{2})(?!\d)/i);
        if(!money||!discount||!dates)continue;
        const price=Number(money[1].replace(',','.'));
        const oldPrice=Number(money[3].replace(',','.'));
        if(!(oldPrice>price&&price>0))continue;
        if(Math.abs(100*(oldPrice-price)/oldPrice-Number(discount[1]))>2.1)continue;
        seen.add(u.pathname);
        out.push({name,url:u.href,price,oldPrice,discount:Number(discount[1]),
          pack:money[2].toLowerCase(),expires:dates[0]});
      }
      return out;
    }""")

async def collect_public_economy(page,max_pages=2):
    if not 1<=max_pages<=3:raise ValueError("ATB bounded request limit")
    await page.goto(SOURCE,wait_until="domcontentloaded",timeout=40000)
    await page.wait_for_timeout(1500)
    title=(await page.title()).lower()
    body=(await page.locator("body").inner_text(timeout=3000)).lower()
    if ("трохи зачекайте" in title or "cloudflare" in body
            or "перевірка безпеки" in body):
        raise RuntimeError("ATB Cloudflare challenge on public Economy catalogue")
    all_rows={}
    for page_num in range(max_pages):
        raw=await extract_page(page)
        for item in raw:
            normalized=normalize_atb(item)
            if normalized:all_rows[normalized["id"]]=normalized
        print("ATB public Economy page",page_num+1,"candidates",len(raw),
              "verified",len(all_rows),flush=True)
        if page_num+1>=max_pages:break
        # Use the site's own visible "show more" control once per page.
        more=page.get_by_text("Показати ще",exact=True)
        try:
            if not await more.count() or not await more.first.is_visible(timeout=1000):break
            await more.first.click(timeout=2500)
            await page.wait_for_timeout(1200)
        except Exception:break
    return list(all_rows.values())
