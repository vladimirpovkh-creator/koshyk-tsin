"""Shared ordered categories for the price basket.

Python merge and JavaScript UI both read data/category_rules.json so that
same names do not drift between imported and collected products.
"""
import json
import re
from pathlib import Path

RULES_PATH=Path(__file__).resolve().parents[1]/"data"/"category_rules.json"
with RULES_PATH.open(encoding="utf-8") as stream:
    _data=json.load(stream)
RULES=[
    (
        item["label"],
        re.compile(item["pattern"],re.IGNORECASE),
        re.compile(item["exclude"],re.IGNORECASE) if item.get("exclude") else None,
    )
    for item in _data["rules"]
]
def category_for(name):
    text=str(name or "").strip()
    for label,pattern,excluded in RULES:
        if pattern.search(text) and (excluded is None or not excluded.search(text)):
            return label
    return "Інші товари"
