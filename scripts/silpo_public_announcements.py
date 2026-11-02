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
        try:
            start=dt.date(posted.year,int(m[2]),int(m[1]))
            return dt.date(posted.year,int(m[4]),int(m[3])) if start<=day else None
        except ValueError:return None
    m=SAME_MONTH_PERIOD.search(text)
    if m and (month:=MONTHS.get(m[3].lower())):
        try:
            start=dt.date(posted.year,month,int(m[1]))
            return dt.date(posted.year,month,int(m[2])) if start<=day else None
        except ValueError:return None
    m=WORDS_PERIOD.search(text)
    if m and (month:=MONTHS.get(m[4].lower())):
        try:
            start_month=MONTHS.get(m[2].lower()) if m[2] else month
            start=dt.date(posted.year,start_month,int(m[1]))
            return dt.date(posted.year,month,int(m[3])) if start<=day else None
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

def summarize_posts(posts, now=None):
    """Give auditable reasons for a zero-item official Telegram result."""
    current=now or dt.datetime.now(TZ)
    day=current.date()
    stats={"messages":len(posts),"postsWithPrice":0,"postsWithProductDiscount":0,
           "postsWithCurrentPeriod":0,"acceptedOffers":0}
    for post in posts:
        text=post.get("text","")
        if PRICE.search(text):stats["postsWithPrice"]+=1
        if PRICE.search(text) and DISCOUNT.search(text):stats["postsWithProductDiscount"]+=1
        try:
            date=dt.datetime.fromisoformat(post["postedAt"].replace("Z","+00:00")).astimezone(TZ).date()
        except (KeyError,ValueError,TypeError):continue
        end=_end_date(text,date,day)
        if end and date<=day<=end and (end-date).days<=35:
            stats["postsWithCurrentPeriod"]+=1
    stats["acceptedOffers"]=len(extract_posts(posts,current))
    return stats

async def collect_public_announcements(page, diagnostics=None):
    """Read up to three Telegram public history pages, no account or private API."""
    posts=[]
    seen=set()
    next_url=SOURCE
    history_pages=0
    for _ in range(3):
        await page.goto(next_url,wait_until="domcontentloaded",timeout=20000)
        found=await page.evaluate("""() => [...document.querySelectorAll('.tgme_widget_message')].map(m=>({
          url:'https://t.me/'+(m.getAttribute('data-post')||''),
          text:m.querySelector('.tgme_widget_message_text')?.innerText||'',
          postedAt:m.querySelector('.tgme_widget_message_date time')?.getAttribute('datetime')||''
        }))""")
        if not found:break
        fresh=[p for p in found if p["url"] not in seen]
        if not fresh:break
        posts.extend(fresh)
        seen.update(p["url"] for p in fresh)
        history_pages+=1
        ids=[]
        for p in found:
            match=re.fullmatch(r"https://t[.]me/silposilpo/(\d+)",p["url"])
            if match:ids.append(int(match[1]))
        if not ids:break
        oldest=min(ids)
        next_url=SOURCE+"?before="+str(oldest)
        dates=[]
        for p in found:
            try:
                dates.append(dt.datetime.fromisoformat(p["postedAt"].replace("Z","+00:00")).astimezone(TZ).date())
            except (KeyError,ValueError,TypeError):continue
        if dates and max(dates)<dt.datetime.now(TZ).date()-dt.timedelta(days=20):break
    offers=extract_posts(posts)
    if diagnostics is not None:
        diagnostics.update(summarize_posts(posts))
        diagnostics["pagesChecked"]=history_pages
    return offers
