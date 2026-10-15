"""
國立臺灣科學教育館（科教館）官網的「特展」與「微型展」。
官網沒有開放資料，從列表頁取得展覽，再到各展覽頁讀取展期、展區與參觀資訊。
"""

from __future__ import annotations

import html
import re
import time

from .. import fetch
from ..normalize import clean_text, parse_date, parse_price, parse_zh_date_range, truncate

SOURCE_ID = "ntsec"
SOURCE_NAME = "國立臺灣科學教育館"
SOURCE_URL = "https://www.ntsec.gov.tw/"
SITE = "https://www.ntsec.gov.tw"
LIST_URL = SITE + "/article/list.aspx?a={a}"
TICKET_PAGE = SITE + "/article/detail.aspx?a=23"
# 列表頁代號：特展、微型展（常設展多為長年展示區，不收錄）
LISTS = ("25", "5904")

VENUE = "國立臺灣科學教育館"
ADDRESS = "臺北市士林區士商路189號"
# 票價頁讀取失敗時使用（115 年 1 月 1 日起的常設展票價）
DEFAULT_TICKETS = (120, 90)

_ITEM = re.compile(r'<a\s+href="(?P<href>[^"]+)"[^>]*class="message-item[^"]*"[^>]*>(?P<body>.*?)</a>', re.S)
_FIELD_END = r"(?=展覽日期|展覽期間|展覽時間|展覽地點|參觀資訊|觀展小提醒|指導單位|主辦單位|協辦單位|照片集|檔案下載|▼|$)"


def _text(fragment: str) -> str:
    fragment = re.sub(r"<script.*?</script>|<style.*?</style>", " ", fragment, flags=re.S)
    return clean_text(html.unescape(re.sub(r"<[^>]+>", " ", fragment)))


def _first(pattern: str, body: str) -> str:
    m = re.search(pattern, body, re.S)
    return _text(m.group(1)) if m else ""


def parse_list(page: str, list_id: str = "25") -> list[dict]:
    items = []
    for m in _ITEM.finditer(page):
        body = m.group("body")
        items.append({
            "list_url": LIST_URL.format(a=list_id),
            "href": html.unescape(m.group("href")),
            "title": _first(r'class="newsMessage-content"[^>]*>(.*?)</div>', body),
            "date": parse_date(_first(r"<p>(.*?)</p>", body)),
            "note": _first(r'class="message-annotation"[^>]*>(.*?)</div>', body),
            "image": (re.search(r'<img[^>]+src="([^"]+)"', body) or [None, None])[1],
        })
    return [i for i in items if i["title"]]


def parse_detail(page: str) -> dict:
    """讀取展覽頁的「展覽日期／地點／參觀資訊」與第一段介紹。"""
    start = page.find('<main id="main-content">')
    text = _text(page[start:] if start >= 0 else page)
    body = text.split("照片集")[0].split("展開網站導覽")[0]

    def field(label: str) -> str:
        m = re.search(r"(?:" + label + r")\s*[｜|:：]\s*(.*?)" + _FIELD_END, body)
        return m.group(1).strip() if m else ""

    intro = re.sub(r"^.*?最後更新日期\s*[:：]\s*\d{4}-\d{2}-\d{2}", "", body, count=1).strip()
    return {
        "dates": field(r"展覽(?:日期|期間)"),
        "place": field(r"(?:展覽)?地點"),
        "visit": field(r"展覽時間與參觀資訊|參觀資訊"),
        "intro": intro,
    }


def parse_ticket_prices(page: str) -> tuple[int, int] | None:
    """從票價總覽頁取出常設展全票、優待票價格。"""
    text = _text(page)
    m = re.search(r"常設展門票.{0,40}?全票\D{0,6}(\d+)\s*元.{0,20}?優待票\D{0,6}(\d+)\s*元", text)
    return (int(m.group(1)), int(m.group(2))) if m else None


def museum_ticket_price(full: int, concession: int) -> dict:
    return parse_price(f"憑科教館當日常設展或特展門票參觀；常設展全票{full}元；優待票{concession}元")


def build_record(item: dict, detail: dict | None, tickets: tuple[int, int]) -> dict:
    detail = detail or {}
    start, end = parse_zh_date_range(detail.get("dates"))
    note_start, note_end = parse_zh_date_range(item["note"])
    start = start or note_start or item["date"]
    end = end or note_end

    place = re.sub(r"^本館\s*", "", detail.get("place") or "")
    if not place and re.search(r"\d\s*F|樓|展區", item["note"]):
        place = item["note"]

    visit = detail.get("visit") or ""
    external = not item["href"].startswith(SITE)
    if external:
        price = parse_price("需另行購票，請見購票頁面")
        price.update({"free": False})
    elif "門票" in visit or not visit:
        price = museum_ticket_price(*tickets)
    elif re.search(r"免費|開放參觀", visit):
        price = parse_price("免費參觀")
    else:
        price = parse_price(visit)

    # 介紹開頭常重複標題與「展覽介紹」字樣
    intro = re.sub(r"^[★☆\s]+", "", detail.get("intro") or "")
    if intro.startswith(item["title"]):
        intro = intro[len(item["title"]):]
    intro = re.sub(r"^\s*(展覽介紹|展覽簡介)\s*", "", intro)

    return {
        "source": SOURCE_ID,
        "city": "臺北市",
        "source_id": (re.search(r"a=(\d+)", item["href"]) or [None, item["title"]])[1],
        "title": item["title"],
        "venue": f"{VENUE} {place}".strip(),
        "address": ADDRESS,
        "lat": None,
        "lng": None,
        "start": start,
        "end": end,
        "price": price,
        "url": item["href"] if not external else item.get("list_url", SOURCE_URL),
        "ticket_url": item["href"] if external else None,
        "image": item["image"],
        "organizer": VENUE,
        "description": truncate(intro or item["note"], 160),
    }


def collect() -> list[dict]:
    items: list[dict] = []
    for list_id in LISTS:
        items.extend(parse_list(fetch.get_text(LIST_URL.format(a=list_id), timeout=60), list_id))

    try:
        tickets = parse_ticket_prices(fetch.get_text(TICKET_PAGE, timeout=60)) or DEFAULT_TICKETS
    except RuntimeError:
        tickets = DEFAULT_TICKETS

    records, seen = [], set()
    for item in items:
        if item["href"] in seen:
            continue
        seen.add(item["href"])
        detail = None
        if item["href"].startswith(SITE + "/article/detail.aspx"):
            time.sleep(1)  # 對官網客氣一點
            try:
                detail = parse_detail(fetch.get_text(item["href"], timeout=60))
            except RuntimeError as e:
                print(f"  [ntsec] {item['href']}: {e}")
        records.append(build_record(item, detail, tickets))
    return records
