import unittest
from datetime import date

from scraper.normalize import (
    is_taipei,
    normalize_address,
    parse_date,
    parse_price,
    street_key,
    title_key,
)


class PriceTest(unittest.TestCase):
    def test_moc_plus_format(self):
        p = parse_price("優惠參觀券+150;團體參觀券+320;普通參觀券+350;")
        self.assertFalse(p["free"])
        self.assertEqual((p["min"], p["max"]), (150, 350))
        self.assertEqual(len(p["tickets"]), 3)

    def test_moc_spaces_in_name(self):
        p = parse_price("早鳥票+380;全   票+580")
        self.assertEqual([t["name"] for t in p["tickets"]], ["早鳥票", "全票"])

    def test_free_text_with_amounts(self):
        p = parse_price("全票100元，半票70元。")
        self.assertEqual((p["min"], p["max"]), (70, 100))

    def test_nt_dollar(self):
        self.assertEqual(parse_price("全票 NT$500")["min"], 500)
        self.assertEqual(parse_price("一般觀眾NTD$80")["min"], 80)
        self.assertEqual(parse_price("NT$30元(現場販售)")["min"], 30)

    def test_numbers_without_unit_are_ignored_unless_ticketed(self):
        text = "一般票600、優待票450、團體票(20人以上)450/1 張"
        self.assertIsNone(parse_price(text)["min"])
        p = parse_price(text, assume_currency=True)
        self.assertEqual((p["min"], p["max"]), (450, 600))

    def test_free(self):
        p = parse_price("本展覽免費入場，參觀者無須購票")
        self.assertTrue(p["free"])
        self.assertEqual(p["min"], 0)

    def test_on_sales_fallback(self):
        self.assertTrue(parse_price("", "N")["free"])
        self.assertFalse(parse_price("", "Y")["free"])
        self.assertIsNone(parse_price("", "")["free"])

    def test_non_price_text_is_dropped(self):
        p = parse_price("▎《原鄉情長》開幕茶會｜10/17（六）下午三點", "N")
        self.assertTrue(p["free"])
        self.assertNotIn("茶會", p["text"])


class AddressTest(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_address("10066臺北市中正區南海路四十七號"), "臺北市中正區南海路47號")
        self.assertEqual(normalize_address("台北市中正區重慶南路2段45號"), "臺北市中正區重慶南路二段45號")

    def test_street_key(self):
        self.assertEqual(street_key("臺北市大安區青田街八巷三號"), "青田街8巷3號")
        self.assertEqual(street_key("臺北市中山區中山北路三段181號"), "中山北路三段181號")
        self.assertIsNone(street_key("臺北市大安區"))

    def test_is_taipei(self):
        self.assertTrue(is_taipei("臺北市中正區忠孝西路一段70號"))
        self.assertTrue(is_taipei("台北市信義區松高路79號"))
        self.assertTrue(is_taipei("大同區迪化街1段21號"))
        self.assertFalse(is_taipei("新北市板橋區縣民大道二段7號"))
        self.assertFalse(is_taipei("臺中市北區館前路一號"))
        # 基隆市也有中正區：沒有座標時不能只靠區名判斷
        self.assertFalse(is_taipei("中正區中正路1號"))
        self.assertTrue(is_taipei("中正區中山南路21號", lat=25.0346, lng=121.5218))
        self.assertFalse(is_taipei("中正區中正路1號", lat=25.13, lng=121.74))


class MiscTest(unittest.TestCase):
    def test_parse_date(self):
        self.assertEqual(parse_date("2026/10/15"), date(2026, 10, 15))
        self.assertEqual(parse_date("2026-09-12 09:30:00"), date(2026, 9, 12))
        self.assertIsNone(parse_date(""))
        self.assertIsNone(parse_date("2026/02/30"))

    def test_title_key_ignores_punctuation_and_generic_words(self):
        self.assertEqual(
            title_key("古典光影大師 林布蘭到哥雅-托雷多美術館珍藏展 I"),
            title_key("古典光影大師：林布蘭到哥雅─托雷多美術館珍藏展 I"),
        )
        self.assertEqual(title_key("【特展】 「請戲-布袋戲一條街」特展"), "請戲布袋戲一條街")
        self.assertNotEqual(title_key("「虛空之境」展覽-領土"), title_key("「虛空之境」展覽-都市"))


if __name__ == "__main__":
    unittest.main()
