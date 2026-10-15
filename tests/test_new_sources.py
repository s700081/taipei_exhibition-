import unittest
from datetime import date

from scraper.sources import kmoa, nmmst, ntcam, ntpc_events, ntpc_museums

NTCAM_ITEMS = [
    {"ExNo": "H2608001", "ExName": "冥王星在天蠍座", "ExDateSt": "/Date(1787932800000)/", "ExDateEn": "/Date(1795276800000)/",
     "ExLocationTextTW": "新北市美術館 – 4A展覽室", "ExCost": 100, "ExListImg": "20260807100836.jpg",
     "BuyLink": "https://ntcam.fonticket.com/?lang=zh_TW", "ContentDesc": "<p><strong>介紹</strong></p>"},
    {"ExNo": "H2609003", "ExName": "動力夢工廠", "ExDateSt": "/Date(1790956800000)/", "ExDateEn": "/Date(1819468800000)/",
     "ExLocationTextTW": "新北市美術館 – 探索基地 L1、L2", "ExCost": 0, "ExListImg": "", "BuyLink": ""},
]

RSS = """<rss><channel>
<item><link>https://www.ceramics.ntpc.gov.tw/xmdoc/cont?xsmsid=0J1&amp;sid=0Q2</link><title>山彩疊疊-唐榕個展</title>
<description>展覽日期：2026年10月16日至2026年11月15日</description><enddate>2026-11-16</enddate></item>
<item><link>https://www.ceramics.ntpc.gov.tw/xmdoc/cont?sid=0Q3</link><title>117年申請展簡章</title>
<description>報名期間：2026年12月1日至2027年2月1日</description><enddate>2027-02-02</enddate></item>
<item><link>https://www.sshm.ntpc.gov.tw/x</link><title>馭風乘浪-古代南島船舶特展</title>
<description><![CDATA[展覽名稱：馭風乘浪展覽時間：115年7月25日 - 116年5月9日展覽地點：新北市立十三行博物館 第二特展廳 南島語族的傳統歌謠]]></description><enddate>2027-05-10</enddate></item>
<item><link>https://www.sshm.ntpc.gov.tw/y</link><title>阮ê海海人生</title><description>特展介紹</description><enddate>2027-03-02</enddate></item>
<item><link>https://www.tshs.ntpc.gov.tw/z</link><title>季風之路─互動劇場</title><description>劇場簡介</description><enddate></enddate></item>
</channel></rss>"""

KMOA_LIST = """<ul><li><a  href="News_Photo_Content.aspx?n=7484&s=18755" class="div IsTop"  title="流動的港口《瓶中船 𝙎𝙝𝙞𝙥》"  target="_self"><div class="img">
<span><img src="https://klctb-ws.klcg.gov.tw/001/Upload/449/a.png" alt=""></span></div>
<div class="essay"><div class="figcaption"><span>流動的港口</span></div><div class="label"><ul><li><span><i class="mark">115-09-19</i></span></li></ul></div>
<div class="p"><p><span>基隆，這座面海而生的城市。</span></p></div></div></a></li></ul>"""

KMOA_DETAIL = """
<div   class="div "  title="檔期時間(起)"   >  <div class="essay">    <div class="caption"><span>檔期時間(起)</span></div>    <div class="p">      <p><span>115-10-16</span></p>    </div>  </div></div>
<div   class="div "  title="檔期時間(訖)"   >  <div class="essay">    <div class="caption"><span>檔期時間(訖)</span></div>    <div class="p">      <p><span>116-01-24</span></p>    </div>  </div></div>
<div   class="div "  title="地點"   >  <div class="essay">    <div class="caption"><span>地點</span></div>    <div class="p">      <p><span>基隆美術館1樓、M樓</span></p>    </div>  </div></div>
<div   class="div "  title="費用"   >  <div class="essay">    <div class="caption"><span>費用</span></div>    <div class="p">      <p><span>免費</span></p>    </div>  </div></div>
"""

NMMST = """<div class='gallery words_zoom'>
<div class='ga ga_effects'><a href='https://www.nmmst.gov.tw/chhtml/newsdetail/221/11010/0' title='連至115/10/01-116/11/30「海怪與王子號」水下文化資產校園巡迴微型展'><div class='gaimg'><img src='https://www.nmmst.gov.tw/other/a.jpg' alt='*'></div></a></div>
<div class='ga ga_effects'><a href='https://www.nmmst.gov.tw/chhtml/newsdetail/221/10634/0' title='連至115/06/05-116/05/02《極地探險》Exploring the Poles 特展'><div class='gaimg'><img src='https://www.nmmst.gov.tw/other/b.jpg' alt='*'></div></a></div>
</div>"""


class NtcamTest(unittest.TestCase):
    def test_parse(self):
        paid, free = ntcam.parse(NTCAM_ITEMS)
        self.assertEqual((paid["start"], paid["end"]), (date(2026, 8, 29), date(2026, 11, 22)))
        self.assertEqual(paid["price"]["min"], 100)
        self.assertEqual(paid["ticket_url"], "https://ntcam.fonticket.com/?lang=zh_TW")
        self.assertEqual(paid["image"], "https://ntcart.museum/retrieve/exhibition/20260807100836.jpg")
        self.assertTrue(free["price"]["free"])
        self.assertIsNone(free["image"])
        self.assertEqual(free["city"], "新北市")


class NtpcMuseumsTest(unittest.TestCase):
    def test_parse_feed(self):
        recs = ntpc_museums.parse_feed(RSS, "新北市立十三行博物館", "新北市八里區博物館路200號")
        self.assertEqual([r["title"] for r in recs], ["山彩疊疊-唐榕個展", "馭風乘浪-古代南島船舶特展", "阮ê海海人生"])
        self.assertEqual((recs[0]["start"], recs[0]["end"]), (date(2026, 10, 16), date(2026, 11, 15)))
        self.assertEqual((recs[1]["start"], recs[1]["end"]), (date(2026, 7, 25), date(2027, 5, 9)))
        self.assertEqual(recs[1]["venue"], "新北市立十三行博物館 第二特展廳")
        # 沒寫展期時用 <enddate> 的前一天
        self.assertEqual((recs[2]["start"], recs[2]["end"]), (None, date(2027, 3, 1)))
        self.assertTrue(recs[0]["url"].endswith("xsmsid=0J1&sid=0Q2"))


class NtpcEventsTest(unittest.TestCase):
    def test_filters_and_dates(self):
        base = {"activeDate": "10/02/2026", "activeEndDate": "11/15/2026", "place": "新北市土城藝文館",
                "address": "新北市土城區和平路24號", "money": "", "aboutUrl": "https://www.ntpc.gov.tw/x", "picUrl": ""}
        recs = ntpc_events.parse([
            {**base, "title": "「翰墨傳心」書法聯展"},
            {**base, "title": "兒童繪本書展"},
            {**base, "title": "社區發展講座"},
            {**base, "title": "里民大會"},
        ])
        self.assertEqual([r["title"] for r in recs], ["「翰墨傳心」書法聯展"])
        self.assertEqual((recs[0]["start"], recs[0]["end"]), (date(2026, 10, 2), date(2026, 11, 15)))


class KmoaTest(unittest.TestCase):
    def test_list_and_detail(self):
        [item] = kmoa.parse_list(KMOA_LIST)
        self.assertEqual(item["title"], "流動的港口《瓶中船 Ship》")
        self.assertEqual(item["image"], "https://klctb-ws.klcg.gov.tw/001/Upload/449/a.png")
        rec = kmoa.build_record(item, kmoa.parse_detail(KMOA_DETAIL))
        self.assertEqual((rec["start"], rec["end"]), (date(2026, 10, 16), date(2027, 1, 24)))
        self.assertEqual(rec["venue"], "基隆美術館1樓、M樓")
        self.assertTrue(rec["price"]["free"])
        self.assertEqual(rec["city"], "基隆市")


class NmmstTest(unittest.TestCase):
    def test_parse_skips_touring(self):
        [rec] = nmmst.parse_list(NMMST)
        self.assertEqual(rec["title"], "《極地探險》Exploring the Poles 特展")
        self.assertEqual((rec["start"], rec["end"]), (date(2026, 6, 5), date(2027, 5, 2)))
        self.assertEqual(rec["image"], "https://www.nmmst.gov.tw/other/b.jpg")


if __name__ == "__main__":
    unittest.main()
