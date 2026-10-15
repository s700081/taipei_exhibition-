import tempfile
import unittest
from datetime import date
from pathlib import Path

from scraper.geocode import Geocoder
from scraper.main import VENUES_PATH, is_duplicate
from scraper.normalize import CITY_DISTRICTS, DISTRICT_CENTROIDS, detect_city, find_district, parse_price


class DetectCityTest(unittest.TestCase):
    def test_explicit_city(self):
        self.assertEqual(detect_city("臺北市中正區忠孝西路一段70號"), "臺北市")
        self.assertEqual(detect_city("22041新北市板橋區縣民大道二段7號"), "新北市")
        self.assertEqual(detect_city("基隆市中正區北寧路367號"), "基隆市")
        self.assertEqual(detect_city("320桃園市中壢區中美路16號"), "桃園市")

    def test_old_county_names(self):
        self.assertEqual(detect_city("台北縣淡水鎮"), "新北市")
        self.assertEqual(detect_city("桃園縣大溪鎮"), "桃園市")

    def test_other_cities_excluded(self):
        self.assertIsNone(detect_city("臺中市北區館前路一號"))
        self.assertIsNone(detect_city("新竹縣竹北市文興路一段123號"))

    def test_district_only(self):
        self.assertEqual(detect_city("板橋區文化路一段"), "新北市")
        self.assertEqual(detect_city("龜山區文化一路"), "桃園市")
        self.assertEqual(detect_city("七堵區明德一路"), "基隆市")

    def test_district_shared_by_taipei_and_keelung(self):
        self.assertIsNone(detect_city("中正區中正路1號"))
        self.assertEqual(detect_city("中正區中正路1號", lat=25.13, lng=121.74), "基隆市")
        self.assertEqual(detect_city("中正區中山南路21號", lat=25.0346, lng=121.5218), "臺北市")

    def test_find_district_respects_city(self):
        self.assertEqual(find_district("基隆市中正區北寧路", city="基隆市"), "中正區")
        self.assertIsNone(find_district("新北市板橋區", city="臺北市"))

    def test_district_data(self):
        self.assertEqual({c: len(d) for c, d in CITY_DISTRICTS.items()},
                         {"臺北市": 12, "新北市": 29, "基隆市": 7, "桃園市": 13})
        self.assertIn("鶯歌區", DISTRICT_CENTROIDS["新北市"])


class CityGeocodeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.geo = Geocoder(VENUES_PATH, Path(self.tmp.name) / "cache.json", network=False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_district_fallback_uses_city(self):
        loc = self.geo.locate("某藝廊", "新北市鶯歌區", city="新北市")
        self.assertEqual((loc["precision"], loc["district"]), ("district", "鶯歌區"))
        self.assertAlmostEqual(loc["lat"], DISTRICT_CENTROIDS["新北市"]["鶯歌區"][0])

    def test_venue_table_is_city_scoped(self):
        # 臺北市的場館不能套用到其他縣市的同名字串
        self.assertIsNone(self.geo.match_venue("國立臺灣大學", "", city="桃園市"))
        self.assertIsNotNone(self.geo.match_venue("國立臺灣大學", "", city="臺北市"))

    def test_source_coordinates_accepted_across_region(self):
        loc = self.geo.locate("某館", "桃園市大溪區", 24.88, 121.29, city="桃園市")
        self.assertEqual(loc["precision"], "source")


class CityMergeTest(unittest.TestCase):
    def test_same_district_name_in_different_cities_is_not_merged(self):
        base = {"title": "海洋特展", "venue": "文化中心", "lat": None, "lng": None, "precision": "district",
                "district": "中正區", "start": date(2026, 10, 1), "end": date(2026, 11, 1), "price": parse_price("")}
        self.assertFalse(is_duplicate({**base, "city": "臺北市"}, {**base, "city": "基隆市"}))
        self.assertTrue(is_duplicate({**base, "city": "基隆市"}, {**base, "city": "基隆市"}))


if __name__ == "__main__":
    unittest.main()
