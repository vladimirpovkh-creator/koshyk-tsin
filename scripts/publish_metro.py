#!/usr/bin/env python3
"""Publish only a verified METRO-only result; preserve every other store byte-for-byte."""
import datetime as dt
import json
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from categories import category_for
from audit_categories import audit as audit_categories

ROOT = Path(__file__).resolve().parents[1] / "data"
now = dt.datetime.now(dt.timezone.utc)
today = dt.datetime.now(ZoneInfo("Europe/Kyiv")).date().isoformat()

def read(path,default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default

def valid(row):
    if not isinstance(row,dict) or row.get("store")!="metro":
        return False
    if row.get("priceVerified") is not True:
        return False
    if not isinstance(row.get("price"),(int,float)) or not 0 < row["price"] < 100000:
        return False
    if not isinstance(row.get("name"),str) or not 12 <= len(row["name"]) <= 190:
        return False
    if row.get("date")!=today:
        return False
    source=row.get("sourceType")
    host=urlparse(row.get("url","")).hostname
    if source=="metro-official-pdf-catalog":
        return (host=="promotions.metro.ua" and row.get("conditionsVerified") is False
                and row.get("validTo","")>=today
                and row.get("priceUnit") in ("кг","шт","уп"))
    if source=="metro-official-public-promotions":
        return (host in ("metro.ua","www.metro.ua") and
                isinstance(row.get("oldPrice"),(int,float))
                and row["oldPrice"]>row["price"])
    return False

status=read(ROOT/"stores"/"metro-status.json",{})
rows=read(ROOT/"stores"/"metro.json",[])
if status.get("status") not in ("ok","partial_verified") or not isinstance(rows,list):
    print("METRO-only: no successful verified result, publication skipped")
    raise SystemExit(0)
if len(rows)<3 or any(not valid(r) for r in rows):
    print("METRO-only: rejected incomplete or unverified input; publication skipped")
    raise SystemExit(0)
ids=[x.get("id") for x in rows]
if len(set(ids))!=len(ids):
    print("METRO-only: duplicate offer IDs, publication skipped")
    raise SystemExit(0)

prior=read(ROOT/"offers.json",[])
meta=read(ROOT/"status.json",{})
if not isinstance(prior,list) or not isinstance(meta,dict) or not isinstance(meta.get("sources"),dict):
    raise RuntimeError("Cannot preserve existing store catalog: missing or invalid combined data")
unchanged=[x for x in prior if isinstance(x,dict) and x.get("store")!="metro"]
merged=unchanged+[{**x,"category":category_for(x["name"])} for x in rows]
meta["generatedAt"]=now.isoformat()
meta["total"]=len(merged)
meta["sources"]["metro"]={**status,"count":len(rows)}
(ROOT/"offers.json").write_text(json.dumps(merged,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(ROOT/"status.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
report={"generatedAt":now.isoformat(),**audit_categories(merged,sample_limit=10)}
(ROOT/"category_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("METRO-only: published",len(rows),"verified offers; preserved",len(unchanged),"other-store offers")
