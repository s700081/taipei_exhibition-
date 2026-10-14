import tempfile
import unittest
from datetime import date
from pathlib import Path

from scraper.geocode import Geocoder, _similar
from scraper.main import VENUES_PATH, in_window, is_duplicate, merge_duplicates
from scraper.normalize import parse_price
from scraper.sources import culture_express, moc, tfam


def record(**kw):
    base = {
        "source": "test", "source_id": "1", "title": "測試展", "venue": "某畫廊", "address": "臺北市大安區",
        "lat": 25.03, "lng": 121.54, "start": date(2026, 10, 1), "end": date(2026, 11, 1),
        "price": parse_price(""), "url": None, "image": None, "organizer": "", "description": "",
        "precision": "source", "district": "大安區",
    }
    base.update(kw)
    return base


class GeocoderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.geo = Geocoder(VENUES_PATH, Path(self.tmp.name) / "cache.json", network=False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_venue_alias_beats_source_coordinates(self):
        # 臺北文化快遞曾把郵政博物館標在 3 公里外
        loc = self.geo.locate("郵政博物館臺北館特展室", "臺北市中正區", 25.06263, 121.51921)
        self.assertEqual(loc["precision"], "venue")
        self.assertAlmostEqual(loc["lat"], 25.0317, places=3)

    def test_longest_alias_wins(self):
        loc = self.geo.locate("國立臺灣博物館南門館", "")
        self.assertIn("國立臺灣博物館南門館", loc["keywords"])

    def test_street_key_match(self):
        loc = self.geo.locate("美學空間", "臺北市南海路四十七號")
        self.assertEqual(loc["precision"], "venue")

    def test_district_fallback(self):
        loc = self.geo.locate("某不知名藝廊", "臺北市文山區")
        self.assertEqual((loc["precision"], loc["district"]), ("district", "文山區"))

    def test_similarity_rejects_unrelated_names(self):
        self.assertTrue(_similar("華山1914文化創意產業園區", "華山1914文化創意產業園區"))
        self.assertFalse(_similar("臺北市政府", "博愛路派出所"))


class MergeTest(unittest.TestCase):
    def test_merge_across_sources(self):
        a = record(source="tfam", title="坂本龍一︱觀音．聽時", lat=25.07203, lng=121.524661)
        b = record(source="culture_express", title="北美館 - 坂本龍一：觀音，聽時", lat=25.0699, lng=121.52451,
                   price=parse_price("NT$30"))
        merged = merge_duplicates([a, b])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["title"], a["title"])
        self.assertEqual(merged[0]["sources"], ["tfam", "culture_express"])

    def test_different_shows_same_venue_are_kept(self):
        a = record(title="「虛空之境」展覽-領土")
        b = record(title="「虛空之境」展覽-都市")
        self.assertFalse(is_duplicate(a, b))

    def test_approximate_location_merges_by_district(self):
        a = record(title="物．我｜林宇軒個展 The Self in Things", district="大同區")
        b = record(title="物．我｜林宇軒個展", district="大同區", precision="road", lat=25.06, lng=121.50)
        self.assertTrue(is_duplicate(a, b))

    def test_split_date_ranges_are_joined(self):
        a = record(start=date(2026, 7, 11), end=date(2026, 12, 31))
        b = record(start=date(2027, 1, 1), end=date(2027, 1, 3))
        merged = merge_duplicates([a, b])
        self.assertEqual((merged[0]["start"], merged[0]["end"]), (date(2026, 7, 11), date(2027, 1, 3)))

    def test_window(self):
        today = date(2026, 10, 14)
        self.assertTrue(in_window(record(), today, 120))
        self.assertFalse(in_window(record(end=date(2026, 10, 13)), today, 120))
        self.assertFalse(in_window(record(start=date(2027, 6, 1), end=date(2027, 7, 1)), today, 120))


class SourceParseTest(unittest.TestCase):
    def test_moc(self):
        items = [{
            "UID": "abc", "title": "測試特展", "startDate": "2026/10/01", "endDate": "2026/12/31",
            "showInfo": [{"time": "2026/10/01 09:00:00", "endTime": "2026/12/31 17:00:00",
                          "location": "臺北市中正區南海路49號", "locationName": "國立歷史博物館",
                          "onSales": "Y", "price": "全票+80;優待票+40", "latitude": None, "longitude": None}],
            "masterUnit": ["國立歷史博物館"], "imageUrl": "", "webSales": "", "sourceWebPromote": "",
            "descriptionFilterHtml": "<p>介紹</p>",
        }]
        [r] = moc.parse(items)
        self.assertEqual((r["start"], r["end"]), (date(2026, 10, 1), date(2026, 12, 31)))
        self.assertEqual(r["price"]["min"], 40)
        self.assertIn("uid=abc", r["url"])
        self.assertEqual(r["description"], "介紹")

    def test_culture_express_filters(self):
        def item(**kw):
            base = {"ID": "x", "Category": "展覽", "City": "臺北市", "Caption": "某個展", "Venue": "某畫廊",
                    "Area": "大安區", "StartDate": "2026-10-01 10:00:00", "EndDate": "2026-11-01 18:00:00",
                    "TicketType": "免費", "TicketPrice": None, "Latitude": 25.03, "Longitude": 121.54}
            base.update(kw)
            return base

        records = culture_express.parse([
            item(),
            item(Category="講座"),
            item(City="新北市"),
            item(Caption="2027 國際攝影大賽"),
            item(Venue="威尼斯雙年展台灣館"),
            item(Caption="售票展", TicketType="售票", TicketPrice="50"),
            item(Caption="坐標缺漏", Latitude=0.0, Longitude=0.0),
        ])
        self.assertEqual([r["title"] for r in records], ["某個展", "售票展", "坐標缺漏"])
        self.assertTrue(records[0]["price"]["free"])
        self.assertEqual(records[1]["price"]["min"], 50)
        self.assertIsNone(records[2]["lat"])
        self.assertEqual(records[0]["address"], "臺北市大安區")

    def test_tfam_skips_overseas_and_online(self):
        items = [
            {"ExID": 1, "ExName": "館內展", "Area": "一樓1A", "BeginDate": "2026/10/01", "EndDate": "2026/12/01",
             "IsSpecial": 1, "ShowStyle": 1, "ExternalLink": "https://", "NowPlayImg": "Exhibition\\Main\\1\\a.jpg"},
            {"ExID": 2, "ExName": "威尼斯台灣館", "Area": "義大利威尼斯普里奇歐尼宮", "BeginDate": "2026/05/09",
             "EndDate": "2026/11/22", "IsSpecial": 0, "ShowStyle": 2, "ExternalLink": "https://example.org"},
            {"ExID": 3, "ExName": "線上計畫", "Area": "", "BeginDate": "2025/09/19", "EndDate": "2026/12/31"},
        ]
        [r] = tfam.parse(items)
        self.assertEqual(r["title"], "館內展")
        self.assertEqual(r["image"], "https://www.tfam.museum/File/Exhibition/Main/1/a.jpg")
        self.assertTrue(r["url"].endswith("Exhibition_Special.aspx?ddlLang=zh-tw&id=1"))


if __name__ == "__main__":
    unittest.main()
