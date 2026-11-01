#!/usr/bin/env python3
"""Best-effort published catalog prices. Do not label a failed fetch as a live price."""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"
SOURCES={
 "novus":[("Хліб","https://novus.zakaz.ua/uk/categories/bread/"),("Молоко","https://novus.zakaz.ua/uk/categories/uht-milk/"),("Молоко","https://novus.zakaz.ua/uk/categories/pasteurized-milk/"),("Масло","https://novus.zakaz.ua/uk/categories/butter/")],
 "metro":[("Хліб","https://metro.zakaz.ua/uk/categories/bread-metro/"),("Молоко","https://metro.zakaz.ua/uk/categories/milk-metro/")],
 "atb":[("Молоко","https://www.atbmarket.com/catalog/398-moloko")],
 "fora":[("Акції","https://fora.ua/all-offers")],
 "silpo":[("Акції","https://silpo.ua/offers/city/kiyiv")],
}
AGENT="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
UAH=r"(?:\d{1,4}(?:[\s\u00a0]?\d{3})*[.,]\d{2}|\d{1,4})"
def fetch(url):
 req=urllib.request.Request(url,headers={"User-Agent":AGENT,"Accept-Language":"uk-UA,uk;q=0.9","Accept":"text/html,application/xhtml+xml"})
 with urllib.request.urlopen(req,timeout=25) as resp:
  if resp.status!=200:raise ValueError(f"HTTP {resp.status}")
  raw=resp.read(5_000_001)
  if len(raw)>5_000_000:raise ValueError("Page exceeds 5MB")
  return BeautifulSoup(raw,"html.parser")

def make(store,category,url,name,price,old=None):
 name=re.sub(r"\s+"," ",name).strip(" +–-")
 if not 6<=len(name)<=180 or not any(c.isalpha() for c in name):return None
 if not 0.1<=price<=20000:return None
 key=hashlib.sha256((store+"|"+name.casefold()).encode()).hexdigest()[:16]
 item={"id":store+"-"+key,"name":name,"store":store,"price":price,"category":category,"date":dt.date.today().isoformat(),"url":url,"locationKey":"kyiv","location":"Онлайн-каталог; конкретний магазин не підтверджено","sourceType":"catalog-scan"}
 if old and price<old<price*5:item["oldPrice"]=old
 return item

def price_number(s):
 try:return float(s.replace("\u00a0","").replace(" ","").replace(",","."))
 except ValueError:return None

def scan_novus(soup,url,category):
 # Zakaz pages publish inline catalog item text, sometimes without JSON-LD.
 lines=[re.sub(r"\s+"," ",s).strip() for s in soup.stripped_strings]
 results=[]
 # Store text commonly includes "+46.99 ₴Молоко ..." in a single text node.
 for i,line in enumerate(lines):
  m=re.search(r"(?:^|\s)(\d{1,4}[.,]\d{2})\s*₴\s*(.{8,160})",line)
  if m:
   p=price_number(m.group(1)); name=m.group(2)
   name=re.sub(r"^\+?[-\d %₴.,]+","",name).strip()
   name=re.split(r"\s+(?:Додати|Купити|В кошик|Немає в наявності)",name)[0]
   item=make("novus",category,url,name,p) if p is not None else None
   if item:results.append(item)
 # Text listing: +42.79 ₴Хліб Кулиничі ... 400г
 full=re.sub(r"\\s+"," ",soup.get_text(" ",strip=True))
 keyword={"Хліб":r"(?:Хліб|Хлiб|Батон|Багет)","Молоко":r"(?:Молоко|Молочний)","Масло":r"(?:Масло)"}.get(category,r"(?:Хліб|Молоко|Масло)")
 pattern=r"\\+?(\\d{1,4}[.,]\\d{2})\\s*₴\\s*("+keyword+r"[^₴+]{8,120}?(?:\\d{2,4}\\s*г|\\d[.,]?\\d*\\s*л))"
 for m in re.finditer(pattern,full,re.I):
  p=price_number(m.group(1))
  if p:
   item=make("novus" if "novus." in url else "metro",category,url,m.group(2),p)
   if item:results.append(item)
 # Fallback: price and product are neighboring tokens (often name follows).
 for i,line in enumerate(lines[:-1]):
  m=re.fullmatch(r"\+?("+UAH+r")\s*₴",line)
  if not m:continue
  p=price_number(m.group(1))
  candidates=[x for x in lines[i+1:i+4] if (category.lower() in x.lower() or "молоко" in x.lower() or "масло" in x.lower()) and len(x)>9]
  if candidates and p:
   item=make("novus",category,url,candidates[0],p)
   if item:results.append(item)
 return results

def scan_atb(soup,url,category):
 lines=[re.sub(r"\s+"," ",s).strip() for s in soup.stripped_strings]
 results=[]
 # ATB: product title then price '51.90 грн/шт'.
 for i,line in enumerate(lines):
  m=re.search(r"("+UAH+r")\s*грн\s*/\s*шт",line,re.I)
  if not m:continue
  p=price_number(m.group(1))
  if p is None:continue
  prior=lines[max(0,i-9):i]
  names=[x for x in reversed(prior) if (x.lower().startswith("молоко ") or x.lower().startswith("напій ") or "молоко" in x.lower()) and 10<len(x)<180 and "грн" not in x.lower()]
  if names:
   item=make("atb",category,url,names[0],p)
   if item:results.append(item)
 return results

def collect(store,category,url):
 soup=fetch(url)
 items=scan_novus(soup,url,category) if store in ("novus","metro") else scan_atb(soup,url,category) if store=="atb" else []
 # Only collect explicitly parsed product-price pairs; no generic guessing.
 return items

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 today=dt.date.today()
 now=dt.datetime.now(dt.timezone.utc).isoformat()
 previous=[]
 try:previous=json.loads((OUT/"offers.json").read_text(encoding="utf-8"))
 except (OSError,ValueError):pass
 all_items={}
 statuses={}
 for store,pages in SOURCES.items():
  fresh=[]; errors=[]
  for category,url in pages:
   try:
    found=collect(store,category,url)
    fresh+=found
    if not found:errors.append("Немає розпізнаних товарів: "+url)
   except Exception as exc:errors.append(str(exc)[:160]+": "+url)
  if fresh:
   for item in fresh:all_items[item["id"]]=item
   state="ok"
  else:
   # Only show cached offers within 48 hours of their last independent verification.
   recent=[]
   for o in previous:
    if o.get("store")!=store:continue
    try:
     checked=dt.date.fromisoformat(o["date"])
     expiry=dt.date.fromisoformat(o["validTo"]) if o.get("validTo") else checked+dt.timedelta(days=2)
     if checked<=today<=expiry and (today-checked).days<=2:recent.append(o)
    except (ValueError,KeyError,TypeError):pass
   for item in recent:all_items[item["id"]]=item
   state="cached_recent" if recent else "error"
  statuses[store]={"status":state,"count":sum(1 for x in all_items.values() if x["store"]==store),"checkedAt":now,"errors":errors[:4]}
 result=sorted(all_items.values(),key=lambda o:(o["store"],o["name"]))
 (OUT/"offers.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (OUT/"status.json").write_text(json.dumps({"generatedAt":now,"total":len(result),"sources":statuses},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"total":len(result),"statuses":statuses},ensure_ascii=False))
 if not any(s["status"]=="ok" for s in statuses.values()):
  print("WARNING: No new published prices parsed; check source errors.")
if __name__=="__main__":main()
