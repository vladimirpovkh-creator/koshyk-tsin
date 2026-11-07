#!/usr/bin/env python3
"""Isolated integration test: no production data is modified."""
import json, subprocess, sys, tempfile, datetime as dt
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TODAY=dt.datetime.now(ZoneInfo("Europe/Kyiv")).date().isoformat()
MERGER=ROOT/"scripts"/"merge_stores.py"
CATEGORIES=ROOT/"scripts"/"categories.py"
CATEGORY_AUDIT=ROOT/"scripts"/"audit_categories.py"
CATEGORY_RULES=ROOT/"data"/"category_rules.json"

def record(sku, price=20):
 return {"id":"novus-"+sku,"store":"novus","channel":"online","name":"Молоко тестове "+sku,"price":price,"oldPrice":30,"date":TODAY,"url":"https://novus.zakaz.ua/uk/products/test-"+sku+"/"}

with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp)
 (root/"scripts").mkdir()
 (root/"data"/"stores").mkdir(parents=True)
 (root/"data"/"category_rules.json").write_text(CATEGORY_RULES.read_text(encoding="utf-8"),encoding="utf-8")
 (root/"scripts"/"merge_stores.py").write_text(MERGER.read_text(encoding="utf-8"),encoding="utf-8")
 (root/"scripts"/"categories.py").write_text(CATEGORIES.read_text(encoding="utf-8"),encoding="utf-8")
 (root/"scripts"/"audit_categories.py").write_text(CATEGORY_AUDIT.read_text(encoding="utf-8"),encoding="utf-8")
 def write(path,obj):
  path.write_text(json.dumps(obj,ensure_ascii=False),encoding="utf-8")
 def run():
  subprocess.run([sys.executable,str(root/"scripts"/"merge_stores.py")],check=True,capture_output=True,text=True)
  return json.loads((root/"data"/"offers.json").read_text()),json.loads((root/"data"/"status.json").read_text())
 items=[record(str(i)) for i in range(659)]
 store=root/"data"/"stores"
 write(store/"novus.json",items)
 write(store/"novus-status.json",{"store":"novus","status":"ok","count":659,"checkedAt":TODAY+"T20:00:00Z"})
 got,status=run()
 assert len(got)==659 and status["sources"]["novus"]["status"]=="ok",("initial",len(got),status)
 # Simulate failed scraping with an empty file, leaving previous merged output as cache.
 write(store/"novus.json",[])
 write(store/"novus-status.json",{"store":"novus","status":"error","count":0,"checkedAt":TODAY+"T21:00:00Z","error":"simulated outage"})
 got,status=run()
 assert len(got)==659,("lost items on failure",len(got))
 assert status["sources"]["novus"]["status"]=="cached_previous",status
 assert len({x["id"] for x in got})==659
 # New valid catalog must replace cache, not append.
 write(store/"novus.json",[record("new",25)])
 write(store/"novus-status.json",{"store":"novus","status":"ok","count":1,"checkedAt":TODAY+"T22:00:00Z"})
 got,status=run()
 assert len(got)==1 and got[0]["id"]=="novus-new",("fresh result",got)
 assert status["sources"]["novus"]["status"]=="ok",status
 # Expired NOVUS data must not remain in the basket after an outage.
 old=(dt.datetime.now(ZoneInfo("Europe/Kyiv")).date()-dt.timedelta(days=4)).isoformat()
 write(store/"novus.json",[])
 write(store/"novus-status.json",{"store":"novus","status":"error","count":0,"checkedAt":TODAY+"T23:00:00Z"})
 write(root/"data"/"offers.json",[{**record("stale"),"date":old}])
 got,status=run()
 assert not got and status["sources"]["novus"]["count"]==0,(got,status)
 print("PASS: recent cache retained; stale NOVUS data expired; fresh catalog replaces cache.")
