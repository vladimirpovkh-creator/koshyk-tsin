#!/usr/bin/env python3
"""Reject ambiguous pack labels and normalize only explicit units."""
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from price_units import unit_price

assert unit_price("100г",3.99)=={"unitPrice":39.9,"unitPriceUnit":"кг"}
assert unit_price("1кг",39.9)=={"unitPrice":39.9,"unitPriceUnit":"кг"}
assert unit_price("0,135кг",24.99)=={"unitPrice":185.11,"unitPriceUnit":"кг"}
assert unit_price("0,2л",19.99)=={"unitPrice":99.95,"unitPriceUnit":"л"}
assert unit_price("900мл",45)=={"unitPrice":50.0,"unitPriceUnit":"л"}
assert unit_price("12шт",120)=={"unitPrice":10.0,"unitPriceUnit":"шт"}
assert unit_price("52шт/уп",260)=={"unitPrice":5.0,"unitPriceUnit":"шт"}
for ambiguous in ("1.0", "1", "100г/шт", "100г+50г", "за кг", "шт/кг", "10г х 3", "0г", "", None):
    assert unit_price(ambiguous,10) is None,(ambiguous,unit_price(ambiguous,10))
for invalid in (None,True,0,-1,float("nan"),float("inf")):
    assert unit_price("100г",invalid) is None
print("PASS: compare per kg/l/item only when pack basis is unambiguous")
