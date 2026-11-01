#!/usr/bin/env python3
"""Experimental public catalog collector. Fail closed: no invented prices."""
import json, os, re, datetime, urllib.request, urllib.error, html
from html.parser import HTMLParser
from pathlib import Path
from decimal import Decimal, InvalidOperation

SOURCES = {
 "silpo": ("https://silpo.ua/offers/city/kiyiv", "kyiv"),
 "metro": ("https://www.metro.ua/propositions", "kyiv"),
 "fora": ("https://fora.ua/all-offers", "kyiv"),
 "atb": ("https://www.atbmarket.com/promo/economy", "kyiv"),
 "novus": ("https://novus.online/", "kyiv"),
}
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data"
HEADERS = {"User-Agent":"Mozilla/5.0 (compatible; KoshykTsinBot/0.1; public-price-monitor)", "Accept":"text/html,application/xhtml+xml", "Accept-Language":"uk-UA,uk;q=0.9"}
MAX_BYTES = 4_000_000

class JSONLD(HTMLParser):
 def __init__(self):
  super().__init__(); self.active=False; self.buf=[]; self.items=[]
 def handle_starttag(self,tag,attrs):
  if tag=="script" and dict(attrs).get("type","").lower()=="application/ld+json":
   self.active=True;self.buf=[]
 def handle_data(self,data):
  if self.active:self.buf.append(data)
 def handle_endtag(self,tag):
  if tag=="script" and self.active:
   try:self.items.append(json.loads("".join(self.buf)))
   except (ValueError,TypeError):pass
   self.active=False

def product_nodes(root):
 if isinstance(root,list):
  for o in root:yield from product_nodes(o)
 elif isinstance(root,dict):
  typ=root.get("@type",[])
  if isinstance(typ,str):typ=[typ]
  if any(str(t).lower().endswith("product") for t in typ):yield root
  for key in ("@graph","itemListElement","item","mainEntity"):
   if key in root:yield from product_nodes(root[key])

def price(value):
 try:
  x=Decimal(str(value).replace(" ","").replace(",","."))
  return float(x) if x>0 and x<1000000 else None
 except (InvalidOperation,ValueError):return None

def collect(store,url,region):
 request=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(request,timeout=30) as response:
  raw=response.read(MAX_BYTES+1)
  if len(raw)>MAX_BYTES:raise ValueError("page too large")
  body=raw.decode("utf-8","replace")
 doc=JSONLD();doc.feed(body)
 rows=[]
 for p in product_nodes(doc.items):
  name=html.unescape(re.sub("<[^>]+>","",str(p.get("name","")))).strip()
  offer=p.get("offers",{})
  if isinstance(offer,list):offer=next((x for x in offer if isinstance(x,dict)),{})
  if not isinstance(offer,dict):continue
  value=price(offer.get("price"))
  currency=offer.get("priceCurrency","UAH")
  if not name or len(name)<5 or not value or currency!="UAH":continue
  link=p.get("url") or offer.get("url") or url
  if not isinstance(link,str) or not link.startswith(("https://","http://")):link=url
  identifier=str(p.get("sku") or p.get("gtin13") or p.get("productID") or name)
  import hashlib
  pid=store+"-"+hashlib.sha256(identifier.encode()).hexdigest()[:14]
  rows.append({"id":pid,"name":name,"store":store,"price":value,"url":link,"locationKey":region,"location":"Київ — онлайн-каталог; конкретний магазин не підтверджено","date":datetime.date.today().isoformat(),"category":"Інше","pack":"","sourceType":"jsonld"})
 return list({x["id"]:x for x in rows}.values())

def main():
 OUT.mkdir(exist_ok=True)
 result=[]; statuses={};now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 previous=[]
 try:
  previous=json.loads((OUT/"offers.json").read_text(encoding="utf-8"))
 except (OSError,ValueError):pass
 def is_recent(o):
  try:
   checked=datetime.date.fromisoformat(o.get("date",""))
   expiry=datetime.date.fromisoformat(o["validTo"]) if o.get("validTo") else checked+datetime.timedelta(days=1)
   return checked<=datetime.date.today()<=expiry and (datetime.date.today()-checked).days<=2
  except (ValueError,TypeError,KeyError):return False
 for store,(url,region) in SOURCES.items():
  try:
   rows=collect(store,url,region)
   statuses[store]={"status":"ok" if rows else "no_supported_data","count":len(rows),"checkedAt":now,"url":url,"note":"Лише Product JSON-LD з ціною UAH; не підтверджує залишки чи ціни локальних магазинів"}
   result.extend(rows)
  except Exception as e:
   statuses[store]={"status":"error","count":0,"checkedAt":now,"url":url,"error":str(e)[:180]}
 # Keep only very recently checked offers after a provider failure.
 for store in SOURCES:
  if statuses[store]["count"]==0:
   recent=[o for o in previous if o.get("store")==store and is_recent(o)]
   if recent:
    result.extend(recent)
    statuses[store]["status"]="cached_recent"
    statuses[store]["count"]=len(recent)
    statuses[store]["note"]="Recently verified cache, not live data"

 (OUT/"offers.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (OUT/"status.json").write_text(json.dumps({"generatedAt":now,"total":len(result),"sources":statuses},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"total":len(result),"sources":{k:v["status"] for k,v in statuses.items()}},ensure_ascii=False))
if __name__=="__main__":main()
