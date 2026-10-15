import unittest
from datetime import date

from scraper import jsonld
from scraper.normalize import detect_topics
from scraper.sources import accupass, ibon, skm

IBON_ITEM = {"ActivityID": 39973, "ActivityName": "海之召喚海洋生靈祈願旅程．台北三創 ", "GameLocation": "台北三創",
             "ActivitySDate": "2026-05-28T00:00:00", "ActivityEDate": "2026-12-31T00:00:00",
             "GameTicketURL": "https://tour.ibon.com.tw/event/6aa8eaa9acf21524ce1cd6b3",
             "ActivityImageURL": "https://tour.ibon.com.tw/media/a.jpg"}
IBON_PAGE = """<script type="application/ld+json">{"@context":"https://schema.org","@type":"Event","name":"海之召喚",
"startDate":"2026-05-28T04:00:00Z","endDate":"2026-12-31T11:00:59.999Z",
"location":{"@type":"Place","name":"台北三創","address":{"@type":"PostalAddress","streetAddress":"台北市中正區市民大道三段2號3樓","addressRegion":"台北市"}},
"offers":{"@type":"AggregateOffer","priceCurrency":"TWD","lowPrice":550.0,"highPrice":1100.0}}</script>"""

SKM_LIST = """
<div><span class="building">台北信義新天地</span><div class="promotion-title"><a href="https://www.skm.com.tw/page/121/202609cornerart?page_crumb=New">A11 3F轉角藝術 | meow meow cry</a></div></div>
<div><span class="building">台北信義新天地</span><div class="promotion-title"><a href="https://www.skm.com.tw/page/121/202609cornerart?page_crumb=New">A11 3F轉角藝術 | meow meow cry</a></div></div>
<div><span class="building">台北南西店</span><div class="promotion-title"><a href="https://www.skm.com.tw/page/101/GRACEGIFT?page_crumb=New">2026 GRACE GIFT 秋靴大賞</a></div></div>
<div><span class="building">高雄左營店</span><div class="promotion-title"><a href="https://www.skm.com.tw/page/351/x?page_crumb=New">《麥可．克雷格-馬丁特展》</a></div></div>
<script>var page_total_rcnt = "26";</script>"""
SKM_EVENT = {"@type": "Event", "name": "A11 3F轉角藝術 | meow meow cry", "startDate": "2026-09-18T00:00:00",
             "endDate": "2026-11-03T00:00:00", "image": ["https://img.skmbuy.com.tw/a.webp"], "description": "展出插畫"}

ACCU_ITEM = {"eventIdNumber": "123", "name": "恐怖心展・台北", "eventPlaceType": "Offline",
             "startDateTime": "2026-09-12T02:00:00Z", "endDateTime": "2026-11-23T13:00:00Z",
             "photoUrl": "https://static.accupass.com/a.jpg"}
ACCU_PAGE = """<script type="application/ld+json">{"@type":"Event","name":"【日本爆紅展覽首度來台】「恐怖心展・台北」",
"startDate":"2026-09-12T10:00:00+08:00","endDate":"2026-11-23T21:00:00+08:00",
"location":{"@type":"Place","address":"台灣台北市灰棚｜中山區中山北路二段 59 巷 16 號 B1","name":"（近捷運中山站／雙連站）"},
"organizer":{"@type":"Organization","name":"SaltSweeet"}}</script>"""


class JsonLdTest(unittest.TestCase):
    def test_to_date_converts_timezones(self):
        self.assertEqual(jsonld.to_date("2026-05-27T16:00:00Z"), date(2026, 5, 28))
        self.assertEqual(jsonld.to_date("2026-09-12T10:00:00+08:00"), date(2026, 9, 12))
        self.assertEqual(jsonld.to_date("2026-09-18T00:00:00"), date(2026, 9, 18))
        self.assertIsNone(jsonld.to_date(""))


class IbonTest(unittest.TestCase):
    def test_record(self):
        rec = ibon.build_record(IBON_ITEM, jsonld.first_of_type(IBON_PAGE, "Event"))
        self.assertEqual(rec["city"], "臺北市")
        self.assertEqual(rec["address"], "台北市中正區市民大道三段2號3樓")
        self.assertEqual((rec["price"]["min"], rec["price"]["max"]), (550, 1100))
        self.assertEqual((rec["start"], rec["end"]), (date(2026, 5, 28), date(2026, 12, 31)))
        self.assertEqual(rec["ticket_url"], IBON_ITEM["GameTicketURL"])

    def test_filters(self):
        def item(name, place="某場地"):
            return {"ActivityName": name, "GameLocation": place}
        self.assertTrue(ibon.keep(item("POPUPASIA 亞洲手創暨生活展", "松山文創園區")))
        self.assertFalse(ibon.keep(item("古屋呂敏　台北粉絲見面會")))
        self.assertFalse(ibon.keep(item("台北．國立臺灣博物館四館聯票")))
        self.assertFalse(ibon.keep(item("台北．國立故宮博物院北院")))
        self.assertFalse(ibon.keep(item("臺北市立美術館", "臺北市立美術館")))
        self.assertFalse(ibon.keep(item("臺中市立美術館．真鍋大度個展", "臺中市立美術館")))


class SkmTest(unittest.TestCase):
    def test_list_filter_and_record(self):
        cards = skm.parse_list(SKM_LIST)
        self.assertEqual(len(cards), 3)  # 重複的卡片只算一次
        self.assertEqual(skm.page_count(SKM_LIST), 3)
        kept = [c for c in cards if skm.keep(c)]
        self.assertEqual([c["title"] for c in kept], ["A11 3F轉角藝術 | meow meow cry"])  # 促銷與外縣市排除
        rec = skm.build_record(kept[0], SKM_EVENT)
        self.assertEqual(rec["venue"], "新光三越台北信義新天地A11 3F")
        self.assertEqual(rec["address"], "臺北市信義區松壽路11號")
        self.assertEqual((rec["start"], rec["end"]), (date(2026, 9, 18), date(2026, 11, 3)))
        self.assertTrue(rec["price"]["free"])
        self.assertEqual(rec["url"], "https://www.skm.com.tw/page/121/202609cornerart")


class AccupassTest(unittest.TestCase):
    def test_record(self):
        rec = accupass.build_record(ACCU_ITEM, jsonld.first_of_type(ACCU_PAGE, "Event"))
        self.assertEqual(rec["venue"], "灰棚")
        self.assertEqual(rec["address"], "臺北市中山區中山北路二段 59 巷 16 號 B1")
        self.assertEqual(rec["city"], "臺北市")
        self.assertEqual((rec["start"], rec["end"]), (date(2026, 9, 12), date(2026, 11, 23)))
        self.assertEqual(rec["organizer"], "SaltSweeet")

    def test_filters(self):
        self.assertTrue(accupass.keep({"name": "Hearts2Hearts POP-UP in TAIPEI", "eventPlaceType": "Offline"}))
        self.assertFalse(accupass.keep({"name": "GELEVEN PLAZA 展演空間 場地租借", "eventPlaceType": "Offline"}))
        self.assertFalse(accupass.keep({"name": "快閃展覽講座", "eventPlaceType": "Offline"}))
        self.assertFalse(accupass.keep({"name": "線上快閃展", "eventPlaceType": "Online"}))


class PopupTopicTest(unittest.TestCase):
    def test_popup_titles(self):
        self.assertIn("mall", detect_topics("2026寶可夢30週年快閃店", "某園區"))
        self.assertIn("mall", detect_topics("2026台北萌寵物用品展", "台北世貿一館"))
        self.assertNotIn("mall", detect_topics("王雅慧：旅行者", "臺北市立美術館"))


if __name__ == "__main__":
    unittest.main()
