#!/usr/bin/env python3
"""Read-only diagnostic of public official METRO Ukraine website pages.

No authentication, access-control bypass, scraping of private APIs, or changes
to any production price data. Output contains aggregate signals only.
"""
import argparse
import asyncio
import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

SOURCES = (
    ("metro_promotions", "https://www.metro.ua/propositions"),
    ("metro_topoffers", "https://www.metro.ua/propositions/topoffers"),
    ("metro_home", "https://www.metro.ua/"),
    ("metro_shop", "https://shop.metro.ua/"),
)
ALLOWED_HOSTS = {"www.metro.ua", "metro.ua", "shop.metro.ua"}
PRICE = re.compile(r"(?<!\d)\d[\d\s\u00a0\u202f]{0,8}[.,]\d{2}\s*(?:₴|грн)|(?:₴|грн)\s*\d[\d\s]{0,8}[.,]\d{2}", re.I)
DISCOUNT = re.compile(r"(?<!\w)(?:акц[іi]я|знижк|спец[іi]альн[а-яіїєґ]*\s+ц[іi]н|promo|promotion)(?!\w)",re.I)
VAT = re.compile(r"(?:з\s*ПДВ|без\s*ПДВ)",re.I)
WHOLESALE = re.compile(r"(?:від\s*\d+\s*(?:шт|од)|оптов[а-яіїєґ]*\s+ц[іi]н|\d+\s*\+\s*шт)",re.I)
LOCATION = re.compile(r"(?:Позняки|Позняк|Київ|Киев|Kyiv|Pozniaky)",re.I)


def classify(status, body):
    """Signals are diagnostics, never evidence that a product is price-verified."""
    text = body or ""
    if status in (401, 403, 429):
        label = "access_restricted"
    elif status is None or not 200 <= status < 300:
        label = "http_error"
    elif len(text.strip()) < 100:
        label = "insufficient_visible_content"
    else:
        label = "public_content_accessible"
    return {
        "access": label,
        "visibleCharacters": len(text),
        "visiblePriceMentions": len(PRICE.findall(text)),
        "promotionMentions": len(DISCOUNT.findall(text)),
        "vatMentions": len(VAT.findall(text)),
        "wholesaleConditionMentions": len(WHOLESALE.findall(text)),
        "locationMentions": len(LOCATION.findall(text)),
        "kyivPozniakyExplicit": bool(re.search(r"Позняк|Pozniaky", text, re.I)),
        "verifiedOfferCount": 0,
    }


def self_test():
    assert classify(403,"Access Denied")["access"] == "access_restricted"
    assert classify(200,"")["access"] == "insufficient_visible_content"
    text = ("METRO Київ Позняки. Акція філе куряче 229,00 грн з ПДВ. "
            "Ціна від 2 шт. " * 3)
    result = classify(200,text)
    assert result["access"] == "public_content_accessible"
    assert result["visiblePriceMentions"] == 3
    assert result["kyivPozniakyExplicit"] is True
    assert result["wholesaleConditionMentions"] == 3
    assert result["verifiedOfferCount"] == 0
    print("PASS: offline METRO diagnostics classifiers")


async def probe():
    report = {
        "checkedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "purpose": "read_only_source_access_diagnostics",
        "verifiedOfferCount": 0,
        "productionDataModified": False,
        "sources": [],
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(locale="uk-UA", viewport={"width": 1350, "height": 900})
        try:
            for name, url in SOURCES:
                record = {"name":name, "url":url}
                page = await context.new_page()
                network = {"requests":0,"failedRequests":0,"http4xx":0,"http5xx":0,"scriptResponses":0}
                page.on("request", lambda _: network.__setitem__("requests",network["requests"]+1))
                page.on("requestfailed", lambda _: network.__setitem__("failedRequests",network["failedRequests"]+1))
                def inspect_response(r):
                    try:
                        status = r.status
                        if status >= 500: network["http5xx"] += 1
                        elif status >= 400: network["http4xx"] += 1
                        if r.request.resource_type == "script": network["scriptResponses"] += 1
                    except Exception:
                        pass
                page.on("response", inspect_response)
                try:
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                    record["httpStatus"] = response.status if response else None
                    # Restrict collection to intended public hosts; never follow
                    # a redirected login, advertising or unrelated domain.
                    actual = urlparse(page.url)
                    record["redirectedHost"] = actual.hostname
                    if actual.scheme != "https" or actual.hostname not in ALLOWED_HOSTS:
                        record["access"] = "unexpected_redirect"
                    elif record["httpStatus"] in (401,403,429):
                        record.update(classify(record["httpStatus"], ""))
                    else:
                        try:
                            await page.wait_for_timeout(12000 if name=="metro_shop" else 1200)
                            body = (await page.locator("body").inner_text(timeout=12000))[:250000]
                            record.update(classify(record["httpStatus"], body))
                            record["pageTitleLength"] = len(await page.title())
                            record["domReadyState"] = await page.evaluate("document.readyState")
                            record["bodyHtmlCharacters"] = await page.locator("body").evaluate(
                                "(body)=>body.outerHTML.length"
                            )
                            record["scriptTags"] = await page.locator("script").count()
                            record["mainElements"] = await page.locator("main").count()
                            record["formElements"] = await page.locator("form").count()
                            record["anchorElements"] = await page.locator("a").count()
                            record["visibleTextAfterDelay"] = len(body.strip())
                            record["productLinks"] = await page.locator(
                                'a[href*="/product"],a[href*="/products"],a[href*="/propositions"]'
                            ).count()
                        except Exception as exc:
                            record["access"] = "body_read_error"
                            record["errorClass"] = type(exc).__name__
                except Exception as exc:
                    record["access"] = "navigation_error"
                    record["errorClass"] = type(exc).__name__
                finally:
                    record["networkSummary"] = network
                    await page.close()
                report["sources"].append(record)
                print(json.dumps(record,ensure_ascii=False),flush=True)
        finally:
            await browser.close()
    Path("metro-source-diagnostic.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n", encoding="utf-8"
    )
    print("METRO probe complete. No catalog files changed.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        asyncio.run(probe())
