#!/usr/bin/env python3
"""Catalog pagination offers only the supported page sizes."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/"index.html").read_text(encoding="utf-8")

assert 'id="pageSize"' in html
assert all(f'value="{size}"' in html for size in (30,60,90))
assert 'pageData=data.slice' in html
assert 'id="prevPage"' in html and 'id="nextPage"' in html
assert 'currentPage=1' in html and 'Math.ceil(data.length/pageSize)' in html
print("PASS: catalog pagination supports 30, 60 and 90 products per page")
