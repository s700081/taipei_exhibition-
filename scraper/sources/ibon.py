"""
ibon 售票系統的「展覽」類別（多為需購票的特展、商品展、快閃展）。
列表來自 ibon 售票網的公開 API，地址與票價取自各活動售票頁的 JSON-LD。
"""

from __future__ import annotations

import re
import time

from .. import fetch, jsonld
from ..normalize import clean_text, detect_city, parse_date, parse_price, truncate

SOURCE_ID = "ibon"
SOURCE_NAME = "ibon售票 展覽"
SOURCE_URL = "https://ticket.ibon.com.tw/"
LIST_URL = "https://ticket.ibon.com.tw/api/Result/GetResultData"
DETAIL_URL = "https://ticket.ibon.com.tw/ActivityInfo/Details/{id}"

# 不是展覽的活動
_NOT_EXHIBITION = re.compile(r"(見面會|演唱會|音樂會|SOLO|LIVE|旅展|球賽|講座|課程|研習)", re.I)
# 博物館門票、套票等票券商品（展覽本身通常另有資料）
_TICKET_PRODUCT = re.compile(r"(參觀券|聯票|套票|好禮|語導|語音導覽|常設展全票|早鳥票|優惠票|優待票|展期全票|展期區間票)")
# 「台北．國立故宮博物院北院」這類只有場館名稱的門票
_CITY_PREFIX = re.compile(r"^(台北|臺北|新北|基隆|桃園|台中|臺中|台南|臺南|高雄|嘉義|屏東|宜蘭|花蓮|台東|臺東|新竹|苗栗|彰化|南投|雲林)．")
# 明顯在其他縣市的活動（省下讀取售票頁）
_ELSEWHERE = re.compile(r"(臺中|台中|臺南|台南|高雄|嘉義|屏東|宜蘭|花蓮|臺東|台東|新竹|苗栗|彰化|南投|雲林|澎湖|金門|奇美|駁二|通霄)")


def keep(item: dict) -> bool:
    title = clean_text(item.get("ActivityName"))
    place = clean_text(item.get("GameLocation"))
    if not title or _NOT_EXHIBITION.search(title) or _TICKET_PRODUCT.search(title):
        return False
    if _CITY_PREFIX.match(title) and "展" not in title:
        return False
    if title == place:
        return False
    return not _ELSEWHERE.search(f"{title} {place}")


def build_record(item: dict, event: dict | None) -> dict:
    event = event or {}
    location = event.get("location") or {}
    if isinstance(location, list):
        location = location[0] if location else {}
    address = location.get("address") or {}
    if isinstance(address, str):
        street, region = address, ""
    else:
        street, region = clean_text(address.get("streetAddress")), clean_text(address.get("addressRegion"))
    venue = clean_text(item.get("GameLocation")) or clean_text(location.get("name"))
    full_address = street or f"{region}{venue}"

    offers = event.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    low, high = offers.get("lowPrice", offers.get("price")), offers.get("highPrice", offers.get("price"))
    try:
        low, high = int(float(low)), int(float(high))
    except (TypeError, ValueError):
        low = high = None
    if low is None:
        price = parse_price("需購票，請見售票頁")
        price["free"] = False
    elif low == high == 0:
        price = parse_price("免費參觀")
    else:
        price = {"text": f"NT${low}" if low == high else f"NT${low}–{high}", "free": False,
                 "min": low, "max": high, "tickets": []}

    ticket = clean_text(item.get("GameTicketURL"))
    return {
        "source": SOURCE_ID,
        "city": detect_city(full_address, venue),
        "source_id": str(item.get("ActivityID")),
        "title": clean_text(item.get("ActivityName")),
        "venue": venue,
        "address": full_address,
        "lat": None,
        "lng": None,
        "start": parse_date(item.get("ActivitySDate")) or jsonld.to_date(event.get("startDate")),
        "end": parse_date(item.get("ActivityEDate")) or jsonld.to_date(event.get("endDate")),
        "price": price,
        "ticket_url": ticket if ticket.startswith("http") else None,
        "url": DETAIL_URL.format(id=item.get("ActivityID")),
        "image": clean_text(item.get("ActivityImageURL")) or None,
        "organizer": "",
        "description": truncate(event.get("description") or "", 160),
    }


def collect() -> list[dict]:
    resp = fetch.post_json(LIST_URL, {"CategoryCode": "exhibition", "PageIndex": 0, "PageSize": 200}, timeout=60)
    item = resp.get("Item")
    items = (item.get("Rows") or []) if isinstance(item, dict) else []
    records = []
    for item in items:
        if not keep(item):
            continue
        event = None
        url = clean_text(item.get("GameTicketURL"))
        if url.startswith("https://tour.ibon.com.tw/event/"):
            time.sleep(1)
            try:
                event = jsonld.first_of_type(fetch.get_text(url, timeout=60), "Event")
            except RuntimeError as e:
                print(f"  [{SOURCE_ID}] {url}: {e}")
        records.append(build_record(item, event))
    return records
