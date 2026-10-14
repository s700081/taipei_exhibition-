"""
文化部「文化資料開放服務網」藝文活動開放資料（類別 6：展覽）。
資料說明：https://cloud.culture.tw/frontsite/opendata/activityOpenDataJsonAction.do
"""

from __future__ import annotations

from .. import fetch
from ..normalize import clean_text, parse_date, parse_float, parse_price, truncate

SOURCE_ID = "moc"
SOURCE_NAME = "文化部文化資料開放服務網"
SOURCE_URL = "https://cloud.culture.tw/"
API_URL = "https://cloud.culture.tw/frontsite/trans/SearchShowAction.do?method=doFindTypeJ&category=6"
DETAIL_URL = "https://cloud.culture.tw/frontsite/inquiry/eventInquiryAction.do?method=showEventDetail&uid={uid}"


def fetch_raw() -> list[dict]:
    return fetch.get_json(API_URL, timeout=120)


def parse(items: list[dict]) -> list[dict]:
    """把 API 回傳轉成共用格式；每個 showInfo（場次地點）各自成為一筆。"""
    records = []
    for item in items:
        uid = item.get("UID") or ""
        title = clean_text(item.get("title"))
        if not title:
            continue
        url = (
            clean_text(item.get("sourceWebPromote"))
            or clean_text(item.get("webSales"))
            or DETAIL_URL.format(uid=uid)
        )
        organizer = "、".join(clean_text(u) for u in item.get("masterUnit") or [] if clean_text(u))
        start_all = parse_date(item.get("startDate"))
        end_all = parse_date(item.get("endDate"))

        for idx, show in enumerate(item.get("showInfo") or []):
            start = parse_date(show.get("time")) or start_all
            end = parse_date(show.get("endTime")) or end_all
            # showInfo 的時間有時只是單一場次，以活動整體期間為主
            if start_all and end_all:
                start, end = min(filter(None, [start, start_all])), max(filter(None, [end, end_all]))
            records.append({
                "source": SOURCE_ID,
                "source_id": f"{uid}-{idx}",
                "title": title,
                "venue": clean_text(show.get("locationName")),
                "address": clean_text(show.get("location")),
                "lat": parse_float(show.get("latitude")),
                "lng": parse_float(show.get("longitude")),
                "start": start,
                "end": end,
                "price": parse_price(show.get("price"), show.get("onSales")),
                "url": url if url.startswith("http") else DETAIL_URL.format(uid=uid),
                "image": clean_text(item.get("imageUrl")) or None,
                "organizer": organizer or clean_text(item.get("showUnit")),
                "description": truncate(item.get("descriptionFilterHtml") or "", 160),
            })
    return records


def collect() -> list[dict]:
    return parse(fetch_raw())
