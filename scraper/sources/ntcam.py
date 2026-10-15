"""新北市美術館官網的展覽資料（目前展覽＋即將展出）。"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone

from .. import fetch
from ..normalize import clean_text, parse_price, truncate

SOURCE_ID = "ntcam"
SOURCE_NAME = "新北市美術館"
SOURCE_URL = "https://ntcart.museum/"
API_URL = "https://ntcart.museum/exhibition.aspx"
SITE = "https://ntcart.museum"
ADDRESS = "新北市鶯歌區館前路300號"
_TAIPEI_TZ = timezone(timedelta(hours=8))


def parse_ms_date(value) -> date | None:
    """把 .NET 的 /Date(1790956800000)/（UTC 毫秒）轉成台北日期。"""
    m = re.search(r"Date\((-?\d+)", str(value or ""))
    if not m:
        return None
    return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=_TAIPEI_TZ).date()


def parse(items: list[dict]) -> list[dict]:
    records = []
    for item in items:
        title = clean_text(item.get("ExName"))
        if not title:
            continue
        raw_cost = item.get("ExCost")
        cost = clean_text("" if raw_cost is None else str(raw_cost))
        if cost.isdigit():
            price = parse_price("免費參觀") if cost == "0" else parse_price(f"全票{cost}元")
        else:
            price = parse_price("")
        image = clean_text(item.get("ExListImg"))
        buy = clean_text(item.get("BuyLink"))
        records.append({
            "source": SOURCE_ID,
            "city": "新北市",
            "source_id": item.get("ExNo"),
            "title": title,
            "venue": clean_text(item.get("ExLocationTextTW")) or SOURCE_NAME,
            "address": ADDRESS,
            "lat": None,
            "lng": None,
            "start": parse_ms_date(item.get("ExDateSt")),
            "end": parse_ms_date(item.get("ExDateEn")),
            "price": price,
            "ticket_url": buy if buy.startswith("http") else None,
            "url": f"{SITE}/exhibition_content.aspx?id={item.get('ExNo')}",
            "image": f"{SITE}/retrieve/exhibition/{image}" if image else None,
            "organizer": SOURCE_NAME,
            "description": truncate(item.get("ContentDesc") or "", 160),
        })
    return records


def collect() -> list[dict]:
    resp = fetch.post_form(API_URL, {"q": "get", "data": json.dumps({"p": 1, "ps": 100, "Kind": ""})}, timeout=60)
    items = (resp.get("list") or {}).get("items", []) + (resp.get("future_list") or {}).get("items", [])
    return parse(items)
