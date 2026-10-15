# 北北基桃近期展覽地圖

每週自動抓取**臺北市、新北市、基隆市、桃園市**的近期展覽，在地圖上標出展覽地點，並列出**票價**與**展期**。

- 🗺 **地圖**：以 OpenStreetMap 顯示每個展覽場館，同一場館的多檔展覽會合併成一個標記
- 🎟 **票價**：整理成「免費」或「NT$最低–最高」，並保留各票種明細與購票連結
- 📅 **展期**：標示「展出中／剩 N 天／N 天後開展」，可篩選「本週末」「即將結束」「即將開展」
- 🔎 搜尋展覽、場館（支援「北美館」「松菸」等簡稱）、依縣市、行政區、主題（如「科學・科技」）與費用篩選
- 🗂 電腦可切換「地圖＋列表／只看列表」（只看列表時卡片多欄排列並顯示簡介），手機可切換「列表／地圖」；會記住上次的選擇
- 🔁 GitHub Actions 每週一凌晨自動更新資料並重新部署

## 資料來源

| 來源 | 內容 | 說明 |
| --- | --- | --- |
| [臺北市文化局 臺北文化快遞](https://cultureexpress.taipei/)（[臺北市資料大平臺](https://data.taipei/dataset/detail?id=9a7af75b-9abd-4ac1-b359-685fbd7dac23)） | 臺北市藝文活動（展覽類） | 主要來源，含座標、售票方式、圖片 |
| [文化部文化資料開放服務網](https://cloud.culture.tw/) | 全國藝文活動（類別 6：展覽） | 篩選出位於北北基桃的展覽 |
| [臺北市立美術館](https://www.tfam.museum/) | 目前展覽、即將展出 | 官網公開的展覽資料 |
| [國立臺灣科學教育館](https://www.ntsec.gov.tw/) | 特展、微型展 | 從官網列表頁與展覽頁讀取展期、展區；票價依官網常設展票價 |
| [華山1914文化創意產業園區](https://www.huashan1914.com/) | 類別為「展覽」的活動 | 依官網 robots.txt，從 sitemap 取得活動頁再讀取展期、展館、票價（不抓市集、快閃店） |
| [新北市美術館](https://ntcart.museum/) | 目前展覽、即將展出 | 官網展覽資料（含票價、購票連結） |
| 新北市立博物館 RSS（[鶯歌陶瓷](https://www.ceramics.ntpc.gov.tw/)、[十三行](https://www.sshm.ntpc.gov.tw/)、[淡水古蹟](https://www.tshs.ntpc.gov.tw/)） | 展覽 | 從 RSS 說明讀取展期 |
| [新北市政府 近期活動](https://data.ntpc.gov.tw/datasets/029e3fc2-1927-4534-8702-da7323be969b) | 市府、圖書館、地政事務所等的藝文展覽 | 只收標題含「展」的活動（排除書展、講座等） |
| [基隆美術館](https://kmoa.klcg.gov.tw/) | 當期展覽 | 從官網列表頁與展覽頁讀取檔期、地點、費用 |
| [國立海洋科技博物館](https://www.nmmst.gov.tw/) | 當期特展 | 從官網列表頁讀取展期 |

| [新光三越](https://www.skm.com.tw/) | 「文藝」「展售」活動 | 北北基桃分店的藝術展、快閃店；以標題排除促銷訊息 |
| [ibon售票](https://ticket.ibon.com.tw/) | 「展覽」類別 | 需購票的特展、商品展、快閃展；地址與票價取自售票頁；排除見面會、博物館門票等 |
| [Accupass 活動通](https://www.accupass.com/) | 搜尋「快閃」 | 快閃展、商品展；Accupass 沒有提供票價 |

百貨公司方面，SOGO 官網的活動頁禁止自動抓取（robots.txt），遠東百貨、誠品、KKTIX 等有機器人驗證，皆不抓取；這些地點的展覽若出現在 ibon、Accupass 或文化局資料中仍會收錄。

桃園市目前沒有可用的展覽開放資料（桃園市立美術館官網有機器人驗證，不抓取），桃園的展覽主要來自文化部資料。

同一檔展覽出現在多個來源時會自動合併（標題相同或互相包含、地點相近、展期重疊），並以場館官方資料優先。

> 政府開放資料依[政府資料開放授權條款](https://data.gov.tw/license)使用；地圖圖資 © OpenStreetMap contributors。
> 票價與展期以主辦單位公告為準。

## 運作方式

```
GitHub Actions（每週一 02:17 台北時間）
  └─ python -m scraper.main
       ├─ 各來源抓資料 → 判斷縣市，篩選北北基桃、近期（已開展或 120 天內開展、尚未結束）
       ├─ 整理票價、日期
       ├─ 定位：場館對照表 → 來源座標 → OpenStreetMap Nominatim → 行政區中心
       ├─ 合併重複展覽
       └─ 輸出 site/data/exhibitions.json（並提交回 repo）
  └─ 部署 site/ 到 GitHub Pages
```

網頁是純靜態檔案（`site/`），在瀏覽器端依「今天」計算展覽狀態，因此兩次更新之間已結束的展覽也會自動隱藏。

某個來源暫時抓取失敗時，會沿用上次抓到且尚未結束的資料；所有來源都失敗時則不覆寫資料。

## 部署到 GitHub Pages

1. **Settings → Pages → Build and deployment → Source** 選擇 **GitHub Actions**。
2. 確認要用來發布的分支是 repo 的**預設分支**（Settings → General → Default branch，建議命名為 `main`）。
   排程（schedule）只會在預設分支執行。
3. 到 **Actions → 更新展覽資料並部署網站 → Run workflow** 手動執行一次。
4. 完成後網址為 `https://<帳號>.github.io/<repo 名稱>/`。

> 免費帳號的 GitHub Pages 需要 repo 為公開。
> 工作流程每週會提交一次資料更新，repo 保持活躍，因此排程不會因 60 天無活動而被停用。

## 在本機執行

只需要 Python 3.10 以上，不需安裝任何套件。

```bash
# 抓取資料（約 1–2 分鐘）
python -m scraper.main

# 不連線 Nominatim，只用場館對照表與快取定位
python -m scraper.main --offline-geocode

# 調整收錄範圍：只收 60 天內開展的展覽
python -m scraper.main --days 60

# 執行測試
python -m unittest discover -s tests -t .

# 預覽網站（直接開啟 index.html 會因瀏覽器限制無法讀取 JSON）
python -m http.server 8000 -d site
# 然後開啟 http://localhost:8000
```

## 專案結構

```
scraper/
  main.py              主流程：抓取、篩選、定位、合併、輸出
  normalize.py         票價、日期、地址、縣市與行政區判斷
  geocode.py           地點定位（含 Nominatim 查詢與快取）
  fetch.py             HTTP 工具（只用標準函式庫）
  sources/             各資料來源（每個檔案一個來源）
  data/venues.json     北北基桃常見展覽場館座標與別名（人工確認）
  data/districts.json  各縣市行政區與中心點
  data/geocode_cache.json  Nominatim 查詢快取（自動產生）
site/
  index.html, style.css, app.js   網站（Leaflet + OpenStreetMap）
  data/exhibitions.json           輸出的展覽資料
tests/                 單元測試
.github/workflows/update.yml      每週排程與部署
```

## 常見調整

**某個場館的位置不對或常常只顯示「約略位置」**：在 `scraper/data/venues.json` 新增一筆：

```json
{"name": "場館正式名稱", "aliases": ["簡稱"], "street_keys": ["南海路49號"], "lat": 25.0315, "lng": 121.5112, "district": "中正區", "city": "臺北市"}
```

`aliases` 是會出現在來源「地點名稱」中的字串；`street_keys` 是「路段＋門牌」，用來比對地址；`city` 省略時視為臺北市。

**調整主題的判斷**：「科學・科技」編輯 `scraper/normalize.py` 的 `_SCIENCE_VENUES`（場館）與 `_SCIENCE_WORDS`（標題關鍵字）；「百貨・快閃・商品展」編輯 `_MALL_WORDS`（場館名稱）與 `_POPUP_WORDS`（標題關鍵字）。沒有任何展覽的主題不會出現在選單中。

**新增資料來源**：在 `scraper/sources/` 新增模組，提供 `SOURCE_ID`、`SOURCE_NAME`、`SOURCE_URL` 與回傳共用格式的 `collect()`（欄位見 `scraper/sources/__init__.py`），再加入 `SOURCES` 清單。

**修改更新頻率**：編輯 `.github/workflows/update.yml` 的 `cron`（使用 UTC 時間）。
