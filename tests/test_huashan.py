import json
import unittest
from datetime import date

from scraper.sources import huashan

URL = "https://www.huashan1914.com/exhibition/%E6%98%9F%E7%90%83%E6%A8%82%E5%9C%92"


def page(category_name):
    data = [
        {"root": 9},
        {"id": 2, "categoryId": 3, "name": 4}, "cat-1", "event_category", category_name,
        {"id": 6, "categoryId": 7, "name": 8}, "ven-1", "event_venue", "東3A館\t展場",
        {"_id": 10, "article": 11, "aside": 23}, "w1",
        {"default": 12, "event_content": 14, "event_time": 16, "sidebar_info": 19},
        {"slug": 13, "title": 13}, "星球樂園",
        {"description": 15}, "<p>展期｜10/1-10/31</p><p>票價｜全票 300 元</p><p>主辦｜某公司</p>",
        {"start_date": 17, "end_date": 18}, "2026-09-30T16:00:00Z", "2026-10-30T16:00:00Z",
        {"organizer": 20, "ticket_link": 21}, "某公司", "https://tickets.example.com/x", "unused",
        {"category_event_category": 24, "category_event_venue": 25}, [2], [6],
    ]
    return f'<html><script type="application/json" id="__NUXT_DATA__">{json.dumps(data, ensure_ascii=False)}</script></html>'


class HuashanTest(unittest.TestCase):
    def test_exhibition_is_parsed(self):
        rec = huashan.parse_event(page("展覽"), URL)
        self.assertEqual(rec["title"], "星球樂園")
        self.assertEqual((rec["start"], rec["end"]), (date(2026, 10, 1), date(2026, 10, 31)))
        self.assertEqual(rec["venue"], "華山1914文化創意產業園區 東3A館 展場")
        self.assertEqual(rec["price"]["min"], 300)
        self.assertEqual(rec["ticket_url"], "https://tickets.example.com/x")
        self.assertEqual(rec["organizer"], "某公司")

    def test_non_exhibition_is_skipped(self):
        self.assertIsNone(huashan.parse_event(page("快閃店"), URL))

    def test_sitemap_keeps_only_current_urls(self):
        sitemap = ("<url><loc>https://www.huashan1914.com/exhibition/%E6%98%9F%E7%90%83</loc></url>"
                   "<url><loc>https://www.huashan1914.com/exhibition/event-old</loc></url>"
                   "<url><loc>https://www.huashan1914.com/space</loc></url>")
        self.assertEqual(huashan.current_event_urls(sitemap), ["https://www.huashan1914.com/exhibition/%E6%98%9F%E7%90%83"])


if __name__ == "__main__":
    unittest.main()
