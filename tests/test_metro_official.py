#!/usr/bin/env python3
"""Official METRO prices: no VAT confusion, inventory guesses or Zakaz fallback."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from metro_official import parse_promotions, catalog_pdf_candidates, SOURCE

page = """
Каталоги
Риба та морепродукти
Акція Дорадо охолоджена розмірний ряд 300-400г 1 кг Available
548,99 ₴ 478,96 ₴ - 13 % 399,13 ₴ без ПДВ Ціна / кг
Акція Сібас розмірний ряд 300-400г 1 кг Not Available
598,99 ₴ 518,95 ₴ - 13 % 432,46 ₴ без ПДВ
Акція Камчадал Ікра лососева зерниста солона 100г 1 шт Available
1 309,00 ₴ 999,00 ₴ - 24 % 832,50 ₴ без ПДВ 9 990,00 ₴ / КГ
Акція Сібас розмірний ряд 200-300г 1 кг Limited Availability
548,99 ₴ 438,95 ₴ - 20 % 365,79 ₴ без ПДВ
Акція Некоректна ціна 1 шт Available 200,00 ₴ 100,00 ₴ - 5 % 83,33 ₴ без ПДВ
Акція Без знижки 1 шт Available 300,00 ₴ 300,00 ₴ - 0 % 250,00 ₴ без ПДВ
"""
results = parse_promotions(page, "2026-11-05")
assert len(results) == 3, results
dorado = next(x for x in results if x["name"].startswith("Дорадо"))
assert dorado["price"] == 478.96 and dorado["oldPrice"] == 548.99, dorado
assert dorado["sourceType"] == "metro-official-public-promotions"
assert dorado["url"] == SOURCE
assert dorado["priceVerified"] is True
assert "Позняки" in dorado["location"]
assert any(x["price"] == 999.0 and x["oldPrice"] == 1309.0 for x in results)
assert any(x["availabilityStatus"] == "limited" for x in results)
assert all("Сібас розмірний ряд 300-400" not in x["name"] for x in results)
assert not parse_promotions("Access denied - Cloudflare")
assert not parse_promotions("Великий вибір товарів. Акція знижки без цін.")
assert not parse_promotions("Акція Тест 1 шт Available 200,00 ₴ 110,00 ₴ - 5 % 91,66 ₴")
assert not any("zakaz.ua" in x["url"] for x in results)
# Rotation: expired pinned leaflets must not be reused, but replacement
# official PDF links should be allowed and validated from their printed cover.
known="https://promotions.metro.ua/834/old/pdfs/old.pdf"
new="https://promotions.metro.ua/834/new/pdfs/new.pdf"
assert catalog_pdf_candidates([],known,"2026-11-08","2026-11-09")==[]
assert catalog_pdf_candidates([],known,"2026-11-08","2026-11-07")==[known]
assert catalog_pdf_candidates([new],known,"2026-11-08","2026-11-09")==[new]
assert catalog_pdf_candidates(["https://evil.example/pdfs/fake.pdf",
                               "https://promotions.metro.ua.evil.example/pdfs/fake.pdf",
                               "http://promotions.metro.ua/pdfs/fake.pdf",
                               new,new+"?tracking=1"],
                              known,"2026-11-08","2026-11-09")==[new]
print("PASS: official METRO prices, availability and safe PDF catalog rotation")
