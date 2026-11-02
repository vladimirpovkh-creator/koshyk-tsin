#!/usr/bin/env python3
"""Price-basis normalization. Never guess product mass from its name.

The Silpo API's displayRatio describes the quantity to which displayPrice
applies. Preserve the original label and calculate comparable prices only
when the entire label has an unambiguous amount and unit.
"""
import math
import re

_UNIT = re.compile(
    r"^\s*(\d{1,5}(?:[.,]\d{1,3})?)\s*(кг|г|мл|л|шт)(?:\s*/\s*уп)?\s*$",
    re.IGNORECASE,
)
_MULTIPACK = re.compile(
    r"^\s*(\d{1,3})\s*[x×*]\s*(\d{1,5}(?:[.,]\d{1,3})?)\s*(кг|г|мл|л)(?:\s*/\s*уп)?\s*$",
    re.IGNORECASE,
)

def unit_price(display_ratio, price):
    if not isinstance(display_ratio, str):
        return None
    if not isinstance(price, (int, float)) or isinstance(price, bool):
        return None
    if not math.isfinite(price) or price <= 0:
        return None
    m = _UNIT.fullmatch(display_ratio)
    multipack = None
    if not m:
        multipack = _MULTIPACK.fullmatch(display_ratio)
        if not multipack:
            return None
        count = int(multipack[1])
        amount = count * float(multipack[2].replace(",", "."))
        raw_unit = multipack[3].lower()
    else:
        amount = float(m[1].replace(",", "."))
        raw_unit = m[2].lower()
    if amount <= 0:
        return None
    if raw_unit in ("г", "кг"):
        quantity = amount / 1000 if raw_unit == "г" else amount
        basis = "кг"
    elif raw_unit in ("мл", "л"):
        quantity = amount / 1000 if raw_unit == "мл" else amount
        basis = "л"
    else:
        quantity = amount
        basis = "шт"
    if not 0 < quantity <= 100000:
        return None
    standardized = price / quantity
    if not math.isfinite(standardized) or standardized > 1000000:
        return None
    return {"unitPrice": round(standardized, 2), "unitPriceUnit": basis}
