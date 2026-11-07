#!/usr/bin/env python3
"""Read-only summary of price-label geometry in METRO's public seasonal PDF."""
import json
import re
import urllib.request
import fitz
URL="https://promotions.metro.ua/834/2320153/pdfs/4c86826c-5dae-4b5a-9fab-a97f239eaee9.pdf"
req=urllib.request.Request(URL,headers={"User-Agent":"KoshykTsin-Diagnostics/1.0"})
with urllib.request.urlopen(req,timeout=75) as response:
    payload=response.read(120_000_001)
if not payload.startswith(b"%PDF-") or len(payload)>120_000_000:
    raise RuntimeError("Invalid official PDF or over size limit")
doc=fitz.open(stream=payload,filetype="pdf")
print("METRO_PDF_LENGTH",len(doc),"BYTES",len(payload),flush=True)
total_units=0
for page_n in range(min(14,len(doc))):
    words=doc[page_n].get_text("words",sort=True)
    units=[w for w in words if w[4].casefold().rstrip(".") in
           ("грн/шт","грн/кг","грн/уп","грн/наб")]
    total_units += len(units)
    evidence=[]
    for u in units[:5]:
        near=[w for w in words if u[0]-155 <= w[0] <= u[0]+25
              and u[1]-100 <= w[1] <= u[1]+15]
        evidence.append({
            "unit":u[4],
            "neighborWords":[x[4] for x in near[:28]],
            "priceTokens":[x[4] for x in near if re.fullmatch(r"\\d{2,7}",x[4])][:9],
        })
    print(json.dumps({"page":page_n+1,"words":len(words),"units":len(units),
                      "examples":evidence},ensure_ascii=False),flush=True)
print("METRO_PDF_UNIT_LABELS_FIRST14",total_units)
