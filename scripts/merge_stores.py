#!/usr/bin/env python3
"""Merge five independent retailer artifacts without misrepresenting missing sources."""
import json,datetime as dt
from categories import category_for
from pathlib import Path
root=Path(__file__).resolve().parents[1]/"data"
stores=("metro","novus","novus_official","fora","silpo","atb")
offers=[];statuses={}
def read_offers(path):
 raw=path.read_text(encoding="utf-8")
 try:
  return json.loads(raw),False
 except json.JSONDecodeError:
  parsed,end=json.JSONDecoder().raw_decode(raw.lstrip())
  if not isinstance(parsed,list):raise ValueError("Invalid retailer file")
  return parsed,True

for store in stores:
 file=root/"stores"/(store+".json"); status=root/"stores"/(store+"-status.json")
 try:
  rows,recovered=read_offers(file);s=json.loads(status.read_text())
  if not isinstance(rows,list):raise ValueError("Invalid items array")
  clean=[r for r in rows if r.get("store")==("novus" if store=="novus_official" else store) and isinstance(r.get("price"),(int,float)) and r.get("price",0)>0 and r.get("name")]
  for item in clean:
   item['category']=category_for(item['name'])
  offers.extend(clean);statuses[store]=s
  if recovered:statuses[store]["warning"]="Recovered first JSON array; trailing data ignored"
 except (OSError,ValueError,TypeError) as e:statuses[store]={"status":"error","count":0,"error":str(e)}
now=dt.datetime.now(dt.timezone.utc).isoformat()
(root/"offers.json").write_text(json.dumps(offers,ensure_ascii=False,indent=2)+"\n")
(root/"status.json").write_text(json.dumps({"generatedAt":now,"total":len(offers),"sources":statuses},ensure_ascii=False,indent=2)+"\n")
print("Merged",len(offers),"offers",[(k,v.get("count",0)) for k,v in statuses.items()])
