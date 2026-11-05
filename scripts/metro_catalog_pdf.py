#!/usr/bin/env python3
"""Strict spatial extraction from METRO-owned, dated PDF promotion leaflets.

Never infer prices from non-spatial text or scan non-METRO sources. Only
publish a single, printed per-unit price when no multi-buy/starting-from
qualifier is near the label and the promotion is active.
"""
import datetime as dt
import hashlib
import re
from io import BytesIO
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

DOMAIN = "promotions.metro.ua"
PRICE_UNITS = {"ГРН/КГ": "кг", "ГРН/ШТ": "шт", "ГРН/ШТ.": "шт", "ГРН/УП": "уп"}
SKIP = re.compile(
    r"(?i)^(?:УКРАЇНА|ІСПАНІЯ|ВЛАСНИЙ|ІМПОРТ|ТЕРМІН|ДІЇ|ПРОПОЗИЦІЇ|"
    r"ПОНАД|МЕТРО|METRO|ЦІНА|ДО|ЗНИЖКА|[\\d.,% ~]+)$"
)
CONDITIONS = {"від", "до", "шт.", "ціна", "асортимент", "набір"}
UNSAFE = re.compile(r"(?i)(без\\s*ПДВ|від\\s*\\d+\\s*шт|ціна\\s*від|за\\s*умови)")


def _words_for_one_offer(words, unit):
    ux, uy = unit[0], unit[1]
    cents = [w for w in words if re.fullmatch(r"\\d{2}", w[4]) and
             abs(w[0] - ux) < 11 and uy - 41 <= w[1] <= uy - 8]
    mains = [w for w in words if re.fullmatch(r"[1-9]\\d{0,3}", w[4]) and
             ux - 102 <= w[0] <= ux - 24 and uy - 54 <= w[1] <= uy - 11]
    # No decimal certainty: never guess from plain 7900 or 11400.
    if len(cents) != 1 or len(mains) != 1:
        return None
    whole = int(mains[0][4])
    price = round(whole + int(cents[0][4]) / 100, 2)
    if not 1 <= price <= 10000:
        return None
    main = mains[0]
    # Reject multi-buy, "from" and overlapping price displays.
    qualifier = [w for w in words if ux - 110 <= w[0] <= ux + 28 and
                 uy - 77 <= w[1] <= uy + 22 and
                 w[4].casefold().strip(".,") in CONDITIONS]
    if qualifier:
        return None
    # Name must be printed in its own left-of-price region, not borrowed
    # from a different column or next row.
    name_words = [w for w in words if w[0] < main[0] - 26 and
                  main[0] - 210 <= w[0] and
                  main[1] - 57 <= w[1] <= main[1] + 42 and
                  re.search(r"[А-Яа-яІіЇїЄєҐґ]",w[4]) and
                  not SKIP.fullmatch(w[4].strip(" .,:;"))]
    lines = {}
    for w in name_words:
        line_key = round(w[1] / 8) * 8
        lines.setdefault(line_key, []).append(w)
    valid_lines = []
    for y, items in sorted(lines.items()):
        words_in_line = [w[4] for w in sorted(items,key=lambda v:v[0])]
        phrase = " ".join(words_in_line).strip()
        if len(phrase) >= 3 and not re.search(
            r"(?i)(термін|пропозиц|охолодженого\\s*м'яса\\s*асортимент|грн)",phrase
        ):
            valid_lines.append((y,phrase))
    if not valid_lines:
        return None
    # Choose at most 3 contiguous product-name lines by proximity.
    valid_lines.sort(key=lambda x: abs(x[0] - main[1]))
    chosen = sorted(valid_lines[:3])
    name = re.sub(r"\\s+"," "," ".join(x[1] for x in chosen)).strip()
    if len(name) < 12 or len(name) > 110 or len(name.split()) < 2:
        return None
    if UNSAFE.search(name):
        return None
    return name,price


def parse_pdf(pdf_bytes, url, valid_to, checked_date=None, max_pages=12):
    """Return independently located price/name pairs from METRO print PDF."""
    import fitz
    if urlparse(url).hostname != DOMAIN or not pdf_bytes.startswith(b"%PDF-"):
        return []
    checked = checked_date or dt.datetime.now(ZoneInfo("Europe/Kyiv")).date().isoformat()
    if valid_to < checked:
        return []
    document = fitz.open(stream=pdf_bytes,filetype="pdf")
    # Do not accept PDFs with no searchable text or impossible page layout.
    if not 1 <= len(document) <= 100:
        return []
    found = {}
    for page_number in range(min(len(document),max_pages)):
        page = document[page_number]
        words = page.get_text("words",sort=True)
        for unit in words:
            label = unit[4].upper().strip()
            if label not in PRICE_UNITS:
                continue
            parsed = _words_for_one_offer(words,unit)
            if not parsed:
                continue
            name,price = parsed
            key = hashlib.sha256((name.casefold()+"|"+PRICE_UNITS[label]).encode()).hexdigest()[:18]
            item = {
                "id":"metro-"+key,
                "name":name,
                "store":"metro",
                "price":price,
                "category":"Акційні товари",
                "date":checked,
                "validTo":valid_to,
                "url":url,
                "locationKey":"kyiv",
                "location":"Офіційний каталог METRO; ціни та наявність залежать від ТЦ",
                "sourceType":"metro-official-pdf-catalog",
                "sourceLabel":"METRO.ua — офіційний акційний PDF (умови за посиланням)",
                "priceVerified":True,
                "conditionsVerified":False,
                "priceUnit":PRICE_UNITS[label],
                "catalogPage":page_number + 1,
                "catalogCoverage":"verified-individual-price-only",
            }
            # Within the same PDF, conflicting prices are ambiguous.
            if key in found and found[key]["price"] != price:
                found[key] = None
            elif key not in found:
                found[key] = item
    return [x for x in found.values() if x is not None]
