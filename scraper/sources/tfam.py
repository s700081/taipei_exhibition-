"""臺北市立美術館官網的展覽資料（目前展覽＋即將展出）。"""

from __future__ import annotations

from .. import fetch
from ..normalize import clean_text, parse_date, parse_price, truncate

SOURCE_ID = "tfam"
SOURCE_NAME = "臺北市立美術館"
SOURCE_URL = "https://www.tfam.museum/"
API_URL = "https://www.tfam.museum/ashx/Exhibition.ashx?ddlLang=zh-tw"
SITE = "https://www.tfam.museum"

VENUE = "臺北市立美術館"
ADDRESS = "臺北市中山區中山北路三段181號"
# 官網展覽資料沒有票價欄位；北美館一般展覽採單一門票
PRICE_TEXT = "全票 NT$30（優待及免費資格請見官網）"

TYPE_CURRENT, TYPE_UPCOMING = "1", "2"


def _detail_url(item: dict) -> str:
    link = clean_text(item.get("ExternalLink"))
    if str(item.get("ShowStyle")) == "2" and link.startswith("http") and link != "https://":
        return link
    page = "Exhibition_Special.aspx" if str(item.get("IsSpecial")) == "1" else "Exhibition_page.aspx"
    return f"{SITE}/Exhibition/{page}?ddlLang=zh-tw&id={item.get('ExID')}"


def parse(items: list[dict]) -> list[dict]:
    records = []
    for item in items:
        title = clean_text(item.get("ExName"))
        room = clean_text(item.get("Area"))
        # 沒有展場（線上計畫）或在海外展出（如威尼斯雙年展台灣館）的不收錄
        if not title or not room or any(w in room for w in ("威尼斯", "義大利", "海外", "國外")):
            continue
        image = clean_text(item.get("NowPlayImg")).replace("\\", "/")
        records.append({
            "source": SOURCE_ID,
            "city": "臺北市",
            "source_id": str(item.get("ExID")),
            "title": title,
            "venue": f"{VENUE} {room}",
            "address": ADDRESS,
            "lat": None,
            "lng": None,
            "start": parse_date(item.get("BeginDate")),
            "end": parse_date(item.get("EndDate")),
            "price": parse_price(PRICE_TEXT),
            "url": _detail_url(item),
            "image": f"{SITE}/File/{image}" if image else None,
            "organizer": VENUE,
            "description": truncate(item.get("Content") or "", 160),
        })
    return records


def collect() -> list[dict]:
    items: list[dict] = []
    for ex_type in (TYPE_CURRENT, TYPE_UPCOMING):
        resp = fetch.post_json(API_URL, {"JJMethod": "GetEx", "Type": ex_type}, timeout=60)
        if str(resp.get("Status")) != "1":
            raise RuntimeError(f"TFAM API 回傳狀態 {resp.get('Status')}")
        items.extend(resp.get("Data") or [])
    return parse(items)
