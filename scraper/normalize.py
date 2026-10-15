"""文字、日期、票價、地址的正規化工具。"""

from __future__ import annotations

import html
import re
import unicodedata
from datetime import date, datetime

TAIPEI_DISTRICTS = (
    "中正區", "大同區", "中山區", "松山區", "大安區", "萬華區",
    "信義區", "士林區", "北投區", "內湖區", "南港區", "文山區",
)
# 基隆市也有這三個行政區，單憑區名無法判斷是否在臺北市
AMBIGUOUS_DISTRICTS = ("中正區", "中山區", "信義區")

# 行政區中心點，作為找不到精確座標時的概略位置
DISTRICT_CENTROIDS = {
    "中正區": (25.0324, 121.5199),
    "大同區": (25.0634, 121.5130),
    "中山區": (25.0685, 121.5333),
    "松山區": (25.0598, 121.5577),
    "大安區": (25.0264, 121.5434),
    "萬華區": (25.0286, 121.4980),
    "信義區": (25.0330, 121.5680),
    "士林區": (25.0927, 121.5250),
    "北投區": (25.1321, 121.5010),
    "內湖區": (25.0697, 121.5880),
    "南港區": (25.0548, 121.6066),
    "文山區": (24.9897, 121.5703),
}

# 臺北市的大致範圍（經度上限可排除基隆市）
TAIPEI_BBOX = (24.96, 25.22, 121.45, 121.67)  # lat_min, lat_max, lng_min, lng_max

_FULLWIDTH = str.maketrans(
    "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ　－",
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz -",
)
_SECTION_DIGITS = {"1": "一", "2": "二", "3": "三", "4": "四", "5": "五",
                   "6": "六", "7": "七", "8": "八", "9": "九"}
_CN_NUM = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9}


def clean_text(value: str | None) -> str:
    """去除 HTML、合併空白、轉換全形英數字。"""
    if not value:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.translate(_FULLWIDTH)
    return re.sub(r"\s+", " ", text).strip()


def to_tai(value: str) -> str:
    """統一使用「臺」字，方便比對。"""
    return value.replace("台", "臺")


def _cn_to_int(text: str) -> int | None:
    """把「四十七」「一百二十」這類中文數字轉成整數（足以處理門牌號碼）。"""
    if not text:
        return None
    if all(ch in _CN_NUM for ch in text):
        return int("".join(str(_CN_NUM[ch]) for ch in text))
    total, current = 0, 0
    for ch in text:
        if ch in _CN_NUM:
            current = _CN_NUM[ch]
        elif ch == "十":
            total += (current or 1) * 10
            current = 0
        elif ch == "百":
            total += (current or 1) * 100
            current = 0
        else:
            return None
    return total + current


def normalize_address(address: str) -> str:
    """地址正規化：臺字、半形數字、「1段」→「一段」、中文門牌→數字、去除郵遞區號。"""
    addr = to_tai(clean_text(address)).replace(" ", "")
    addr = re.sub(r"^\d{3,6}", "", addr)
    addr = re.sub(r"(臺北市)\d{3,6}", r"\1", addr)
    addr = re.sub(r"(\d)段", lambda m: _SECTION_DIGITS.get(m.group(1), m.group(1)) + "段", addr)

    def _num(m: re.Match) -> str:
        n = _cn_to_int(m.group(1))
        return f"{n}{m.group(2)}" if n is not None else m.group(0)

    addr = re.sub(r"([〇零一二三四五六七八九十百]+)(號|巷|弄)", _num, addr)
    return addr


def street_key(address: str) -> str | None:
    """取出「路段＋門牌」作為比對鍵，例如「南海路49號」。"""
    addr = normalize_address(address)
    m = re.search(
        r"([^\d區市縣鄉鎮里]{1,10}?(?:路|街|大道)(?:[一二三四五六七八九]段)?(?:\d+巷)?(?:\d+弄)?\d+號)",
        addr,
    )
    return m.group(1) if m else None


def road_name(address: str) -> str | None:
    """取出路名（含段），作為地理編碼的退而求其次方案。"""
    addr = normalize_address(address)
    addr = re.sub(r"^.*?(?:市|區)", "", addr)
    m = re.search(r"([^\d]{1,10}?(?:路|街|大道)(?:[一二三四五六七八九]段)?)", addr)
    return m.group(1) if m else None


def in_taipei_bbox(lat: float | None, lng: float | None) -> bool:
    if lat is None or lng is None:
        return False
    lat_min, lat_max, lng_min, lng_max = TAIPEI_BBOX
    return lat_min <= lat <= lat_max and lng_min <= lng <= lng_max


def find_district(*texts: str) -> str | None:
    for text in texts:
        if not text:
            continue
        for district in TAIPEI_DISTRICTS:
            if district in text:
                return district
    return None


def is_taipei(address: str, venue: str = "", lat: float | None = None,
              lng: float | None = None) -> bool:
    """判斷是否位於臺北市（排除新北市、基隆市等）。"""
    addr = to_tai(clean_text(address))
    venue = to_tai(clean_text(venue))
    if "臺北市" in addr:
        return True
    other_city = re.search(r"(新北市|基隆市|桃園市|臺中市|臺南市|高雄市|新竹|苗栗|彰化|南投|雲林|嘉義|屏東|宜蘭|花蓮|臺東|澎湖|金門|連江)", addr)
    if other_city:
        return False
    district = find_district(addr, venue)
    if district and district not in AMBIGUOUS_DISTRICTS:
        return True
    if district and in_taipei_bbox(lat, lng):
        return True
    if "臺北市" in venue:
        return True
    return False


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = clean_text(value)
    m = re.search(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", value)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


_ZH_DATE = re.compile(
    r"(?P<y>\d{2,4})\s*[年./\-]\s*(?P<m>\d{1,2})\s*[月./\-]\s*(?P<d>\d{1,2})\s*日?"
    r"(?:\s*[（(][一二三四五六日][)）])?"
)


def parse_zh_date_range(text: str | None) -> tuple[date | None, date | None]:
    """
    解析中文的展期文字，回傳 (開始, 結束)；年份可為西元或民國。
      「2025 年 7 月 19 日至 2027 年 12 月 31 日」→ (2025-07-19, 2027-12-31)
      「自2025年11月8日(六)起」→ (2025-11-08, None)   沒有結束日期
      「即日起至116年4月30日」→ (None, 2027-04-30)
    """
    text = clean_text(text)
    found = []
    for m in _ZH_DATE.finditer(text):
        y = int(m.group("y"))
        if y < 1911:
            y += 1911  # 民國年
        try:
            found.append((m, date(y, int(m.group("m")), int(m.group("d")))))
        except ValueError:
            continue
    if not found:
        return None, None
    if len(found) >= 2:
        return found[0][1], found[1][1]
    m, d = found[0]
    before, after = text[: m.start()], text[m.end(): m.end() + 3]
    if re.search(r"(至|到|~|～|－|迄)\s*$", before) or "即日起" in before:
        return None, d
    if "起" in after:
        return d, None
    return d, d


# 標記「科學・科技」主題的關鍵字（比對標題、場館與主辦單位）
_SCIENCE_VENUES = ("科學教育館", "科教館", "天文科學教育館", "天文館")
_SCIENCE_WORDS = re.compile(
    r"(科學|科技|科普|化學|物理|數學|天文|太空|宇宙|星際|分子|原子|半導體|人工智慧|"
    r"\bAI\b|機器人|程式設計|工程|生物多樣性|生命科學|人體|醫學|演化|恐龍|化石|地球科學|氣候變遷|STEAM|實驗)",
    re.IGNORECASE,
)


def detect_topics(title: str, venue: str = "", organizer: str = "") -> list[str]:
    topics = []
    place = to_tai(f"{venue} {organizer}")
    if any(v in place for v in _SCIENCE_VENUES) or _SCIENCE_WORDS.search(to_tai(title)):
        topics.append("science")
    return topics


def parse_float(value) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # 排除 NaN


_PRICE_HINT = re.compile(r"(票|價|費|元|NT|購|參觀|入場|官網)")
FREE_WORDS = ("免費", "免票", "自由參觀", "免門票", "不收費", "免費參觀", "免費入場")
TICKET_SPLIT = re.compile(r"[;；\n]")


_GENERIC_PRICE = re.compile(
    r"(?P<name>[^\d,，、。;；:：()（）/／]{0,12}?)\s*[:：]?\s*"
    r"(?P<cur>NT\$|NTD\$?|NT|新臺幣|新台幣|\$)?\s*(?P<amount>\d[\d,]*)\s*(?P<unit>元)?"
)


def parse_price(raw: str | None, on_sales: str | None = None, *,
                assume_currency: bool = False) -> dict:
    """
    將來源的票價文字整理成：
      {"text": 顯示用文字, "free": True/False/None, "min": int|None, "max": int|None,
       "tickets": [{"name": 票種, "amount": 金額}]}
    `on_sales` 是文化部資料的「是否售票」欄位（Y / N）。
    `assume_currency` 為 True 時（已知是售票活動），「一般票600」這種沒寫「元」的數字也視為金額。
    """
    text = clean_text(raw)
    tickets: list[dict] = []

    for part in TICKET_SPLIT.split(text):
        part = part.strip()
        if not part:
            continue
        # 文化部格式：「全票+350」
        m = re.fullmatch(r"(.{0,30}?)\s*\+\s*(\d[\d,]*)", part)
        if m:
            name = re.sub(r"\s+", "", m.group(1)).strip("-:： ") or "票價"
            tickets.append({"name": name, "amount": int(m.group(2).replace(",", ""))})
            continue
        # 一般文字：「全票100元，半票70元」「全票 NT$350」「一般票600、優待票450」
        for m in _GENERIC_PRICE.finditer(part):
            name = m.group("name").strip(" ，,、")
            has_unit = bool(m.group("cur") or m.group("unit"))
            ticket_word = bool(re.search(r"(票|價|費)$", name))
            if not (has_unit or (assume_currency and ticket_word)):
                continue  # 沒有金額單位，可能是人數、年齡等數字
            tickets.append({"name": name or "票價", "amount": int(m.group("amount").replace(",", ""))})

    amounts = [t["amount"] for t in tickets if t["amount"] > 0]
    mentions_free = any(w in text for w in FREE_WORDS)

    if amounts:
        lo, hi = min(amounts), max(amounts)
        summary = f"NT${lo}" if lo == hi else f"NT${lo}–{hi}"
        return {"text": text if len(text) <= 120 else summary, "free": False,
                "min": lo, "max": hi, "tickets": tickets}
    if mentions_free or (tickets and all(t["amount"] == 0 for t in tickets)):
        return {"text": text or "免費", "free": True, "min": 0, "max": 0, "tickets": []}
    if text and _PRICE_HINT.search(text):
        return {"text": truncate(text, 80), "free": None, "min": None, "max": None, "tickets": []}
    # 其餘文字（例如誤填的活動介紹）不當作票價
    if (on_sales or "").upper() == "N":
        return {"text": "免費（非售票活動）", "free": True, "min": 0, "max": 0, "tickets": []}
    if (on_sales or "").upper() == "Y":
        return {"text": "需購票，請見官網", "free": False, "min": None, "max": None, "tickets": []}
    return {"text": "未提供票價資訊", "free": None, "min": None, "max": None, "tickets": []}


_GENERIC_TITLE_WORDS = re.compile(r"(常設展|特展|展覽)")


def title_key(title: str) -> str:
    """用於比對重複展覽的標題鍵：去掉標點符號、空白與「特展」「展覽」等泛用字。"""
    t = to_tai(clean_text(title)).lower()
    t = "".join(ch for ch in t if unicodedata.category(ch)[0] not in "PSZC")
    return _GENERIC_TITLE_WORDS.sub("", t)


def truncate(text: str, limit: int = 160) -> str:
    text = clean_text(text)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def now_taipei() -> datetime:
    from datetime import timezone, timedelta
    return datetime.now(timezone(timedelta(hours=8)))
