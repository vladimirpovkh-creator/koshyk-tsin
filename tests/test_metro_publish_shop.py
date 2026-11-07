#!/usr/bin/env python3
"""Isolated publisher integration: official shop promotions must not alter other stores."""
import datetime as dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
TODAY=dt.datetime.now(ZoneInfo("Europe/Kyiv")).date().isoformat()
scripts=["publish_metro.py","categories.py","audit_categories.py"]

with tempfile.TemporaryDirectory() as d:
    testroot=Path(d)
    (testroot/"scripts").mkdir()
    (testroot/"data"/"stores").mkdir(parents=True)
    for name in scripts:
        (testroot/"scripts"/name).write_text(
            (ROOT/"scripts"/name).read_text(encoding="utf-8"),encoding="utf-8")
    (testroot/"data"/"category_rules.json").write_text(
        (ROOT/"data"/"category_rules.json").read_text(encoding="utf-8"),encoding="utf-8")
    def put(path,obj):
        path.write_text(json.dumps(obj,ensure_ascii=False),encoding="utf-8")
    other={"id":"novus-preserved","store":"novus","name":"Тестове молоко 1 л",
           "price":30,"oldPrice":39,"date":TODAY}
    put(testroot/"data"/"offers.json",[other])
    put(testroot/"data"/"status.json",{"generatedAt":"fixture","total":1,
                                     "sources":{"novus":{"status":"ok","count":1}}})
    offers=[]
    for idx in range(3):
        offers.append({
            "id":f"metro-test-{idx}",
            "store":"metro",
            "name":f"Товар тестовий METRO {idx} 250г",
            "price":50+idx,
            "oldPrice":80+idx,
            "date":TODAY,
            "url":"https://shop.metro.ua/",
            "sourceType":"metro-official-shop-public-promo",
            "priceVerified":True,"conditionsVerified":False,
            "locationKey":"kyiv",
        })
    put(testroot/"data"/"stores"/"metro.json",offers)
    put(testroot/"data"/"stores"/"metro-status.json",{
        "store":"metro","status":"partial_verified","count":3,"checkedAt":TODAY})
    def run():
        subprocess.run([sys.executable,str(testroot/"scripts"/"publish_metro.py")],
                       check=True,capture_output=True,text=True)
        return json.loads((testroot/"data"/"offers.json").read_text(encoding="utf-8"))
    got=run()
    assert len(got)==4,got
    assert got[0]==other,got[0]
    assert len([x for x in got if x["store"]=="metro"])==3
    meta=json.loads((testroot/"data"/"status.json").read_text(encoding="utf-8"))
    assert meta["total"]==4 and meta["sources"]["novus"]["count"]==1,meta
    # One invalid wholesale-origin item rejects the entire unsafe METRO batch.
    offers[0]["url"]="https://not-metro.example/"
    put(testroot/"data"/"stores"/"metro.json",offers)
    again=run()
    assert again==got,"Publisher accepted an untrusted shop domain"
    print("PASS: verified shop offers published; other stores preserved; invalid batch rejected")
