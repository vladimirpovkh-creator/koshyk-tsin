#!/usr/bin/env python3
"""Read-only quality audit of category assignments in the merged offers.

This is a review queue, not an automatic relabeling system. Patterns here
identify product *types* that conflict with an assigned category, not just
ingredients, flavours or brand mentions.
"""
import argparse
import collections
import json
import re
from pathlib import Path

from categories import category_for, normalize_category_text

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "data" / "offers.json"

# Conflicts are intentionally conservative. Do not label all ingredient
# mentions as wrong: flag only explicit finished-product markers.
CONFLICTS = {
    "Свіжа свинина": r"бургер|локшин|макарон|шаурм|піца|чипс|снек|смаком|пиріг|пиріж|ковбас|паштет",
    "Свіжа птиця": r"бургер|локшин|макарон|шаурм|піца|чипс|снек|смаком|пиріг|пиріж|ковбас|паштет",
    "Свіжа яловичина та телятина": r"бургер|локшин|макарон|шаурм|піца|чипс|снек|смаком|пиріг|пиріж|ковбас|паштет",
    "Свіжа баранина та ягнятина": r"бургер|локшин|макарон|шаурм|піца|чипс|снек|смаком|пиріг|пиріж|ковбас|паштет",
    "Свіже м’ясо (інше)": r"бургер|локшин|макарон|шаурм|піца|чипс|снек|смаком|пиріг|пиріж|ковбас|паштет",
    "Молоко, вершки та рослинні напої": r"горішок|горішки.*згущ|печив|вафл|цукерк|торт|тістеч|шоколад|булоч|круасан",
    "Тверді, м’які та плавлені сири": r"пиріг|пиріж|булоч|слойк|круасан|піца|сироп|тістеч",
    "Риба свіжа та заморожена": r"паштет|консерв|сушен|чипс|корм|локшин|смаком",
    "Пиво": r"чипс|сухарик|ковбас|снек|ароматом|смаком",
    "Вино": r"оцет|соус|цукерк|желе|смаком|ароматом",
    "Горіхи, насіння та сухофрукти": r"печив|цукерк|батончик|торт|тістеч|горішки.*згущ",
}
CONFLICTS = {label: re.compile(pattern, re.I) for label, pattern in CONFLICTS.items()}

# Names with unambiguous product-type evidence that should not remain "Інші".
UNKNOWN_TYPES = {
    "Пиво": re.compile(r"(?:^|\\s)пиво(?:\\s|$|[,.])", re.I),
    "Макарони та локшина": re.compile(r"макарон|локшин|спагеті", re.I),
    "Молоко, вершки та рослинні напої": re.compile(r"(?:^|\\s)молоко(?:\\s|$|[,.;])", re.I),
    "Печиво та вафлі": re.compile(r"печив|вафл", re.I),
}

def audit(offers, sample_limit=12):
    """Return review findings without modifying, hiding or reclassifying offers."""
    if not isinstance(offers, list):
        raise ValueError("Catalog must be a list")
    if not 1 <= sample_limit <= 30:
        raise ValueError("Review sample limit must be between 1 and 30")
    counts = collections.Counter()
    by_category = collections.Counter()
    examples = collections.defaultdict(list)
    seen = set()
    for item in offers:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        name = item["name"].strip()
        if not name:
            continue
        category = category_for(name)
        by_category[category] += 1
        text = normalize_category_text(name)
        reason = None
        if category in CONFLICTS and CONFLICTS[category].search(text):
            reason = "finished-product marker conflicts with category"
        elif category == "Інші товари":
            for expected, expression in UNKNOWN_TYPES.items():
                if expression.search(text):
                    reason = "clear product-type marker remained uncategorized: " + expected
                    break
        if not reason:
            continue
        counts[category] += 1
        key = (category, name.casefold())
        if key in seen or len(examples[category]) >= sample_limit:
            continue
        seen.add(key)
        examples[category].append({"name": name[:190],
                                   "store": str(item.get("store", ""))[:30],
                                   "reason": reason})
    flagged = sum(counts.values())
    total = sum(by_category.values())
    return {"checked": total, "flagged": flagged,
            "flaggedSharePct": round(100 * flagged / total, 2) if total else 0,
            "categoryCounts": dict(sorted(by_category.items())),
            "flaggedByCategory": dict(sorted(counts.items())),
            "samples": dict(sorted(examples.items())),
            "note": "Review candidates only; no products were removed or relabeled."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--sample-limit", type=int, default=12)
    args = parser.parse_args()
    data = json.loads(args.catalog.read_text(encoding="utf-8"))
    result = audit(data, sample_limit=args.sample_limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
