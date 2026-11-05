#!/usr/bin/env python3
"""Verified public promotions from the official METRO Ukraine website.

Source: https://www.metro.ua/propositions (default store: Kyiv Pozniaky).
Never use Zakaz.ua, guessed prices, VAT-exclusive prices or unrelated cards.
"""
import datetime as dt
import hashlib
import re

SOURCE = "https://www.metro.ua/propositions"
NUMBER = r"(\d[\d\s\u00a0\u202f]{0,9}[.,]\d{2})"
OFFER = re.compile(
    r"(?<!\w)Акція\s+((?:(?!\bАкція\b).){7,190}?)\s+"
    r"(Available|Limited\s+Availability|Not\s+Available)\s+"
    + NUMBER + r"\s*₴\s*" + NUMBER
    + r"\s*₴\s*[-−]\s*(\d{1,2})\s*%",
    re.I | re.S,
)


def _amount(value):
    return float(re.sub(r"[\s\u00a0\u202f]", "", value).replace(",", "."))


def parse_promotions(text, checked_date=None):
    """Return only exact, independently verifiable old/new promotional prices."""
    checked_date = checked_date or dt.date.today().isoformat()
    text = re.sub(r"\s+", " ", text or "").strip()
    offers = {}
    for match in OFFER.finditer(text):
        raw_name, availability, original, reduced, pct = match.groups()
        if availability.casefold() == "not available":
            continue
        old, price, discount = _amount(original), _amount(reduced), int(pct)
        if not (0 < price < old <= 100000 and 1 <= discount <= 99):
            continue
        if abs((1 - price / old) * 100 - discount) > 1.5:
            continue
        title = re.sub(r"\s+(?:1\s*(?:шт|кг))$", "", raw_name).strip()
        if not 7 <= len(title) <= 180 or "₴" in title:
            continue
        # Price and source are unambiguous; do not attribute this to Zakaz.
        key = hashlib.sha256(title.casefold().encode("utf-8")).hexdigest()[:18]
        item = {
            "id": "metro-" + key,
            "name": title,
            "store": "metro",
            "price": price,
            "oldPrice": old,
            "discount": discount,
            "category": "Акційні товари",
            "date": checked_date,
            "url": SOURCE,
            "locationKey": "kyiv",
            "location": "METRO Київ, Позняки; ціни можуть залежати від ТЦ",
            "sourceType": "metro-official-public-promotions",
            "sourceLabel": "METRO.ua — офіційні акційні ціни (Київ, Позняки)",
            "priceVerified": True,
            "availabilityStatus": "limited" if "limited" in availability.lower() else "listed",
        }
        offers[item["id"]] = item
    return list(offers.values())


async def collect_official(page, stats=None):
    """Try both official product-listing pages; never publish unverified prices."""
    candidates = (SOURCE, "https://www.metro.ua/propositions/topoffers")
    results = {}
    checked = []
    for url in candidates:
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=22000)
            status = response.status if response else None
            title = await page.title()
            if status in (401, 403, 429):
                checked.append({"url": url, "status": status, "count": 0})
                continue
            body = await page.locator("body").inner_text(timeout=12000)
            found = parse_promotions(body)
            checked.append({"url": url, "status": status, "count": len(found)})
            for item in found:
                item["url"] = url
                results[item["id"]] = item
        except Exception as exc:
            checked.append({"url": url, "error": str(exc)[:120]})
    if stats is not None:
        stats.update({"officialListingsChecked": checked, "offersParsed": len(results),
                      "allPricePairsVerified": True, "fullCatalog": False,
                      "scope": "Official METRO product listings only"})
    if not results:
        raise RuntimeError("Official METRO listings had no verified offers: " +
                           str(checked)[:350])
    return list(results.values())
