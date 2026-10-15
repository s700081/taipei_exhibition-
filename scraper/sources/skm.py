"""
新光三越官網的「文藝」與「展售」活動（店內的藝術展、快閃展、商品展）。
列表頁沒有日期，日期與圖片取自各活動頁的 JSON-LD。活動中混有大量促銷訊息，以標題篩選。
"""

from __future__ import annotations

import html
import math
import re
import time

from .. import fetch, jsonld
from ..normalize import clean_text, parse_price, truncate

SOURCE_ID = "skm"
SOURCE_NAME = "新光三越"
SOURCE_URL = "https://www.skm.com.tw/"
LIST_URL = "https://www.skm.com.tw/page_list/0/New?category_id={category}&page={page}"
CATEGORIES = ("9", "12")  # 9 = 文藝，12 = 展售
PAGE_SIZE = 12

# 北北基桃的分店：(縣市, 地址)
STORES = {
    "台北信義新天地": ("臺北市", "臺北市信義區松高路12號"),
    "台北站前店": ("臺北市", "臺北市中正區忠孝西路一段66號"),
    "台北南西店": ("臺北市", "臺北市中山區南京西路12號"),
    "台北天母店": ("臺北市", "臺北市士林區天母東路68號"),
    "台北車站": ("臺北市", "臺北市中正區北平西路3號"),
    "桃園站前店": ("桃園市", "桃園市桃園區中正路19號"),
}
# 信義新天地各館地址（標題常寫「A11 3F」）
XINYI_BUILDINGS = {
    "A4": "臺北市信義區松壽路19號",
    "A8": "臺北市信義區松高路12號",
    "A9": "臺北市信義區松壽路9號",
    "A11": "臺北市信義區松壽路11號",
}

_CARD = re.compile(
    r'<span class="building">(.*?)</span>.*?class="promotion-title"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S
)
_INCLUDE = re.compile(r"(展|快閃|POP[ -]?UP|藝術|主題店|期間限定)", re.I)
_EXCLUDE = re.compile(r"(展售會|週年慶|優惠|大賞|特賣|滿額|折扣|家電|場地資訊|集結|美食|會員|抽獎)")


def _text(fragment: str) -> str:
    return clean_text(html.unescape(re.sub(r"<[^>]+>", " ", fragment)))


def parse_list(page: str) -> list[dict]:
    cards, seen = [], set()
    for m in _CARD.finditer(page):
        url = html.unescape(m.group(2)).split("?")[0]
        if url in seen:
            continue
        seen.add(url)
        cards.append({"store": _text(m.group(1)), "url": url, "title": _text(m.group(3))})
    return cards


def page_count(page: str) -> int:
    m = re.search(r"page_total_rcnt\s*=\s*[\"']?(\d+)", page)
    return max(1, math.ceil(int(m.group(1)) / PAGE_SIZE)) if m else 1


def keep(card: dict) -> bool:
    return card["store"] in STORES and bool(_INCLUDE.search(card["title"])) and not _EXCLUDE.search(card["title"])


def build_record(card: dict, event: dict | None) -> dict:
    event = event or {}
    city, address = STORES[card["store"]]
    title = clean_text(event.get("name")) or card["title"]
    desc = clean_text(event.get("description"))
    venue = f"新光三越{card['store']}"
    if card["store"] == "台北信義新天地":
        m = re.search(r"(?<![A-Za-z0-9])A(4|8|9|11)(?![0-9])", f"{title} {desc}")
        if m:
            venue += f"A{m.group(1)}"
            address = XINYI_BUILDINGS[f"A{m.group(1)}"]
    floor = re.search(r"(?<![A-Za-z0-9])(B?\d{1,2})\s*F(?![A-Za-z])", f"{title} {desc}")
    if floor:
        venue += f" {floor.group(1)}F"
    image = event.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    return {
        "source": SOURCE_ID,
        "city": city,
        "source_id": card["url"],
        "title": title,
        "venue": venue,
        "address": address,
        "lat": None,
        "lng": None,
        "start": jsonld.to_date(event.get("startDate")),
        "end": jsonld.to_date(event.get("endDate")),
        # 百貨公司店內的展覽與快閃店一般免費入場
        "price": parse_price("免費入場"),
        "url": card["url"],
        "image": image if isinstance(image, str) and image.startswith("http") else None,
        "organizer": SOURCE_NAME,
        "description": truncate(desc, 160),
    }


def collect() -> list[dict]:
    cards: list[dict] = []
    for category in CATEGORIES:
        first = fetch.get_text(LIST_URL.format(category=category, page=1), timeout=60)
        cards.extend(parse_list(first))
        for page in range(2, min(page_count(first), 10) + 1):
            time.sleep(1)
            cards.extend(parse_list(fetch.get_text(LIST_URL.format(category=category, page=page), timeout=60)))

    records, seen = [], set()
    for card in cards:
        if card["url"] in seen or not keep(card):
            continue
        seen.add(card["url"])
        time.sleep(1)
        try:
            event = jsonld.first_of_type(fetch.get_text(card["url"], timeout=60), "Event")
        except RuntimeError as e:
            print(f"  [{SOURCE_ID}] {card['url']}: {e}")
            continue
        rec = build_record(card, event)
        if rec["start"] or rec["end"]:
            records.append(rec)
    return records
