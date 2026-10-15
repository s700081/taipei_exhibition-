"""
Accupass 活動通：以關鍵字「快閃」搜尋北北基桃的實體活動，收錄快閃展、主題展等。
搜尋結果沒有地址，地址與展期取自各活動頁的 JSON-LD；Accupass 沒有提供票價。
"""

from __future__ import annotations

import re
import time

from .. import fetch, jsonld
from ..normalize import CITIES, clean_text, detect_city, parse_price, to_tai, truncate

SOURCE_ID = "accupass"
SOURCE_NAME = "Accupass 活動通（快閃展）"
SOURCE_URL = "https://www.accupass.com/"
SEARCH_URL = "https://api.accupass.com/v3/search/SearchEvents"
EVENT_URL = "https://www.accupass.com/event/{id}"
KEYWORDS = ("快閃",)
CITY_CODES = ["1", "2", "3", "15"]  # 臺北、新北、桃園、基隆
MAX_PAGES = 4  # 每頁 25 筆

_INCLUDE = re.compile(r"(展|快閃|POP[ -]?UP)", re.I)
_EXCLUDE = re.compile(r"(講座|課程|工作坊|分享會|徵件|招募|市集|派對|演唱|音樂會|見面會|路跑|場地|租借|出租|賞屋|報名活動)")


def split_address(raw: str) -> tuple[str, str]:
    """「台灣台北市灰棚｜中山區中山北路二段59巷16號B1」→（場館「灰棚」, 地址「臺北市中山區…」）。"""
    text = to_tai(clean_text(raw)).replace("臺灣", "", 1).strip()
    if "｜" in text or "|" in text:
        head, street = re.split(r"[｜|]", text, maxsplit=1)
        city = next((c for c in CITIES if head.startswith(c)), "")
        venue = head[len(city):].strip()
        street = street.strip()
        return venue, street if any(street.startswith(c) for c in CITIES) else f"{city}{street}"
    return "", text


def build_record(item: dict, event: dict | None) -> dict:
    event = event or {}
    location = event.get("location") or {}
    if isinstance(location, list):
        location = location[0] if location else {}
    address_raw = location.get("address")
    if isinstance(address_raw, dict):
        address_raw = " ".join(str(v) for k, v in address_raw.items() if not k.startswith("@"))
    venue, address = split_address(address_raw or "")
    if not venue:
        name = clean_text(location.get("name"))
        venue = "" if re.fullmatch(r"[（(].*[）)]", name) else name
    organizer = event.get("organizer") or {}
    if isinstance(organizer, list):
        organizer = organizer[0] if organizer else {}
    event_id = clean_text(item.get("eventIdNumber"))
    return {
        "source": SOURCE_ID,
        "city": detect_city(address, venue),
        "source_id": event_id,
        "title": clean_text(event.get("name")) or clean_text(item.get("name")),
        "venue": venue,
        "address": address,
        "lat": None,
        "lng": None,
        "start": jsonld.to_date(event.get("startDate") or item.get("startDateTime")),
        "end": jsonld.to_date(event.get("endDate") or item.get("endDateTime")),
        "price": parse_price(""),
        "url": EVENT_URL.format(id=event_id),
        "image": clean_text(item.get("photoUrl")) or None,
        "organizer": clean_text(organizer.get("name")) if isinstance(organizer, dict) else "",
        "description": truncate(event.get("description") or "", 160),
    }


def keep(item: dict) -> bool:
    title = clean_text(item.get("name"))
    return (item.get("eventPlaceType") in (None, "Offline") and bool(_INCLUDE.search(title))
            and not _EXCLUDE.search(title))


def collect() -> list[dict]:
    items, seen = [], set()
    for keyword in KEYWORDS:
        for page in range(MAX_PAGES):
            payload = {"categoryTypeList": [], "simpleEventPlaceTypeList": ["1"], "cityLocationList": CITY_CODES,
                       "sortBy": "4", "timeType": "0", "keyword": keyword, "currentIndex": page}
            resp = fetch.post_json(SEARCH_URL, payload, timeout=60)
            batch = resp.get("items") or []
            for item in batch:
                if item.get("eventIdNumber") not in seen:
                    seen.add(item.get("eventIdNumber"))
                    items.append(item)
            if len(batch) < 25:
                break
            time.sleep(1)

    records = []
    for item in items:
        if not keep(item):
            continue
        time.sleep(1)
        try:
            page = fetch.get_text(EVENT_URL.format(id=item["eventIdNumber"]), timeout=60)
            event = jsonld.first_of_type(page, "Event")
        except RuntimeError as e:
            print(f"  [{SOURCE_ID}] {item.get('eventIdNumber')}: {e}")
            event = None
        records.append(build_record(item, event))
    return records
