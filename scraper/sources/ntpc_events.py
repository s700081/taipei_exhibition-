"""
新北市政府「近期活動」開放資料（新北市政府資料開放平臺 dataset 029e3fc2-1927-4534-8702-da7323be969b）。
資料沒有展覽分類，只收標題含「展」的活動，並排除書展、講座等。
"""

from __future__ import annotations

import re
from datetime import date, datetime

from .. import fetch
from ..normalize import clean_text, parse_price, truncate

SOURCE_ID = "ntpc_events"
SOURCE_NAME = "新北市政府 近期活動"
SOURCE_URL = "https://data.ntpc.gov.tw/datasets/029e3fc2-1927-4534-8702-da7323be969b"
API_URL = "https://data.ntpc.gov.tw/api/datasets/029e3fc2-1927-4534-8702-da7323be969b/json?page={page}&size=1000"

_EXCLUDE = re.compile(r"(書展|徵件|徵選|徵稿|報名|講座|課程|研習|展演|發展|展開|展現|拓展|延展|展望|展售)")


def _mdy(value: str | None) -> date | None:
    try:
        return datetime.strptime(clean_text(value), "%m/%d/%Y").date()
    except ValueError:
        return None


def parse(items: list[dict]) -> list[dict]:
    records = []
    for item in items:
        title = clean_text(item.get("title"))
        if "展" not in title or _EXCLUDE.search(title):
            continue
        address = clean_text(item.get("address"))
        if address and "新北市" not in address:
            address = f"新北市{address}"
        pics = [p.strip() for p in re.split(r"[、,\s]+", clean_text(item.get("picUrl"))) if p.strip().startswith("http")]
        url = clean_text(item.get("aboutUrl"))
        records.append({
            "source": SOURCE_ID,
            "city": "新北市",
            "source_id": str(item.get("id") or title),
            "title": title,
            "venue": clean_text(item.get("place")),
            "address": address or "新北市",
            "lat": None,
            "lng": None,
            "start": _mdy(item.get("activeDate")),
            "end": _mdy(item.get("activeEndDate")),
            "price": parse_price(item.get("money")),
            "url": url if url.startswith("http") else None,
            "image": pics[0] if pics else None,
            "organizer": clean_text(item.get("author")),
            "description": truncate(item.get("description") or "", 160),
        })
    return records


def collect() -> list[dict]:
    items: list[dict] = []
    for page in range(10):  # 每頁 1000 筆，空陣列代表結束
        batch = fetch.get_json(API_URL.format(page=page), timeout=60)
        if not batch:
            break
        items.extend(batch)
    return parse(items)
