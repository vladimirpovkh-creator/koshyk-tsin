#!/usr/bin/env python3
"""Offline diagnostic tests: safe bounded anonymous Silpo API probes."""
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from silpo_app_probe import summarize_payload,_check,probe_catalog

summary=summarize_payload({"data":{"items":[{"displayPrice":32.9,"displayOldPrice":44.9,"title":"Молоко"}]}})
assert summary["candidateList"]=="data.items"
assert summary["candidateCount"]==1
assert summary["firstProductKeys"]==["displayPrice","displayOldPrice","title"]
assert summary["priceSamples"]==[{"title":"Молоко","displayPrice":32.9,"displayOldPrice":44.9}]

class FakeResponse:
 status=200
 headers={"Content-Type":"application/json; charset=utf-8"}
 def __enter__(self):return self
 def __exit__(self,*args):return False
 def read(self,size=-1):
  return json.dumps({"items":[{"displayPrice":50}]}).encode()

with patch("silpo_app_probe.request.urlopen",return_value=FakeResponse()) as mock:
 result=_check("https://silpo.example.com/api",{"method":"test"})
 assert result["reachable"] and result["candidateCount"]==1
 req=mock.call_args.args[0]
 assert req.get_method()=="POST"
 assert req.get_header("Authorization") is None
 assert req.get_header("Cookie") is None

with patch("silpo_app_probe.request.urlopen",side_effect=HTTPError("url",403,"Forbidden",{},io.BytesIO())):
 assert _check("https://silpo.example.com/api")["httpStatus"]==403

with patch("silpo_app_probe._check",return_value={"reachable":False,"httpStatus":401}) as mock:
 data=probe_catalog()
 assert mock.call_count==2
 assert data["legacy"]["reachable"] is False
 assert data["modern"]["httpStatus"]==401
 assert data["mode"]=="anonymous-readonly-diagnostic"
print("PASS: two bounded, credential-free diagnostics, reject blocked APIs, do not publish offers")
