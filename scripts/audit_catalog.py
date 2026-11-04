#!/usr/bin/env python3
"""Validate retailer promotion catalogs before publishing. Standard library only.

Structural errors fail strict CI; unusually deep discounts and unusually large
catalog changes are reported for review, never silently removed.
"""
import argparse
import datetime as dt
import json
import math
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

DOMAINS = {
    "novus": {"novus.zakaz.ua"},
    "metro": {"metro.zakaz.ua"},
    "novus_official": {"novus.ua"},
    "fora": {"fora.ua"},
    "silpo": {"silpo.ua"},
    "atb": {"www.atbmarket.com"},
}
SAMPLE_LIMIT = 8


def audit(rows, source, *, previous_count=None):
    if source not in DOMAINS:
        raise ValueError("Unsupported retailer")
    errors, warnings = [], []
    by_id, by_url = {}, {}
    discount_count = 0
    extreme = []
    missing_expiry = 0
    dates = Counter()
    if not isinstance(rows, list):
        return {"source": source, "count": 0, "errors": ["Catalog is not a JSON array"],
                "warnings": [], "ok": False}
    for i, row in enumerate(rows):
        prefix = f"row {i + 1}"
        if not isinstance(row, dict):
            errors.append(prefix + ": not an object")
            continue
        item_id, name = row.get("id"), row.get("name")
        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(prefix + ": missing ID")
        elif item_id in by_id:
            errors.append(prefix + f": duplicate ID (first at row {by_id[item_id]})")
        else:
            by_id[item_id] = i + 1
        if not isinstance(name, str) or len(name.strip()) < 6:
            errors.append(prefix + ": missing or short product name")
        expected_store = "novus" if source == "novus_official" else source
        if row.get("store") != expected_store:
            errors.append(prefix + ": retailer mismatch")
        if source == "novus" and row.get("channel") != "online":
            errors.append(prefix + ": expected NOVUS online channel")
        if source == "novus" and row.get("availabilityStatus") != "unverified":
            errors.append(prefix + ": missing honest availability status")
        if source == "novus" and row.get("inStock") is True:
            errors.append(prefix + ": unsupported in-stock claim")
        if source == "novus_official" and row.get("channel") != "official":
            errors.append(prefix + ": expected NOVUS official channel")
        price, old = row.get("price"), row.get("oldPrice")
        numbers_ok = all(isinstance(x, (int, float)) and not isinstance(x, bool)
                         and math.isfinite(x) and 0 < x <= 100000 for x in (price, old))
        if not numbers_ok or old <= price:
            errors.append(prefix + ": invalid promotional prices")
        else:
            discount_count += 1
            pct = round(100 * (1 - price / old), 2)
            if pct >= 90:
                if len(extreme) < SAMPLE_LIMIT:
                    extreme.append({"id": item_id, "name": name, "discountPct": pct,
                                    "price": price, "oldPrice": old})
        url = row.get("url")
        if not isinstance(url, str):
            errors.append(prefix + ": missing product URL")
        else:
            parts = urlsplit(url)
            if parts.scheme != "https" or parts.hostname not in DOMAINS[source]:
                errors.append(prefix + ": unexpected URL host or scheme")
            elif source in ("novus", "metro") and not parts.path.startswith("/uk/products/"):
                errors.append(prefix + ": unexpected Zakaz product path")
            canonical = (parts.hostname or "", parts.path.rstrip("/"))
            if canonical in by_url:
                errors.append(prefix + f": duplicate product URL (first at row {by_url[canonical]})")
            else:
                by_url[canonical] = i + 1
        value = row.get("date")
        try:
            checked = dt.date.fromisoformat(value)
            dates[value] += 1
        except (ValueError, TypeError):
            errors.append(prefix + ": missing or invalid checked date")
            checked = None
        end = row.get("validTo")
        if not end:
            missing_expiry += 1
        else:
            try:
                expires = dt.date.fromisoformat(end)
                if checked and expires < checked:
                    errors.append(prefix + ": promotion expired before checked date")
            except (TypeError, ValueError):
                errors.append(prefix + ": invalid promotion expiration date")
    if extreme:
        warnings.append(f"{len(extreme)} sample(s) of discounts >=90%; review retailer prices")
    if missing_expiry:
        warnings.append(f"{missing_expiry} offers do not declare an expiration date")
    if previous_count is not None and previous_count > 0 and len(rows) < previous_count * 0.65:
        warnings.append(f"Catalog count dropped by >35% versus {previous_count} previous offers")
    report = {
        "source": source, "count": len(rows), "uniqueIds": len(by_id),
        "uniqueProductUrls": len(by_url), "verifiedDiscounts": discount_count,
        "missingExpiry": missing_expiry, "extremeDiscountSamples": extreme,
        "dates": dict(dates), "errors": errors[:100], "errorCount": len(errors),
        "warnings": warnings, "ok": not errors,
    }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--store", required=True, choices=sorted(DOMAINS))
    parser.add_argument("--report", type=Path)
    parser.add_argument("--previous-count", type=int)
    args = parser.parse_args()
    try:
        rows = json.loads(args.input.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("Catalog input unavailable or invalid:", exc)
        raise SystemExit(2)
    report = audit(rows, args.store, previous_count=args.previous_count)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
