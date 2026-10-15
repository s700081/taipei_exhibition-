"""
抓取北北基桃（臺北市、新北市、基隆市、桃園市）近期展覽並輸出 site/data/exhibitions.json。

用法：
  python -m scraper.main                  # 一般執行
  python -m scraper.main --offline-geocode  # 不連線 Nominatim，只用對照表與快取
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from .geocode import Geocoder
from .normalize import CITIES, detect_city, detect_topics, now_taipei, title_key, to_tai
from .sources import SOURCES

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "site" / "data" / "exhibitions.json"
VENUES_PATH = ROOT / "scraper" / "data" / "venues.json"
CACHE_PATH = ROOT / "scraper" / "data" / "geocode_cache.json"

PRECISION_RANK = {"source": 0, "venue": 0, "address": 1, "road": 2, "district": 3, "none": 4}


# 只在網路上展出、沒有實體地點的展覽
_ONLINE_ONLY = re.compile(r"線上(攝影|藝術|特|策)?展")


def in_window(rec: dict, today: date, days_ahead: int) -> bool:
    start, end = rec.get("start"), rec.get("end")
    if end and end < today:
        return False
    if start and start > today + timedelta(days=days_ahead):
        return False
    return bool(start or end)


def make_id(rec: dict) -> str:
    raw = f"{title_key(rec['title'])}|{to_tai(rec.get('venue') or '')}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def distance_m(a: dict, b: dict) -> float | None:
    if a["lat"] is None or b["lat"] is None:
        return None
    dlat = (a["lat"] - b["lat"]) * 111_000
    dlng = (a["lng"] - b["lng"]) * 111_000 * math.cos(math.radians(a["lat"]))
    return math.hypot(dlat, dlng)


def titles_match(a: str, b: str) -> bool:
    """標題相同、互相包含，或幾乎相同（例如「阮的海海人生」與「阮ê海海人生」）。"""
    ka, kb = title_key(a), title_key(b)
    if ka == kb:
        return True
    short, long_ = sorted((ka, kb), key=len)
    if len(short) >= 4 and short in long_:
        return True
    return len(short) >= 8 and difflib.SequenceMatcher(None, ka, kb).ratio() >= 0.85


def dates_overlap(a: dict, b: dict, gap_days: int = 7) -> bool:
    if not (a["start"] and a["end"] and b["start"] and b["end"]):
        return True
    slack = timedelta(days=gap_days)
    return a["start"] <= b["end"] + slack and b["start"] <= a["end"] + slack


APPROXIMATE = ("road", "district", "none")


def is_duplicate(a: dict, b: dict) -> bool:
    """
    同一檔展覽：標題相同或互相包含、檔期重疊，而且地點相同。
    地點判斷：兩邊都有精確座標時需在 400 公尺內（標題完全相同時放寬到 1.5 公里，
    因為部分來源的座標只是大概位置）；任一邊只有概略位置時，同行政區即可。
    """
    if not (titles_match(a["title"], b["title"]) and dates_overlap(a, b)):
        return False
    if a.get("city") != b.get("city"):
        return False
    if a["precision"] in APPROXIMATE or b["precision"] in APPROXIMATE:
        if a.get("district") and a.get("district") == b.get("district"):
            return True
        return to_tai(a.get("venue") or "") == to_tai(b.get("venue") or "")
    dist = distance_m(a, b)
    limit = 1500 if title_key(a["title"]) == title_key(b["title"]) else 400
    return dist is not None and dist <= limit


def merge_duplicates(records: list[dict]) -> list[dict]:
    """合併重複的展覽（跨來源或同來源分段），日期取聯集；以先出現（優先來源）的資料為主。"""
    merged: list[dict] = []
    for rec in records:
        cur = next((m for m in merged if is_duplicate(m, rec)), None)
        if cur is None:
            merged.append({**rec, "sources": [rec["source"]]})
            continue
        if rec["source"] not in cur["sources"]:
            cur["sources"].append(rec["source"])
        cur["start"] = min(filter(None, [cur["start"], rec["start"]]), default=None)
        cur["end"] = max(filter(None, [cur["end"], rec["end"]]), default=None)
        if PRECISION_RANK[rec["precision"]] < PRECISION_RANK[cur["precision"]]:
            for k in ("lat", "lng", "precision", "district"):
                cur[k] = rec[k]
        if cur["price"]["min"] is None and rec["price"]["min"] is not None:
            cur["price"] = rec["price"]
        for k in ("image", "description", "organizer", "url", "ticket_url", "district", "keywords"):
            if not cur.get(k) and rec.get(k):
                cur[k] = rec[k]
    return merged


def to_output(rec: dict) -> dict:
    return {
        "id": make_id(rec),
        "title": rec["title"],
        "venue": rec.get("venue") or "",
        "address": rec.get("address") or "",
        "city": rec.get("city"),
        "district": rec.get("district"),
        "lat": rec["lat"],
        "lng": rec["lng"],
        "geo_precision": rec["precision"],
        "start": rec["start"].isoformat() if rec.get("start") else None,
        "end": rec["end"].isoformat() if rec.get("end") else None,
        "price": rec["price"],
        "url": rec.get("url"),
        "ticket_url": rec.get("ticket_url"),
        "image": rec.get("image"),
        "organizer": rec.get("organizer") or "",
        "description": rec.get("description") or "",
        "keywords": rec.get("keywords") or [],
        "topics": detect_topics(rec["title"], rec.get("venue") or "", rec.get("organizer") or ""),
        "sources": rec["sources"],
    }


def load_previous(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def restore_previous(prev: dict, source_id: str, today: date) -> list[dict]:
    """來源暫時失效時，沿用上次抓到且尚未結束的資料。"""
    out = []
    for ex in prev.get("exhibitions", []):
        if source_id not in ex.get("sources", []):
            continue
        end = date.fromisoformat(ex["end"]) if ex.get("end") else None
        if end and end < today:
            continue
        out.append(ex)
    return out


def run(output: Path, days_ahead: int, network_geocode: bool) -> int:
    today = now_taipei().date()
    previous = load_previous(output)
    geocoder = Geocoder(VENUES_PATH, CACHE_PATH, network=network_geocode)

    records: list[dict] = []
    carried_over: list[dict] = []
    source_status = []
    for src in SOURCES:
        print(f"[{src.SOURCE_ID}] 抓取中…")
        try:
            items = src.collect()
        except Exception as e:  # noqa: BLE001 - 單一來源失敗不影響其他來源
            print(f"[{src.SOURCE_ID}] 失敗：{e}", file=sys.stderr)
            kept = restore_previous(previous, src.SOURCE_ID, today)
            carried_over.extend(kept)
            source_status.append({"id": src.SOURCE_ID, "name": src.SOURCE_NAME, "url": src.SOURCE_URL,
                                  "ok": False, "count": len(kept), "error": str(e)[:200]})
            continue

        # 來源可直接指定 city（單一縣市的來源），否則從地址判斷
        for r in items:
            r["city"] = r.get("city") or detect_city(r["address"], r["venue"], r["lat"], r["lng"])
        in_region = [r for r in items if r["city"] in CITIES and not _ONLINE_ONLY.search(r["title"])]
        recent = [r for r in in_region if in_window(r, today, days_ahead)]
        by_city = {c: sum(1 for r in recent if r["city"] == c) for c in CITIES}
        print(f"[{src.SOURCE_ID}] 共 {len(items)} 筆，北北基桃 {len(in_region)} 筆，近期 {len(recent)} 筆 {by_city}")
        for r in recent:
            loc = geocoder.locate(r["venue"], r["address"], r["lat"], r["lng"], r["city"])
            r.update(loc)
        records.extend(recent)
        source_status.append({"id": src.SOURCE_ID, "name": src.SOURCE_NAME, "url": src.SOURCE_URL,
                              "ok": True, "count": len(recent)})

    geocoder.save()

    if not any(s["ok"] for s in source_status):
        print("所有資料來源都失敗，保留原本的資料。", file=sys.stderr)
        return 1

    exhibitions = []
    seen: set[str] = set()
    for rec in merge_duplicates(records):
        out = to_output(rec)
        while out["id"] in seen:
            out["id"] = hashlib.sha1(out["id"].encode()).hexdigest()[:10]
        seen.add(out["id"])
        exhibitions.append(out)
    exhibitions.extend(e for e in carried_over if e["id"] not in seen)
    exhibitions.sort(key=lambda e: (e["end"] or "9999", e["start"] or "", e["title"]))

    payload = {
        "updated_at": now_taipei().replace(microsecond=0).isoformat(),
        "window": {"from": today.isoformat(), "to": (today + timedelta(days=days_ahead)).isoformat()},
        "sources": source_status,
        "count": len(exhibitions),
        "exhibitions": exhibitions,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    precision, per_city = {}, {}
    for e in exhibitions:
        precision[e["geo_precision"]] = precision.get(e["geo_precision"], 0) + 1
        per_city[e.get("city")] = per_city.get(e.get("city"), 0) + 1
    print(f"輸出 {len(exhibitions)} 筆展覽 {per_city} → {output}（定位精度：{precision}，"
          f"Nominatim 查詢 {geocoder.requests_made} 次）")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓取臺北市近期展覽資料")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--days", type=int, default=120, help="收錄幾天內開展的展覽（預設 120）")
    parser.add_argument("--offline-geocode", action="store_true",
                        help="不連線 Nominatim，只使用場館對照表與快取")
    args = parser.parse_args(argv)
    return run(args.output, args.days, not args.offline_geocode)


if __name__ == "__main__":
    sys.exit(main())
