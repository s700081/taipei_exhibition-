"""
把展覽地點轉成經緯度。依序嘗試：
  1. 內建場館對照表 scraper/data/venues.json（人工確認過，最可靠）
  2. 來源資料本身的座標（需落在臺北市範圍內；部分來源座標只精確到行政區附近）
  3. OpenStreetMap Nominatim 以場館名稱查詢（結果會快取）
  4. Nominatim 以「路段」查詢（概略位置）
  5. 行政區中心點（概略位置）
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

from . import fetch
from .normalize import (
    DISTRICT_CENTROIDS,
    find_district,
    in_taipei_bbox,
    normalize_address,
    road_name,
    street_key,
    to_tai,
)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
TAIPEI_VIEWBOX = "121.45,25.22,121.67,24.96"
NEGATIVE_CACHE_DAYS = 30

# 場館名稱中常見、但對查詢沒有幫助的尾巴
_VENUE_NOISE = re.compile(
    r"(\d+|[一二三四五六七八九十]+|[A-Za-z]\d*)\s*(樓|F|層)|B\d+|"
    r"\d+號(倉庫|館)|展覽室|展示廳|展廳|藝廊|畫廊空間|展區|大廳|迴廊|特展室|"
    r"[一二三四五六七八九十\d]+號?展覽?室"
)


def _bigrams(text: str) -> set[str]:
    text = re.sub(r"[\s()（）\-－_]", "", to_tai(text))
    return {text[i:i + 2] for i in range(len(text) - 1)}


def _similar(query: str, name: str) -> bool:
    """Nominatim 會做模糊比對，必須確認回傳的地點名稱和查詢相近。"""
    q, n = to_tai(query), to_tai(name or "")
    if not q or not n:
        return False
    if q in n or n in q:
        return True
    qb, nb = _bigrams(q), _bigrams(n)
    return bool(qb) and len(qb & nb) / len(qb) >= 0.6


class Geocoder:
    def __init__(self, venues_path: Path, cache_path: Path, *,
                 network: bool = True, max_requests: int = 80) -> None:
        self.cache_path = cache_path
        self.network = network
        self.max_requests = max_requests
        self.requests_made = 0
        self._last_request = 0.0

        self.venues = json.loads(venues_path.read_text(encoding="utf-8"))
        # (別名, 場館) 依別名長度由長到短，優先比對較精確的名稱
        self._aliases: list[tuple[str, dict]] = sorted(
            ((to_tai(alias), v) for v in self.venues for alias in [v["name"], *v.get("aliases", [])]),
            key=lambda pair: -len(pair[0]),
        )
        self.cache: dict = {}
        if cache_path.exists():
            self.cache = json.loads(cache_path.read_text(encoding="utf-8"))

    # ---------------------------------------------------------------- public

    def locate(self, venue: str, address: str, lat: float | None = None,
               lng: float | None = None) -> dict:
        district = find_district(to_tai(address), to_tai(venue))

        hit = self.match_venue(venue, address)
        if hit:
            result = self._result(hit["lat"], hit["lng"], "venue", district or hit.get("district"))
            result["keywords"] = [hit["name"], *hit.get("aliases", [])]
            return result

        if in_taipei_bbox(lat, lng):
            return self._result(lat, lng, "source", district)

        for query in self._venue_queries(venue):
            found = self._nominatim({"q": query}, check_name=query)
            if found:
                return self._result(found[0], found[1], "venue", district)

        key = street_key(address)
        if key:
            found = self._nominatim({"q": f"{key}, 臺北市"}, check_name=None, require_house=True)
            if found:
                return self._result(found[0], found[1], "address", district)

        road = road_name(address)
        if road:
            found = self._nominatim({"street": road, "city": "臺北市", "country": "臺灣"}, check_name=None)
            if found:
                return self._result(found[0], found[1], "road", district)

        if district:
            c_lat, c_lng = DISTRICT_CENTROIDS[district]
            return self._result(c_lat, c_lng, "district", district)
        return self._result(None, None, "none", district)

    def match_venue(self, venue: str, address: str) -> dict | None:
        venue_n = to_tai(venue).replace(" ", "")
        for alias, v in self._aliases:
            if len(alias) >= 2 and alias in venue_n:
                return v
        # 以門牌比對（例如「南海路49號」）
        key = street_key(address)
        if key:
            for v in self.venues:
                if key in (v.get("street_keys") or []):
                    return v
        addr_n = normalize_address(address)
        for alias, v in self._aliases:
            if len(alias) >= 4 and alias in addr_n:
                return v
        return None

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        ordered = dict(sorted(self.cache.items()))
        self.cache_path.write_text(
            json.dumps(ordered, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _result(lat, lng, precision: str, district: str | None) -> dict:
        if lat is not None:
            lat, lng = round(float(lat), 6), round(float(lng), 6)
        return {"lat": lat, "lng": lng, "precision": precision, "district": district}

    @staticmethod
    def _venue_queries(venue: str) -> list[str]:
        venue = to_tai(venue).strip()
        if not venue or venue in ("臺北市", "線上"):
            return []
        cleaned = _VENUE_NOISE.sub(" ", venue)
        parts = [p.strip() for p in re.split(r"[-－–—_/／|｜,，、()（）\s]+", cleaned) if p.strip()]
        candidates = []
        full = re.sub(r"\s+", "", cleaned)
        for cand in [full, *sorted(parts, key=len, reverse=True)]:
            cand = cand.strip("=＝:：")
            if len(cand) < 4 or cand in candidates or re.fullmatch(r"[\d\W]+", cand):
                continue
            # 「大安區（臺北市）」「臺北場」這類只有地名的字串不是場館
            if re.fullmatch(r"(臺北市?)?.?(場|館|店|站)", cand) or find_district(cand):
                continue
            candidates.append(cand)
        return candidates[:3]

    def _nominatim(self, params: dict, *, check_name: str | None,
                   require_house: bool = False) -> tuple[float, float] | None:
        cache_key = "nominatim:" + json.dumps(params, ensure_ascii=False, sort_keys=True)
        cached = self.cache.get(cache_key)
        if cached is not None:
            if cached.get("lat") is not None:
                return cached["lat"], cached["lng"]
            checked = datetime.fromisoformat(cached["checked"])
            if datetime.now() - checked < timedelta(days=NEGATIVE_CACHE_DAYS):
                return None

        if not self.network or self.requests_made >= self.max_requests:
            return None

        query = {
            **params,
            "format": "jsonv2",
            "limit": 3,
            "countrycodes": "tw",
            "viewbox": TAIPEI_VIEWBOX,
            "bounded": 1,
            "addressdetails": 1,
        }
        url = NOMINATIM_URL + "?" + urllib.parse.urlencode(query)
        # Nominatim 使用政策：每秒最多 1 次請求
        wait = 1.1 - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()
        self.requests_made += 1
        try:
            results = fetch.get_json(url, timeout=30, retries=2)
        except Exception as e:  # noqa: BLE001 - 網路錯誤時不快取，下次再試
            print(f"  [geocode] {params}: {e}")
            return None

        found = None
        for r in results or []:
            lat, lng = float(r["lat"]), float(r["lon"])
            if not in_taipei_bbox(lat, lng):
                continue
            if r.get("category") in ("boundary", "place") and r.get("type") != "house":
                continue  # 行政區、里、聚落等範圍，不是具體地點
            if check_name and not _similar(check_name, r.get("name") or ""):
                continue
            if require_house and not (r.get("address") or {}).get("house_number"):
                continue
            found = (round(lat, 6), round(lng, 6))
            break

        today = datetime.now().replace(microsecond=0).isoformat()
        if found:
            self.cache[cache_key] = {"lat": found[0], "lng": found[1], "checked": today}
        else:
            self.cache[cache_key] = {"lat": None, "lng": None, "checked": today}
        return found
