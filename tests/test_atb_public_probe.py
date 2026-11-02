#!/usr/bin/env python3
"""Offline bounded ATB public catalog response diagnostics tests."""
import sys
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from atb_public_probe import inspect_html,probe_site,URLS

html='''<html><title>Акція "Економія" в АТБ</title><body>
<h1>Економія</h1><a href="/product/moloko-123">Молоко 900г</a>
<div>39.90 грн/шт 55.90</div></body></html>'''
parsed=inspect_html(html)
assert parsed["challenge"] is False
assert parsed["productLinkCount"]==1
assert parsed["hasEconomyHeading"] is True
assert parsed["priceMarkers"]==1
assert inspect_html('<title>Трохи зачекайте…</title>Триває перевірка безпеки')['challenge']
assert inspect_html('<title>Just a moment</title>Cloudflare challenge')['challenge']
try:probe_site("https://other.example")
except ValueError:pass
else:raise AssertionError("Unexpected URL accepted")
with patch("atb_public_probe.request.urlopen",side_effect=HTTPError(URLS[0],403,"Forbidden",{},None)) as mocked:
    blocked=probe_site(URLS[0])
    assert blocked["httpStatus"]==403 and not blocked["reachable"]
    assert mocked.call_count==1
print("PASS: only fixed URLs; challenge detection; rejected HTTP 403")
