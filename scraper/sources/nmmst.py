"""國立海洋科技博物館（海科館，基隆）官網的「當期特展」。展期寫在連結標題中（民國年）。"""

from __future__ import annotations

import html
import re

from .. import fetch
from ..normalize import clean_text, parse_price, parse_zh_date_range

SOURCE_ID = "nmmst"
SOURCE_NAME = "國立海洋科技博物館"
SOURCE_URL = "https://www.nmmst.gov.tw/"
LIST_URL = "https://www.nmmst.gov.tw/chhtml/contentlist/221/0"
ADDRESS = "基隆市中正區北寧路367號"

_ITEM = re.compile(
    r"<a href='(https://www\.nmmst\.gov\.tw/chhtml/newsdetail/221/\d+/0)'\s*title='連至([^']*)'>(.*?)</a>", re.S
)
_RANGE = re.compile(r"^\s*(\d{2,4}/\d{1,2}/\d{1,2})\s*-\s*(\d{2,4}/\d{1,2}/\d{1,2})\s*(.+)$")
# 到校園巡迴的展覽不在館內
_SKIP = re.compile(r"巡迴")


def parse_list(page: str) -> list[dict]:
    records = []
    for m in _ITEM.finditer(page):
        label = clean_text(html.unescape(m.group(2)))
        r = _RANGE.match(label)
        if not r or _SKIP.search(label):
            continue
        start, end = parse_zh_date_range(f"{r.group(1)}至{r.group(2)}")
        img = re.search(r"<img[^>]+src='([^']+)'", m.group(3))
        records.append({
            "source": SOURCE_ID,
            "city": "基隆市",
            "source_id": m.group(1),
            "title": r.group(3).strip(),
            "venue": SOURCE_NAME,
            "address": ADDRESS,
            "lat": None,
            "lng": None,
            "start": start,
            "end": end,
            "price": parse_price(""),
            "url": m.group(1),
            "image": img.group(1) if img else None,
            "organizer": SOURCE_NAME,
            "description": "",
        })
    return records


def collect() -> list[dict]:
    # 官網連線偶爾被重設，多試幾次
    return parse_list(fetch.get_text(LIST_URL, timeout=60, retries=5))
