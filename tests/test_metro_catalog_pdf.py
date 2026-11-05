#!/usr/bin/env python3
"""Reject ambiguous METRO catalogue prices and preserve full source provenance."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from metro_catalog_pdf import _words_for_one_offer,parse_pdf

def w(x,y,t):
    return (x,y,x+max(len(t)*5,10),y+12,t,0,0,0)
words = [
 w(30,190,"Філе"),w(62,190,"куряче"),
 w(30,207,"охолоджене"),w(30,222,"фасоване"),
 w(192,236,"229"),w(253,244,"00"),w(253,272,"ГРН/КГ"),
]
assert _words_for_one_offer(words,words[-1]) == ("Філе куряче охолоджене фасоване",229.0)
assert _words_for_one_offer(words[:-2]+[words[-1]],words[-1]) is None
assert _words_for_one_offer(words+[w(210,254,"від")],words[-1]) is None
assert parse_pdf(b"not-a-pdf","https://promotions.metro.ua/example.pdf","2026-11-08")==[]
assert parse_pdf(b"%PDF-invalid","https://metro.zakaz.ua/foo.pdf","2026-11-08")==[]
print("PASS: spatial METRO price matches exact units; ambiguous conditions rejected")
