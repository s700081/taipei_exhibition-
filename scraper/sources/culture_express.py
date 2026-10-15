"""
臺北市政府文化局「臺北文化快遞」活動開放資料（臺北市資料大平臺 dataset 9a7af75b-9abd-4ac1-b359-685fbd7dac23）。
"""

from __future__ import annotations

import re

from .. import fetch
from ..normalize import clean_text, parse_date, parse_float, parse_price, truncate

SOURCE_ID = "culture_express"
SOURCE_NAME = "臺北市文化局 臺北文化快遞"
SOURCE_URL = "https://cultureexpress.taipei/"
API_URL = "https://cultureexpress.taipei/OpenData/Event/C000003"
DETAIL_URL = "https://cultureexpress.taipei/Event/C000003?ID={id}&PageType=1"

# 「展覽」類別中偶爾混入徵件、比賽公告
_NOT_EXHIBITION = re.compile(r"(徵件|徵選|徵稿|甄選|募集|報名|比賽|競賽|大賽|贊助計畫|獎助計畫)")
# 臺北單位主辦、但在國外展出的展覽
_ABROAD = re.compile(r"(威尼斯|義大利|海外|國外)")


def _price(ticket_type: str, ticket_price: str) -> dict:
    text = clean_text(ticket_price)
    if re.fullmatch(r"\d+", text):
        text = f"NT${text}"
    if ticket_type == "免費":
        parsed = parse_price(text)
        if parsed["min"] is not None:
            return parsed
        return parse_price("免費參觀")
    if ticket_type == "售票":
        parsed = parse_price(text, assume_currency=True)
        if parsed["min"] is None:
            parsed.update({"text": text or "需購票，請見官網", "free": False})
        return parsed
    return parse_price(text)


def _http(value) -> str | None:
    value = clean_text(value)
    return value if value.startswith("http") else None


def parse(items: list[dict]) -> list[dict]:
    records = []
    for item in items:
        if item.get("Category") != "展覽" or item.get("City") != "臺北市":
            continue
        title = clean_text(item.get("Caption"))
        if not title or (_NOT_EXHIBITION.search(title) and "展" not in title):
            continue
        venue = clean_text(item.get("Venue"))
        if _ABROAD.search(venue) or _ABROAD.search(clean_text(item.get("TicketPrice"))):
            continue
        if not venue or venue.startswith("http"):
            venue = clean_text(item.get("Company"))
        area = clean_text(item.get("Area") or item.get("Address"))
        lat, lng = parse_float(item.get("Latitude")), parse_float(item.get("Longitude"))
        if not lat or not lng:
            lat = lng = None
        records.append({
            "source": SOURCE_ID,
            "city": "臺北市",
            "source_id": item.get("ID"),
            "title": title,
            "venue": venue,
            "address": f"臺北市{area}" if area and "臺北市" not in area else area or "臺北市",
            "lat": lat,
            "lng": lng,
            "start": parse_date(item.get("StartDate")),
            "end": parse_date(item.get("EndDate")),
            "price": _price(clean_text(item.get("TicketType")), item.get("TicketPrice")),
            "ticket_url": _http(item.get("TicketPurchaseLink")),
            "url": _http(item.get("WebsiteLink")) or DETAIL_URL.format(id=item.get("ID")),
            "image": _http(item.get("ImageFile")),
            "organizer": clean_text(item.get("Company")),
            "description": truncate(item.get("Introduction") or "", 160),
        })
    return records


def collect() -> list[dict]:
    return parse(fetch.get_json(API_URL, timeout=120))
