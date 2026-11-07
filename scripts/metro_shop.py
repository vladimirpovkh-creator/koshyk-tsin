#!/usr/bin/env python3
"""Verified, explicitly discounted public METRO Shop offers for Kyiv Pozniaky.

Only rendered public HTML text, without login, hidden APIs or bypasses.
Never treat VAT-exclusive or quantity-dependent prices as retail discounts.
"""
import datetime as dt
import hashlib
import re
from zoneinfo import ZoneInfo

SOURCE = "https://shop.metro.ua/"
STORE_TEXT = "Київ, Позняки. ТЦ №10"
VALUE = r"([0-9][0-9\s\u00a0\u202f]{0,11}[.,][0-9]{2})"
PRICE_PAIR = re.compile(r"Ціна з ПДВ\s+" + VALUE + r"\s*грн\s*" + VALUE + r"\s*грн", re.I)
PROMO = re.compile(r"Акція\s*Діє\s*протягом\s*\d+\s*днів\b", re.I)
AVAILABLE = re.compile(r"Доступний\s*\(за умови наявності в Київ, Позняки\. ТЦ №10\)", re.I)
NOT_AVAILABLE = re.compile(r"Наразі недоступно", re.I)
WHOLESALE = re.compile(r"від\s*\d+\s*\+|від\s*\d+\s*(?:шт\b|од\b)",re.I)


def _money(value):
    return float(re.sub(r"[\s\u00a0\u202f]", "", value).replace(",", "."))


def parse_shop_promotions(text, checked_date=None):
    """Only explicit promo cards with unambiguous displayed VAT-inclusive prices."""
    checked = checked_date or dt.datetime.now(ZoneInfo("Europe/Kyiv")).date().isoformat()
    if STORE_TEXT not in text:
        return []
    offers = {}
    rejected_ids = set()
    for section in text.split("Купуйте в ТЦ"):
        markers = list(PROMO.finditer(section))
        if not markers:
            continue
        block = section[markers[-1].end():].strip()
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        title = lines[0]
        if (not 12 <= len(title) <= 190 or "грн" in title.casefold()
                or "Тип пакування:" not in block or "Ціна без ПДВ" not in block):
            continue
        if NOT_AVAILABLE.search(block) or not AVAILABLE.search(block) or WHOLESALE.search(block):
            continue
        matches = list(PRICE_PAIR.finditer(block))
        if len(matches) != 1:
            continue
        new, old = map(_money, matches[0].groups())
        if not (0 < new < old < 100000) or (1 - new / old) * 100 < 1:
            continue
        # The old-price line must precede the expressly VAT-exclusive line.
        if "Ціна без ПДВ" not in block[matches[0].end():]:
            continue
        key = "metro-" + hashlib.sha256(title.casefold().encode("utf-8")).hexdigest()[:18]
        item = {
            "id": key, "name": title, "store": "metro",
            "price": new, "oldPrice": old,
            "discount": round((1 - new / old) * 100),
            "date": checked, "url": SOURCE,
            "locationKey": "kyiv",
            "location": "METRO Київ, Позняки. ТЦ №10; наявність залежить від ТЦ",
            "sourceType": "metro-official-shop-public-promo",
            "sourceLabel": "METRO Shop — акційна ціна з ПДВ (Київ, Позняки)",
            "priceVerified": True, "conditionsVerified": False,
            "availabilityStatus": "listed",
            "catalogCoverage": "verified-individual-price-only",
        }
        if key in rejected_ids:
            continue
        existing = offers.get(key)
        if existing and (existing["price"], existing["oldPrice"]) != (new, old):
            offers.pop(key)
            rejected_ids.add(key)
        else:
            offers[key] = item
    return list(offers.values())


async def collect_shop_promotions(page, stats=None):
    """Allow the official public storefront to hydrate without authentication."""
    diagnostics = {"source": SOURCE}
    try:
        response = await page.goto(SOURCE, wait_until="domcontentloaded", timeout=25000)
        diagnostics["httpStatus"] = response.status if response else None
        if not response or response.status != 200 or not page.url.startswith(SOURCE):
            return []
        await page.wait_for_timeout(14000)
        body = (await page.locator("body").inner_text(timeout=12000))[:250000]
        diagnostics["hasExpectedStore"] = STORE_TEXT in body
        offers = parse_shop_promotions(body)
        diagnostics["verifiedOffers"] = len(offers)
        return offers
    except Exception as exc:
        diagnostics["error"] = type(exc).__name__ + ": " + str(exc)[:180]
        return []
    finally:
        if stats is not None:
            stats.update(diagnostics)
