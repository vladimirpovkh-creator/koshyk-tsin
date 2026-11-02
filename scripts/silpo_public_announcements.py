#!/usr/bin/env python3
"""Public, low-volume, official Silpo announcements (not a product-catalog mirror).

Reads only publicly accessible t.me/s/silposilpo messages; no login, keys,
paid services or bypassing anti-bot measures. A promo is included ONLY if its
individual product line explicitly provides a sale price and percentage and
the promotion's dates can be confirmed. Do not infer former prices.
"""
import datetime as dt
import hashlib
import re
from zoneinfo import ZoneInfo

SOURCE="https://t.me/s/silposilpo"
TZ=ZoneInfo("Europe/Kyiv")
MONTHS={"січня":1,"лютого":2,"березня":3,"квітня":4,"травня":5,
        "червня":6,"липня":7,"серпня":8,"вересня":9,"жовтня":10,
        "листопада":11,"грудня":12}
PRICE=re.compile(r"(\d{1,5}(?:[.,]\d{1,2})?)\s*грн\b",re.I)
DISCOUNT=re.compile(r"(?:зі?\s+знижкою|знижк(?:ою|а))\s*[-−]?\s*(\d{1,2})\s*%",re.I)
NUMERIC_PERIOD=re.compile(r"з\s*(\d{1,2})[.](\d{1,2})\s*по\s*(\d{1,2})[.](\d{1,2})",re.I)
WORDS_PERIOD=re.compile(r"(?:тільки\s+)?з\s*(\d{1,2})\s*(?:(\w+)\s+)?до\s*(\d{1,2})\s+(\w+)",re.I)
SAME_MONTH_PERIOD=re.compile(r"(?:тільки\s+)?з\s*(\d{1,2})\s+до\s*(\d{1,2})\s+(\w+)",re.I)
CONDITIONAL=re.compile(r"при купівлі|від\s+\d+\s*[-–]?\s*(?:х|шт)|mastercard|оплат(?:і|ою)\s+картк",re.I)

def _end_date(text, posted, day):
    """Use explicit dates only, never assume undated advertising is current."""
    m=NUMERIC_PERIOD.search(text)
    if m:
        try:return dt.date(posted.year,int(m[4]),int(m[3]))
        except ValueError:return None
    m=SAME_MONTH_PERIOD.search(text)
    if m and (month:=MONTHS.get(m[3].lower())):
        try:return dt.date(posted.year,month,int(m[2]))
        except ValueError:return None
    m=WORDS_PERIOD.search(text)
    if m and (month:=MONTHS.get(m[4].lower())):
        try:return dt.date(posted.year,month,int(m[3]))
        except ValueError:return None
    # "Тільки з 10 до 16 вересня" and "Тільки 7 та 8 листопада".
    m=re.search(r"тільки\s+(\d{1,2})\s+(?:та|і|по)\s+(\d{1,2})\s+(\w+)",text,re.I)
    if m and (month:=MONTHS.get(m[3].lower())):
        try:return dt.date(posted.year,month,int(m[2]))
        except ValueError:return None
    m=re.search(r"(?:до|по)\s*(\d{1,2})[.](\d{1,2})",text,re.I)
    if m:
        try:return dt.date(posted.year,int(m[2]),int(m[1]))
        except ValueError:return None
    if re.search(r"\bсьогодні\b|\bтільки\s+сьогодні\b",text,re.I):
        return posted
    return None

def extract_posts(posts, now=None):
    current=now or dt.datetime.now(TZ)
    day=current.date()
    results={}
    for post in posts:
        if not isinstance(post,dict):continue
        link=post.get("url") or ""
        text=post.get("text") or ""
        if not re.fullmatch(r"https://t[.]me/silposilpo/\d+",link):continue
        try:
            published=dt.datetime.fromisoformat(post["postedAt"].replace("Z","+00:00")).astimezone(TZ).date()
        except (KeyError,ValueError,TypeError):continue
        if published>day or (day-published).days>20:continue
        end=_end_date(text,published,day)
        if end is None or end<day or (end-published).days>35:continue
        for line in text.splitlines():
            line=line.strip()
            match_price=PRICE.search(line)
            match_discount=DISCOUNT.search(line)
            if not match_price or not match_discount or CONDITIONAL.search(line):continue
            price=float(match_price[1].replace(",","."))
            pct=int(match_discount[1])
            if not (0.1<=price<=100000 and 1<=pct<=99):continue
            # First line must be a product listing, not an umbrella offer
            # like "знижки до 40% на товари для тварин".
            name=line[:match_discount.start()].strip(" \t—–-:;.,🎉🧡☕️🥔🍫🐟🍕🥛🍺")
            name=re.sub(r"^[^\w«\"А-ЯІЇЄҐа-яіїєґ]+","",name,flags=re.U)
            if not 8<=len(name)<=180 or not re.search(r"[а-яіїєґА-ЯІЇЄҐ]",name):continue
            key="silpo-"+hashlib.sha256((link+"|"+name).encode()).hexdigest()[:18]
            results[key]={
              "id":key,"name":name,"store":"silpo","price":round(price,2),
              "discount":pct,"validTo":end.isoformat(),"date":day.isoformat(),
              "url":link,"category":"Акційні товари","locationKey":"kyiv",
              "location":"Оголошення мережі Сільпо; ціна в конкретному магазині не перевірена",
              "sourceType":"official-announcement",
              "sourceLabel":"Сільпо — офіційний Telegram (не повний каталог)",
              "priceVerified":True
            }
    return list(results.values())

async def collect_public_announcements(page):
    await page.goto(SOURCE,wait_until="domcontentloaded",timeout=20000)
    posts=await page.evaluate("""() => [...document.querySelectorAll('.tgme_widget_message')].map(m=>({
      url:'https://t.me/'+(m.getAttribute('data-post')||''),
      text:m.querySelector('.tgme_widget_message_text')?.innerText||'',
      postedAt:m.querySelector('.tgme_widget_message_date time')?.getAttribute('datetime')||''
    }))""")
    return extract_posts(posts)
