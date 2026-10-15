"""讀取網頁中的 JSON-LD（schema.org）結構化資料。"""

from __future__ import annotations

import html
import json
import re
from datetime import date, datetime, timedelta, timezone

_TAIPEI_TZ = timezone(timedelta(hours=8))


def blocks(page: str) -> list[dict]:
    """回傳頁面中所有 JSON-LD 物件（@graph 與陣列會攤平）。"""
    found: list[dict] = []
    for m in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(html.unescape(m.group(1).strip()))
        except json.JSONDecodeError:
            continue
        stack = data if isinstance(data, list) else [data]
        for item in stack:
            if isinstance(item, dict) and "@graph" in item:
                found.extend(x for x in item["@graph"] if isinstance(x, dict))
            elif isinstance(item, dict):
                found.append(item)
    return found


def first_of_type(page: str, type_name: str) -> dict | None:
    for block in blocks(page):
        t = block.get("@type")
        if t == type_name or (isinstance(t, list) and type_name in t):
            return block
    return None


def to_date(value) -> date | None:
    """ISO 日期時間轉台北日期；含時區（Z 或 +08:00）時換算成台北時間。"""
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
    if dt.tzinfo is not None:
        dt = dt.astimezone(_TAIPEI_TZ)
    return dt.date()
