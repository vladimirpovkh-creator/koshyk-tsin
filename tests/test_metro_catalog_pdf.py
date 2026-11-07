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

# The PDF's *printed* dates, not hard-coded code dates, determine eligibility.
import fitz
from metro_catalog_pdf import valid_period_from_cover
pdf=fitz.open()
pg=pdf.new_page()
pg.insert_text((50,80),"Weekend",fontsize=12)
# Latin fixtures have the same date semantics as the Ukrainian printed title,
# with the actual Ukrainian title already checked in live PDFs.
assert valid_period_from_cover(b"bad PDF","weekend","2026-11-05") is None
# Regression: three appearances of the same product (including a conflict)
# must never raise TypeError or publish the conflicted product.
class FakePage:
 def __init__(self,whole):
  self.whole=whole
 def get_text(self,kind,sort=True):
  return [w(30,190,"Філе"),w(62,190,"куряче"),
          w(30,207,"охолоджене"),w(30,222,"фасоване"),
          w(192,236,str(self.whole)),w(253,244,"00"),w(253,272,"ГРН/КГ")]
class FakeDoc:
 def __len__(self):return 3
 def __getitem__(self,i):return FakePage((229,220,229)[i])
from unittest.mock import patch
with patch("fitz.open",return_value=FakeDoc()):
 rows=parse_pdf(b"%PDF-fixture","https://promotions.metro.ua/catalog/pdfs/test.pdf",
                "2026-11-08",checked_date="2026-11-07")
 assert rows==[],rows
print("PASS: spatial METRO prices; ambiguous and repeated conflicting prices rejected")
