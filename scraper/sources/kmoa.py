"""基隆美術館官網的「當期展覽」（列表頁＋各展覽頁的檔期、地點、費用）。"""

from __future__ import annotations

import html
import re
import time

from .. import fetch
from ..normalize import clean_text, parse_price, parse_zh_date_range, truncate

SOURCE_ID = "kmoa"
SOURCE_NAME = "基隆美術館"
SOURCE_URL = "https://kmoa.klcg.gov.tw/"
SITE = "https://kmoa.klcg.gov.tw/"
LIST_URL = SITE + "News_Photo.aspx?n=7484&sms=12489"
ADDRESS = "基隆市中正區信一路181號"

_LINK = re.compile(r'<a\s+href="(News_Photo_Content\.aspx\?n=7484&(?:amp;)?s=\d+)"[^>]*title="([^"]*)"')


def _text(fragment: str) -> str:
    return clean_text(html.unescape(re.sub(r"<[^>]+>", " ", fragment)))


def parse_list(page: str) -> list[dict]:
    items, seen = [], set()
    for m in _LINK.finditer(page):
        href = html.unescape(m.group(1))
        if href in seen:
            continue
        seen.add(href)
        rest = page[m.end(): m.end() + 4000]
        img = re.search(r'<img[^>]+src="([^"]+)"', rest)
        para = re.search(r'<div class="p">\s*<p>(.*?)</p>', rest, re.S)
        items.append({
            "url": SITE + href,
            "title": clean_text(html.unescape(m.group(2))),
            "image": img.group(1) if img else None,
            "summary": _text(para.group(1)) if para else "",
        })
    return items


def parse_detail(page: str) -> dict:
    """展覽頁以 title="欄位名稱" 的區塊呈現檔期時間(起)/(訖)、地點、費用。"""
    fields = {}
    for m in re.finditer(r'title="([^"]{1,12})"[^>]*>\s*<div class="essay">.*?<div class="p">(.*?)</div>', page, re.S):
        fields.setdefault(m.group(1), _text(m.group(2)))
    return fields


def build_record(item: dict, fields: dict) -> dict:
    start, _ = parse_zh_date_range(fields.get("檔期時間(起)", ""))
    end, _ = parse_zh_date_range(fields.get("檔期時間(訖)", ""))
    place = fields.get("地點") or SOURCE_NAME
    return {
        "source": SOURCE_ID,
        "city": "基隆市",
        "source_id": item["url"],
        "title": item["title"],
        "venue": place if "基隆" in place else f"{SOURCE_NAME} {place}",
        "address": ADDRESS,
        "lat": None,
        "lng": None,
        "start": start,
        "end": end,
        "price": parse_price(fields.get("費用", "")),
        "url": item["url"],
        "image": item["image"],
        "organizer": SOURCE_NAME,
        "description": truncate(item["summary"], 160),
    }


def collect() -> list[dict]:
    records = []
    for item in parse_list(fetch.get_text(LIST_URL, timeout=60)):
        time.sleep(1)
        try:
            fields = parse_detail(fetch.get_text(item["url"], timeout=60))
        except RuntimeError as e:
            print(f"  [{SOURCE_ID}] {item['url']}: {e}")
            continue
        records.append(build_record(item, fields))
    return records
