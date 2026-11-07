#!/usr/bin/env python3
"""Merge independent retailer catalogs without losing valid cached offers."""
import json
import math
import datetime as dt
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from categories import category_for
from audit_categories import audit as audit_categories

root=Path(__file__).resolve().parents[1]/"data"
stores=("metro","novus","novus_official","fora","silpo","atb")
now=dt.datetime.now(dt.timezone.utc)
today=now.date().isoformat()

def read_json(path,default=None):
 try:return json.loads(path.read_text(encoding="utf-8"))
 except (OSError,ValueError):return default

def valid(row,source):
 if not isinstance(row,dict):return False
 expected="novus" if source=="novus_official" else source
 if row.get("store")!=expected:return False
 if not isinstance(row.get("name"),str) or len(row["name"])<6:return False
 if (not isinstance(row.get("price"),(int,float)) or isinstance(row["price"],bool)
     or not math.isfinite(row["price"]) or row["price"]<=0):return False
 if row.get("validTo") and row["validTo"]<today:return False
 if source in ("novus","novus_official"):
  # A promotional listing without a confirmed expiry cannot stay fresh forever.
  try: checked=dt.date.fromisoformat(row["date"])
  except (KeyError,TypeError,ValueError):return False
  age=(dt.datetime.now(ZoneInfo("Europe/Kyiv")).date()-checked).days
  if not 0<=age<=1:return False
 if source=="metro":
  # Only official METRO.ua data may appear, even when a scrape fails.
  # Never resurrect cached Metro Zakaz.ua offers from the old collector.
  if row.get("sourceType") not in ("metro-official-public-promotions","metro-official-pdf-catalog","metro-official-shop-public-promo"):return False
  if row.get("priceVerified") is not True:return False
  if urlparse(row.get("url","")).hostname not in ("www.metro.ua","metro.ua","promotions.metro.ua","shop.metro.ua"):return False
  if row.get("sourceType")=="metro-official-shop-public-promo":
   if urlparse(row.get("url","")).hostname!="shop.metro.ua":return False
   if row.get("conditionsVerified") is not False or row.get("locationKey")!="kyiv":return False
   if row.get("date")!=dt.datetime.now(ZoneInfo("Europe/Kyiv")).date().isoformat():return False
   if not isinstance(row.get("oldPrice"),(int,float)) or row["oldPrice"]<=row["price"]:return False
  if row.get("sourceType")=="metro-official-pdf-catalog":
   if not row.get("validTo") or row["validTo"]<dt.datetime.now(ZoneInfo("Europe/Kyiv")).date().isoformat():return False
   if row.get("conditionsVerified") is not False:return False
  elif not isinstance(row.get("oldPrice"),(int,float)) or not row["oldPrice"]>row["price"]:return False
  try:
   checked=dt.date.fromisoformat(row["date"])
  except (KeyError,TypeError,ValueError):return False
  if (dt.datetime.now(ZoneInfo("Europe/Kyiv")).date()-checked).days>1:return False
 if source=="silpo":
  # Product price depends on the selected store. Do not carry a failed
  # daily app check into following dates as though its price were current.
  if row.get("sourceType")!="live-promo-app" or row.get("priceVerified") is not True:return False
  if row.get("date")!=dt.datetime.now(ZoneInfo("Europe/Kyiv")).date().isoformat():return False
  if not isinstance(row.get("oldPrice"),(int,float)) or row["oldPrice"]<=row["price"]:return False
  if urlparse(row.get("url","")).hostname!="silpo.ua":return False
 if source=="atb":
  if row.get("sourceType")!="atb-public-economy" or row.get("priceVerified") is not True:return False
  if row.get("date")!=dt.datetime.now(ZoneInfo("Europe/Kyiv")).date().isoformat():return False
  if row.get("conditionsVerified") is not False:return False
  if not isinstance(row.get("oldPrice"),(int,float)) or not row["oldPrice"]>row["price"]:return False
  if urlparse(row.get("url","")).hostname!="www.atbmarket.com":return False
  if not row.get("validTo") or row["validTo"]<dt.datetime.now(ZoneInfo("Europe/Kyiv")).date().isoformat():return False
 if source=="fora":
  if row.get("priceVerified") is not True:return False
  # Fora does not publish an expiry date in our extracted cards. Do not
  # retain yesterday's offers indefinitely after a failed collection.
  try:
   checked=dt.date.fromisoformat(row["date"])
  except (KeyError,TypeError,ValueError):return False
  if (dt.datetime.now(ZoneInfo("Europe/Kyiv")).date()-checked).days>1:return False
 if source=="novus_official":
  if row.get("channel")!="official" or urlparse(row.get("url","")).hostname!="novus.ua":return False
  if not isinstance(row.get("oldPrice"),(int,float)) or row["oldPrice"]<=row["price"]:return False
 return True

prior=read_json(root/"offers.json",[])
prior=[x for x in prior if isinstance(x,dict)] if isinstance(prior,list) else []
merged=[];statuses={};used=set()
for store in stores:
 source=root/"stores"/(store+".json")
 statusfile=root/"stores"/(store+"-status.json")
 current_status=read_json(statusfile,{}) or {}
 rows=read_json(source,None)
 selected=[]
 if isinstance(rows,list) and current_status.get("status") in ("ok","partial_verified"):
  selected=[x for x in rows if valid(x,store)]
 # When the latest scrape failed, retain only previously VALIDATED offers.
 # Never present cached offers as freshly checked.
 if not selected:
  selected=[x for x in prior if valid(x,store) and (x.get("channel")=="official")== (store=="novus_official") ] if store in ("novus","novus_official") else [x for x in prior if valid(x,store)]
  if selected:
   statuses[store]={**current_status,"status":"cached_previous","count":len(selected),"error":current_status.get("error",""),"lastCheckedAt":current_status.get("checkedAt"),"warning":"Last verified catalog retained; prices not freshly checked"}
  else:
   statuses[store]={**current_status,"count":0,"status":current_status.get("status","no_data")}
 else:
  statuses[store]={**current_status,"count":len(selected),"status":current_status.get("status","ok")}
 for item in selected:
  if item["id"] in used:continue
  used.add(item["id"])
  merged.append({**item,"category":category_for(item["name"])})
(root/"offers.json").write_text(json.dumps(merged,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(root/"status.json").write_text(json.dumps({"generatedAt":now.isoformat(),"total":len(merged),"sources":statuses},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(root/"category_audit.json").write_text(json.dumps({"generatedAt":now.isoformat(), **audit_categories(merged, sample_limit=10)},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("Merged",len(merged),[(s,statuses[s]["status"],statuses[s]["count"]) for s in stores])
