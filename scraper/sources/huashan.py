"""
華山1914文化創意產業園區官網的展覽。

官網的 robots.txt 不允許帶查詢字串的網址（例如 /exhibition?page=2）與 /api/，
所以從允許的 sitemap 取得目前活動的網址（新版網址不以 event- 開頭，舊網址是歷史資料），
再讀取各活動頁內嵌的 Nuxt 資料（__NUXT_DATA__），只收錄類別為「展覽」的活動。
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone

from .. import fetch
from ..normalize import clean_text, parse_price, truncate

SOURCE_ID = "huashan"
SOURCE_NAME = "華山1914文化創意產業園區"
SOURCE_URL = "https://www.huashan1914.com/"
SITEMAP_URL = "https://www.huashan1914.com/__sitemap__/zh-TW-main.xml"
ADDRESS = "臺北市中正區八德路一段1號"
EXHIBITION_CATEGORY = "展覽"
MAX_PAGES = 60  # 每週最多讀取的活動頁數
_TAIPEI_TZ = timezone(timedelta(hours=8))


def current_event_urls(sitemap: str) -> list[str]:
    urls = []
    for loc in re.findall(r"<loc>(https://www\.huashan1914\.com/exhibition/[^<]+)</loc>", sitemap):
        slug = urllib.parse.unquote(loc.split("/exhibition/", 1)[1])
        if not slug.startswith("event-") and loc not in urls:
            urls.append(html.unescape(loc))
    return urls


def nuxt_data(page: str) -> list:
    m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    return json.loads(m.group(1)) if m else []


def _resolve(data: list, ref, depth: int = 0):
    """把 Nuxt（devalue）以索引互相參照的陣列還原成一般的 dict / list。"""
    if not isinstance(ref, int) or ref < 0 or ref >= len(data) or depth > 12:
        return ref if not isinstance(ref, int) else None
    value = data[ref]
    if isinstance(value, list):
        if len(value) == 2 and isinstance(value[0], str) and value[0] in ("Reactive", "ShallowReactive", "Ref", "ShallowRef"):
            return _resolve(data, value[1], depth + 1)
        return [_resolve(data, v, depth + 1) for v in value]
    if isinstance(value, dict):
        return {k: _resolve(data, v, depth + 1) for k, v in value.items()}
    return value


def _utc_to_date(value) -> date | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(_TAIPEI_TZ).date()


def parse_event(page: str, url: str) -> dict | None:
    """解析活動頁；不是展覽或缺少資料時回傳 None。"""
    data = nuxt_data(page)
    if not data:
        return None
    # 類別、場地的 id → 名稱
    names = {}
    for value in data:
        if isinstance(value, dict) and "categoryId" in value and "name" in value and "id" in value:
            cid, name = data[value["id"]], data[value["name"]]
            if isinstance(cid, str) and isinstance(name, str):
                names[cid] = name

    slug = urllib.parse.unquote(url.split("/exhibition/", 1)[1])
    event = None
    for i, value in enumerate(data):
        if isinstance(value, dict) and "article" in value and "aside" in value:
            wrapper = _resolve(data, i)
            article = wrapper.get("article") or {}
            if (article.get("default") or {}).get("slug") == slug:
                event = wrapper
                break
    if not event:
        return None

    aside = event.get("aside") or {}
    categories = [names.get(c, "") for c in aside.get("category_event_category") or []]
    if EXHIBITION_CATEGORY not in categories:
        return None
    article = event["article"]
    content = article.get("event_content") or {}
    when = article.get("event_time") or {}
    sidebar = article.get("sidebar_info") or {}

    description = clean_text(content.get("description"))
    venues = [clean_text(names.get(v, "")) for v in aside.get("category_event_venue") or []]
    venues = [v for v in venues if v]
    price_text = ""
    m = re.search(r"(?:票價|入場方式|門票|費用)\s*[｜|:：]\s*(.{1,60}?)(?=\s(?:[^\s｜|:：]{2,6}\s*[｜|:：])|$)", description)
    if m:
        # 截到下一個「標籤｜」之前，例如「免費入場 《光華雜誌》官網｜…」只取「免費入場」
        price_text = re.split(r"\s+(?=\S*[｜|:：])", m.group(1).strip())[0]
    images = content.get("hero_img") or content.get("square_hero_image") or []
    image = images[0].get("path") if images and isinstance(images[0], dict) else None
    ticket = clean_text(sidebar.get("ticket_link"))

    return {
        "source": SOURCE_ID,
        "city": "臺北市",
        "source_id": slug,
        "title": clean_text((article.get("default") or {}).get("title")) or slug,
        "venue": f"{SOURCE_NAME} {'、'.join(venues)}".strip(),
        "address": ADDRESS,
        "lat": None,
        "lng": None,
        "start": _utc_to_date(when.get("start_date")),
        "end": _utc_to_date(when.get("end_date")),
        "price": parse_price(price_text),
        "ticket_url": ticket if ticket.startswith("http") else None,
        "url": url,
        "image": urllib.parse.quote(image, safe=":/") if image else None,
        "organizer": clean_text(sidebar.get("organizer")) or SOURCE_NAME,
        "description": truncate(description, 160),
    }


def collect() -> list[dict]:
    urls = current_event_urls(fetch.get_text(SITEMAP_URL, timeout=120))
    records = []
    for url in urls[:MAX_PAGES]:
        time.sleep(1)  # 對官網客氣一點
        try:
            rec = parse_event(fetch.get_text(url, timeout=60), url)
        except RuntimeError as e:
            print(f"  [{SOURCE_ID}] {url}: {e}")
            continue
        if rec:
            records.append(rec)
    return records
