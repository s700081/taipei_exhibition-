import unittest
from datetime import date

from scraper.normalize import detect_topics, parse_zh_date_range
from scraper.sources import ntsec

LIST_HTML = """
<nav><a href="https://www.ntsec.gov.tw/article/detail.aspx?a=27">常設展</a></nav>
<div id="MainContent_divListItem" class="message-group">
  <a href="https://oddradio.fonticket.com/search?openExternalBrowser=1" target='_blank' class="message-item click-cursor">
    <div><img src="https://www.ntsec.gov.tw/images/ArticleListPic/6115_2.png" alt=""><p>2026.09.02</p></div>
    <div class="newsMessage-content">《VR探索虛實穿越》小王子奇幻星旅 </div>
    <div class="message-annotation">《VR探索虛實穿越》小王子奇幻星旅 即日起至116年4月30日</div>
  </a>
  <a href="https://www.ntsec.gov.tw/article/detail.aspx?a=5462"  class="message-item click-cursor">
    <div><img src="https://www.ntsec.gov.tw/images/ArticleListPic/5462_2.png" alt=""><p>2024.07.31</p></div>
    <div class="newsMessage-content">《末日學校》特展</div>
    <div class="message-annotation">4F 東側展區</div>
  </a>
</div>
"""

DETAIL_HTML = """
<header>參觀資訊 票價總覽</header>
<main id="main-content"><div class="main-content-view">
  ::: 《末日學校》特展 最後更新日期： 2026-03-27
  <p>《末日學校》特展</p><p>展覽介紹</p><p>「末日學校」計畫開始於2018年。</p>
  <p>展覽日期｜ 2024年7月31日（三）起</p><p>展覽時間｜ 依本館開放時間</p>
  <p>展覽地點｜ 本館4樓東側展區</p>
  <p>參觀資訊｜ 憑本館當日常設展、特展門票或有效會員卡即可參觀</p>
  <p>照片集</p>
</div></main>
"""

TICKET_HTML = "<p>◼ 常設展門票（3-6樓）</p><p>全票</p><p>：120元</p><p>優待票</p><p>：90元</p>"


class ZhDateTest(unittest.TestCase):
    def test_range(self):
        self.assertEqual(parse_zh_date_range("2025 年 7 月 19 日至 2027 年 12 月 31 日"),
                         (date(2025, 7, 19), date(2027, 12, 31)))

    def test_open_ended(self):
        self.assertEqual(parse_zh_date_range("自2025年11月8日(六)起"), (date(2025, 11, 8), None))
        self.assertEqual(parse_zh_date_range("2024年7月31日（三）起"), (date(2024, 7, 31), None))

    def test_roc_year_end_only(self):
        self.assertEqual(parse_zh_date_range("即日起至116年4月30日"), (None, date(2027, 4, 30)))

    def test_single_day_and_empty(self):
        self.assertEqual(parse_zh_date_range("2026年11月7日"), (date(2026, 11, 7), date(2026, 11, 7)))
        self.assertEqual(parse_zh_date_range(""), (None, None))


class TopicTest(unittest.TestCase):
    def test_science(self):
        self.assertEqual(detect_topics("看見分子相遇的奇妙"), ["science"])
        self.assertEqual(detect_topics("《末日學校》特展", "國立臺灣科學教育館 4樓東側展區"), ["science"])
        self.assertEqual(detect_topics("Oh!海郵-海洋生物郵票特展", "郵政博物館"), [])
        self.assertEqual(detect_topics("王雅慧：旅行者", "臺北市立美術館"), [])


class NtsecParseTest(unittest.TestCase):
    def test_list_ignores_navigation(self):
        items = ntsec.parse_list(LIST_HTML, "25")
        self.assertEqual([i["title"] for i in items], ["《VR探索虛實穿越》小王子奇幻星旅", "《末日學校》特展"])
        self.assertEqual(items[1]["date"], date(2024, 7, 31))
        self.assertEqual(items[1]["note"], "4F 東側展區")

    def test_ticket_prices(self):
        self.assertEqual(ntsec.parse_ticket_prices(TICKET_HTML), (120, 90))

    def test_detail_record(self):
        item = ntsec.parse_list(LIST_HTML, "25")[1]
        rec = ntsec.build_record(item, ntsec.parse_detail(DETAIL_HTML), (120, 90))
        self.assertEqual((rec["start"], rec["end"]), (date(2024, 7, 31), None))
        self.assertEqual(rec["venue"], "國立臺灣科學教育館 4樓東側展區")
        self.assertEqual((rec["price"]["min"], rec["price"]["max"]), (90, 120))
        self.assertTrue(rec["description"].startswith("「末日學校」計畫"))

    def test_external_item_uses_annotation_dates(self):
        item = ntsec.parse_list(LIST_HTML, "25")[0]
        rec = ntsec.build_record(item, None, (120, 90))
        self.assertEqual((rec["start"], rec["end"]), (date(2026, 9, 2), date(2027, 4, 30)))
        self.assertFalse(rec["price"]["free"])
        self.assertTrue(rec["ticket_url"].startswith("https://oddradio.fonticket.com/"))
        self.assertEqual(rec["url"], "https://www.ntsec.gov.tw/article/list.aspx?a=25")


if __name__ == "__main__":
    unittest.main()
