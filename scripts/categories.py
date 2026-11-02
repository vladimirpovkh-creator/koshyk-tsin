"""Shared ordered categories for the price basket.

Python merge and JavaScript UI both read data/category_rules.json so that
same names do not drift between imported and collected products.
"""
import json
import re
from pathlib import Path

# Some ATB product titles use visually identical Cyrillic and Latin letters
# inside the same word (for example, "Пивo" or "Kaвa"). Correct only mixed
# words, leaving fully Latin brand names unchanged.
_CYR=re.compile(r"[а-яіїєґ]",re.I)
_LAT=re.compile(r"[a-z]",re.I)
_TOKENS=re.compile(r"[a-zа-яіїєґ]+",re.I)
_CONFUSABLES=str.maketrans({
    "a":"а","c":"с","e":"е","i":"і","o":"о","p":"р",
    "x":"х","y":"у","k":"к","h":"н","m":"м","b":"в","t":"т"
})
def normalize_category_text(value):
    text=str(value or "").lower()
    return _TOKENS.sub(
        lambda match: match.group().translate(_CONFUSABLES)
        if _CYR.search(match.group()) and _LAT.search(match.group())
        else match.group(),
        text,
    )

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
    text=normalize_category_text(name).strip()
    for label,pattern,excluded in RULES:
        if pattern.search(text) and (excluded is None or not excluded.search(text)):
            return label
    return "Інші товари"
