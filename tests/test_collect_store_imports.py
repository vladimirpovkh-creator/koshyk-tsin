#!/usr/bin/env python3
"""A retailer job must not require another retailer's optional parser."""
import builtins
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
original_import=builtins.__import__

def import_without_atb_html(name,*args,**kwargs):
    if name=="atb_economy_html" or name.startswith("bs4"):
        raise AssertionError(f"eager optional ATB HTML import: {name}")
    return original_import(name,*args,**kwargs)

builtins.__import__=import_without_atb_html
try:
    import collect_store
finally:
    builtins.__import__=original_import

assert "atb_economy_html" not in sys.modules
print("PASS: non-ATB retailer jobs do not require the optional ATB HTML parser")
