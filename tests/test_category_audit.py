#!/usr/bin/env python3
"""Category audit must be deterministic, read-only and conservative."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_categories import audit

items = [
    {"name": "Свиняча лопатка н/ф охолоджена", "store": "fora", "category": "Невірна стара категорія"},
    {"name": "Горішок зі згущеним молоком", "store": "metro"},
    {"name": "Бургер з рваною свининою Pulled pork, 220г", "store": "fora"},
    {"name": "Локшина Cung Dinh зі смаком тушкованої свинини 80г", "store": "novus"},
    {"name": "Молоко пастеризоване 2,5% 900 мл", "store": "atb"},
    {"name": "Вино червоне сухе 0,75 л", "store": "silpo"},
    {"name": "Пиво світле 0,5 л", "store": "novus"},
    {"name": "Шоколад Ritter Sport з ромом", "store": "metro"},
]
items.extend([
    {"name": "Пиво Seth&Riley Garage зі смаком полуниці 4,4% 0,44л", "store": "novus"},
    {"name": "Чипси Люкс зі смаком лосося 125г", "store": "novus"},
    {"name": "Лосось Русалочка соломка солоно-сушений 50г", "store": "fora"},
])
before = [dict(x) for x in items]
report = audit(items)
assert items == before, "Audit must never modify source offers"
assert report["checked"] == len(items), report
assert report["flagged"] == 0, report
assert report["categoryCounts"]["Пиво"] == 2, report
assert report["categoryCounts"].get("Риба свіжа та заморожена", 0) == 0, report
assert report["categoryCounts"]["Свіжа свинина"] == 1, report
assert report["categoryCounts"]["Готові страви та салати"] == 1, report
assert report["categoryCounts"]["Макарони та локшина"] == 1, report

# An intentionally inconsistent test fixture: audit the assignment logic
# through its patchable category_for hook, not untrusted saved .category.
from unittest.mock import patch
wrong = [
    {"name": "Бургер з рваною свининою", "store": "fora"},
    {"name": "Печиво зі згущеним молоком", "store": "metro"},
    {"name": "Молоко 2,5% 900 мл", "store": "atb"},
]
with patch("audit_categories.category_for", side_effect=[
    "Свіжа свинина",
    "Молоко, вершки та рослинні напої",
    "Молоко, вершки та рослинні напої",
]):
    result = audit(wrong, sample_limit=1)
assert result["checked"] == 3
assert result["flagged"] == 2, result
assert result["flaggedByCategory"]["Свіжа свинина"] == 1
assert result["flaggedByCategory"]["Молоко, вершки та рослинні напої"] == 1
assert result["samples"]["Свіжа свинина"][0]["name"] == wrong[0]["name"]
assert len(result["samples"]["Молоко, вершки та рослинні напої"]) == 1
assert audit([])["flaggedSharePct"] == 0
try:
    audit(items, sample_limit=31)
except ValueError:
    pass
else:
    raise AssertionError("Audit accepted unbounded sample count")

print("PASS: category audit finds product-type conflicts without changing offers")
