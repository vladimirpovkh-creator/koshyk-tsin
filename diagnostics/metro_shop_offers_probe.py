#!/usr/bin/env python3
"""Read-only proof-of-concept for unambiguous public METRO shop discount cards."""
import asyncio
import datetime as dt
import json
import re
from playwright.async_api import async_playwright

VALUE=r"([0-9][0-9\s\u00a0\u202f]{0,11}[.,][0-9]{2})"
PRICE=re.compile(r"Ціна з ПДВ\s+"+VALUE+r"\s*грн\s*"+VALUE+r"\s*грн",re.I)
PROMO=re.compile(r"Акція\s*Діє\s*протягом\s*\d+\s*дн",re.I)
AVAILABLE=re.compile(r"Доступний\s*\(за умови наявності в Київ, Позняки\. ТЦ №10\)",re.I)
UNAVAILABLE=re.compile(r"Наразі недоступно",re.I)
WHOLESALE=re.compile(r"від\s*\d+\s*\+|від\s*\d+\s*(?:шт\b|од\b)",re.I)

def money(s):
    return float(re.sub(r"[\s\u00a0\u202f]","",s).replace(",", "."))

def parse(text):
    accepted=[];reason_counts={}
    def skip(reason):
        reason_counts[reason]=reason_counts.get(reason,0)+1
    for section in text.split("Купуйте в ТЦ"):
        promo=list(PROMO.finditer(section))
        if not promo:
            skip("no_explicit_promotion");continue
        block=section[promo[-1].end():].strip()
        lines=[line.strip() for line in block.splitlines() if line.strip()]
        if not lines or not (12<=len(lines[0])<=190):
            skip("no_product_name");continue
        if UNAVAILABLE.search(block) or not AVAILABLE.search(block):
            skip("not_explicitly_available_at_kyiv_pozniaky");continue
        if WHOLESALE.search(block):
            skip("conditional_quantity_price");continue
        found=list(PRICE.finditer(block))
        if len(found)!=1:
            skip("not_one_clear_VAT_inclusive_price_pair");continue
        new,old=map(money,found[0].groups())
        if not (0<new<old<=100000):
            skip("discount_invalid");continue
        if not re.search(r"Ціна без ПДВ",block[found[0].end():]):
            skip("no_VAT_exclusive_distinction");continue
        # Require promo metadata preceding this SKU, not in a prior unrelated card.
        if "Тип пакування:" not in block or "ТЦ №10" not in block:
            skip("missing_packaging_or_store");continue
        accepted.append({"name":lines[0],"price":new,"oldPrice":old,
                         "discountPct":round((1-new/old)*100,1)})
    return accepted,reason_counts

def check():
    sample=("АкціяДіє протягом 10 днів\nCandumy Вино Domaine Petit Var сухе рожеве 750мл\n"
            "Тип пакування:\n1 шт\nДоступний (за умови наявності в Київ, Позняки. ТЦ №10)\n"
            "Ціна з ПДВ 323,00 грн\n475,24 грн\nЦіна без ПДВ 256,35 грн\n"
            "430,67 грн / 1 Л\nКупуйте в ТЦ")
    got,_=parse(sample)
    assert len(got)==1 and got[0]["price"]==323 and got[0]["oldPrice"]==475.24,got
    assert parse(sample.replace("Доступний (за умови наявності","Наразі недоступно (за умови наявності"))[0]==[]
    assert parse(sample.replace("АкціяДіє","Цінова перевага Діє"))[0]==[]
    assert parse(sample.replace("Ціна з ПДВ 323,00 грн\n475,24 грн",
                                "Ціна з ПДВ 323,00 грн"))[0]==[]
    assert parse(sample.replace("Ціна з ПДВ 323,00 грн",
                                "250,00 грн від 4+\nЦіна з ПДВ 323,00 грн"))[0]==[]
    print("PASS strict offline METRO shop sale parser",flush=True)

async def run():
    check()
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=["--no-sandbox"])
        page=await browser.new_page(locale="uk-UA",viewport={"width":1350,"height":900})
        try:
            response=await page.goto("https://shop.metro.ua/",wait_until="domcontentloaded",timeout=25000)
            await page.wait_for_timeout(14000)
            body=await page.locator("body").inner_text(timeout=10000)
            if not response or response.status!=200 or "Київ, Позняки. ТЦ №10" not in body:
                raise RuntimeError("METRO shop not publicly accessible for Kyiv Pozniaky")
            offers,rejected=parse(body)
            report={"checkedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
                    "source":"https://shop.metro.ua/",
                    "publication":"disabled",
                    "sourceHttpStatus":response.status,
                    "store":"Київ, Позняки. ТЦ №10",
                    "bodyCharacters":len(body),
                    "candidateOffers":len(offers),"rejectedSections":rejected,
                    "samples":offers[:18]}
            print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
            if not offers:
                raise RuntimeError("No unambiguous public promotional shop cards")
        finally:
            await browser.close()

if __name__=="__main__":
    asyncio.run(run())
