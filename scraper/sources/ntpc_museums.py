"""
新北市立博物館的展覽 RSS（鶯歌陶瓷博物館、十三行博物館、淡水古蹟博物館）。
展期寫在 description（例如「展覽日期：2026年7月31日至2026年12月27日」），
<enddate> 則是結束日的隔天。
"""

from __future__ import annotations

import html
import re
from datetime import date, timedelta

from .. import fetch
from ..normalize import clean_text, parse_date, parse_price, parse_zh_date_range, truncate

SOURCE_ID = "ntpc_museums"
SOURCE_NAME = "新北市立博物館（鶯歌陶瓷、十三行、淡水古蹟）"
SOURCE_URL = "https://www.museum.ntpc.gov.tw/"

FEEDS = (
    ("新北市立鶯歌陶瓷博物館", "新北市鶯歌區文化路200號",
     "https://www.ceramics.ntpc.gov.tw/xmdoc/rss?xsmsid=0J148497613881029302"),
    ("新北市立十三行博物館", "新北市八里區博物館路200號",
     "https://www.sshm.ntpc.gov.tw/xmdoc/rss?xsmsid=0G244541084921596757"),
    ("新北市立淡水古蹟博物館", "新北市淡水區中正路28巷1號",
     "https://www.tshs.ntpc.gov.tw/xmdoc/rss?xsmsid=0G245656224351531469"),
)

# 徵件簡章、報名等公告不是展覽
_NOT_EXHIBITION = re.compile(r"(簡章|徵件|徵選|報名|招募|甄選)")


def _tag(item: str, name: str) -> str:
    m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", item, re.S)
    if not m:
        return ""
    value = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", m.group(1), flags=re.S)
    return clean_text(html.unescape(value))


def parse_feed(xml: str, museum: str, address: str) -> list[dict]:
    records = []
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
        title = _tag(item, "title")
        if not title or _NOT_EXHIBITION.search(title):
            continue
        desc = _tag(item, "description")
        m = re.search(r"展覽(?:日期|時間|期間)\s*[:：]?\s*(.{6,60})", desc)
        start, end = parse_zh_date_range(m.group(1) if m else "")
        if end is None:
            end_next = parse_date(_tag(item, "enddate"))
            end = end_next - timedelta(days=1) if end_next else None
        if start is None and end is None:
            continue  # 沒有展期（常設體驗、劇場等）無法判斷是否近期
        place = re.search(r"展覽地點\s*[:：]\s*(\S+(?:\s\S+)?)", desc)
        venue = place.group(1) if place else museum
        if museum not in venue and not venue.startswith("新北市立"):
            venue = f"{museum} {venue}"
        link = html.unescape(_tag(item, "link"))
        records.append({
            "source": SOURCE_ID,
            "city": "新北市",
            "source_id": link or title,
            "title": title,
            "venue": venue,
            "address": address,
            "lat": None,
            "lng": None,
            "start": start,
            "end": end,
            "price": parse_price(""),
            "url": link if link.startswith("http") else None,
            "image": None,
            "organizer": museum,
            "description": truncate(re.sub(r"^.*?展覽地點\s*[:：]\s*\S+(?:\s\S+)?\s*", "", desc), 160),
        })
    return records


def collect() -> list[dict]:
    records, errors = [], []
    for museum, address, url in FEEDS:
        try:
            records.extend(parse_feed(fetch.get_text(url, timeout=60), museum, address))
        except RuntimeError as e:
            errors.append(f"{museum}: {e}")
            print(f"  [{SOURCE_ID}] {museum}: {e}")
    if errors and not records:
        raise RuntimeError("; ".join(errors))
    return records
