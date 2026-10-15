"""
資料來源。每個來源模組需提供：
  SOURCE_ID, SOURCE_NAME, SOURCE_URL 與 collect() -> list[dict]
collect() 回傳的每筆資料欄位：
  source, source_id, title, venue, address, lat, lng, start(date), end(date),
  price(dict, 見 normalize.parse_price), url, image, organizer, description
  （可選）ticket_url

SOURCES 的順序即合併重複展覽時的優先順序：場館官方資料優先。
"""

from . import culture_express, moc, ntsec, tfam

SOURCES = [tfam, ntsec, culture_express, moc]
