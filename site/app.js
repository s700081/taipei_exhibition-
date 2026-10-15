(() => {
  "use strict";

  const DATA_URL = "data/exhibitions.json";
  const TAIPEI_CENTER = [25.05, 121.54];
  const DAY_MS = 86400000;
  const ENDING_SOON_DAYS = 14;
  const DISTRICTS = ["中正區", "大同區", "中山區", "松山區", "大安區", "萬華區",
    "信義區", "士林區", "北投區", "內湖區", "南港區", "文山區"];
  const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];
  const APPROX = new Set(["road", "district", "none"]);

  // ---------- 日期（一律以台北時間計算） ----------

  const todayStr = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date());
  const dayNum = (iso) => (iso ? Math.round(Date.parse(`${iso}T00:00:00Z`) / DAY_MS) : null);
  const TODAY = dayNum(todayStr);
  const fromDayNum = (n) => new Date(n * DAY_MS);
  const dow = fromDayNum(TODAY).getUTCDay();
  // 本週末：週六、週日；若今天是週日則只算今天
  const WEEKEND_START = dow === 0 ? TODAY : TODAY + (6 - dow);
  const WEEKEND_END = dow === 0 ? TODAY : WEEKEND_START + 1;

  function formatDay(n, withYear) {
    const d = fromDayNum(n);
    const y = d.getUTCFullYear();
    const md = `${d.getUTCMonth() + 1}/${d.getUTCDate()}`;
    return `${withYear ? `${y}/` : ""}${md}（${WEEKDAYS[d.getUTCDay()]}）`;
  }

  function formatRange(ex) {
    const thisYear = fromDayNum(TODAY).getUTCFullYear();
    const y = (n) => fromDayNum(n).getUTCFullYear();
    if (ex.s == null && ex.e == null) return "未提供";
    if (ex.s == null) return `至 ${formatDay(ex.e, y(ex.e) !== thisYear)}`;
    if (ex.e == null) return `${formatDay(ex.s, y(ex.s) !== thisYear)} 起`;
    const showYear = y(ex.s) !== thisYear || y(ex.e) !== thisYear;
    return `${formatDay(ex.s, showYear)} – ${formatDay(ex.e, showYear)}`;
  }

  // ---------- 小工具 ----------

  const $ = (sel, root = document) => root.querySelector(sel);
  const setText = (sel, text) => {
    const node = $(sel);
    if (node) node.textContent = text;
  };
  const norm = (s) => (s || "").toLowerCase().replace(/台/g, "臺").replace(/\s+/g, "");

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function safeUrl(u) {
    if (!u) return null;
    try {
      const url = new URL(u);
      return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
    } catch {
      return null;
    }
  }

  // ---------- 狀態 ----------

  const state = {
    all: [],
    q: "",
    when: "all",
    price: "all",
    topic: "all",
    district: "all",
    sort: "ending",
    activeId: null,
  };

  function decorate(ex) {
    const s = dayNum(ex.start);
    const e = dayNum(ex.end);
    const out = { ...ex, s, e, search: norm([ex.title, ex.venue, ex.organizer, ex.district, ex.address, ...(ex.keywords || [])].join(" ")) };
    if (s != null && s > TODAY) {
      out.phase = "upcoming";
      out.daysUntil = s - TODAY;
    } else {
      out.phase = "ongoing";
      out.daysLeft = e != null ? e - TODAY : null;
    }
    // 展期超過一年，或沒有結束日期且已展出一年以上
    out.longRun = s != null && (e != null ? e - s > 365 : TODAY - s > 365);
    return out;
  }

  function statusBadges(ex) {
    const badges = [];
    if (ex.phase === "upcoming") {
      badges.push(["upcoming", ex.daysUntil === 1 ? "明天開展" : `${ex.daysUntil} 天後開展`]);
    } else if (ex.daysLeft === 0) {
      badges.push(["ending", "今天最後一天"]);
    } else if (ex.daysLeft != null && ex.daysLeft <= ENDING_SOON_DAYS) {
      badges.push(["ending", `剩 ${ex.daysLeft} 天`]);
    } else {
      badges.push(["ongoing", "展出中"]);
    }
    if (ex.longRun) badges.push(["", "長期展"]);
    if (ex.price && ex.price.free === true) badges.push(["free", "免費"]);
    return badges;
  }

  function priceText(price) {
    if (!price) return { text: "未提供", free: false };
    if (price.free === true) {
      const t = price.text && price.text.length <= 24 ? price.text : "免費";
      return { text: t, free: true };
    }
    if (price.min != null) {
      const range = price.min === price.max ? `NT$${price.min}` : `NT$${price.min}–${price.max}`;
      const detail = (price.tickets || []).slice(0, 4).map((t) => `${t.name} ${t.amount}`).join("・");
      return { text: detail && price.tickets.length > 1 ? `${range}（${detail}）` : range, free: false };
    }
    return { text: price.text || "未提供", free: false };
  }

  function matches(ex) {
    if (ex.e != null && ex.e < TODAY) return false;
    if (state.q && !state.q.split(/\s+/).every((w) => ex.search.includes(norm(w)))) return false;
    if (state.district !== "all" && ex.district !== state.district) return false;
    if (state.topic !== "all" && !(ex.topics || []).includes(state.topic)) return false;
    if (state.price === "free" && !(ex.price && ex.price.free === true)) return false;
    if (state.price === "paid" && !(ex.price && ex.price.free === false)) return false;
    switch (state.when) {
      case "ongoing":
        return ex.phase === "ongoing";
      case "ending":
        return ex.phase === "ongoing" && ex.daysLeft != null && ex.daysLeft <= ENDING_SOON_DAYS;
      case "upcoming":
        return ex.phase === "upcoming";
      case "weekend":
        return (ex.s == null || ex.s <= WEEKEND_END) && (ex.e == null || ex.e >= Math.max(TODAY, WEEKEND_START));
      default:
        return true;
    }
  }

  const sorters = {
    ending: (a, b) => (a.e ?? 1e9) - (b.e ?? 1e9) || (a.s ?? 0) - (b.s ?? 0),
    newest: (a, b) => (b.s ?? 0) - (a.s ?? 0) || (a.e ?? 1e9) - (b.e ?? 1e9),
    cheapest: (a, b) => priceRank(a) - priceRank(b) || (a.e ?? 1e9) - (b.e ?? 1e9),
  };

  function priceRank(ex) {
    const p = ex.price || {};
    if (p.free === true) return 0;
    if (p.min != null) return p.min;
    return 1e6;
  }

  // ---------- 地圖 ----------

  let map;
  let cluster;
  let needsFit = true;
  const markersByKey = new Map();
  const keyById = new Map();

  function initMap() {
    map = L.map("map", { zoomControl: true, scrollWheelZoom: true }).setView(TAIPEI_CENTER, 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    cluster = L.markerClusterGroup({
      showCoverageOnHover: false,
      maxClusterRadius: 36,
      spiderfyOnMaxZoom: true,
      // 群集上顯示的是展覽檔數，而不是場館數
      iconCreateFunction: (c) => {
        const n = c.getAllChildMarkers().reduce((sum, m) => sum + (m.options.count || 1), 0);
        const size = n < 10 ? "small" : n < 30 ? "medium" : "large";
        return L.divIcon({
          html: `<div><span>${n}</span></div>`,
          className: `marker-cluster marker-cluster-${size}`,
          iconSize: L.point(40, 40),
        });
      },
    });
    map.addLayer(cluster);
  }

  function placeKey(ex) {
    return `${ex.lat.toFixed(4)},${ex.lng.toFixed(4)}`;
  }

  function popupHtml(group) {
    const first = group[0];
    const venue = first.venue || first.address || "";
    const approx = APPROX.has(first.geo_precision)
      ? '<p class="addr">⚠ 約略位置（僅知所在區域）</p>'
      : first.address ? `<p class="addr">${escapeHtml(first.address)}</p>` : "";
    const items = group.map((ex) => {
      const href = safeUrl(ex.url);
      const title = href
        ? `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(ex.title)}</a>`
        : `<strong>${escapeHtml(ex.title)}</strong>`;
      return `
      <li>
        ${title}
        <span class="sub">${escapeHtml(formatRange(ex))}・${escapeHtml(priceText(ex.price).text)}</span>
      </li>`;
    }).join("");
    return `<div class="popup"><h3>${escapeHtml(venue)}</h3>${approx}<ul>${items}</ul></div>`;
  }

  function renderMap(list) {
    cluster.clearLayers();
    markersByKey.clear();
    keyById.clear();

    const groups = new Map();
    for (const ex of list) {
      if (ex.lat == null || ex.lng == null) continue;
      const key = placeKey(ex);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(ex);
      keyById.set(ex.id, key);
    }

    const markers = [];
    for (const [key, group] of groups) {
      const approx = group.every((ex) => APPROX.has(ex.geo_precision));
      const icon = L.divIcon({
        className: "",
        html: `<div class="pin${approx ? " approx" : ""}"><span>${group.length}</span></div>`,
        iconSize: [30, 30],
        iconAnchor: [4, 30],
        popupAnchor: [11, -28],
      });
      const marker = L.marker([group[0].lat, group[0].lng], {
        icon,
        title: group[0].venue || "",
        keyboard: true,
        count: group.length,
      });
      marker.bindPopup(() => popupHtml(group), { maxWidth: 300, minWidth: 220 });
      markersByKey.set(key, marker);
      markers.push(marker);
    }
    cluster.addLayers(markers);
    return markers;
  }

  // 地圖隱藏時（手機列表模式）無法計算範圍，等第一次顯示時再縮放到全部標記
  function fitAll() {
    if (!needsFit || map.getSize().x === 0) return;
    const markers = cluster.getLayers();
    if (markers.length) {
      map.fitBounds(L.featureGroup(markers).getBounds(), { padding: [30, 30], maxZoom: 14 });
    }
    needsFit = false;
  }

  function focusOnMap(id) {
    const key = keyById.get(id);
    const marker = key && markersByKey.get(key);
    if (!marker) return false;
    needsFit = false;
    cluster.zoomToShowLayer(marker, () => {
      if (map.getZoom() < 15) map.setView(marker.getLatLng(), 15);
      marker.openPopup();
    });
    return true;
  }

  // ---------- 列表 ----------

  const cardsEl = $("#cards");
  const cardById = new Map();

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  // 卡片完全由 JS 產生，不依賴 index.html 的結構（避免瀏覽器快取到舊版頁面時出錯）
  function buildCard(ex) {
    const node = el("li", "card");
    node.dataset.id = ex.id;
    const article = el("article");
    const img = el("img", "thumb");
    img.alt = "";
    img.loading = "lazy";
    img.referrerPolicy = "no-referrer";
    const body = el("div", "body");
    const status = el("p", "status");
    const titleEl = el("h2", "title");
    const venue = el("p", "venue");
    const desc = el("p", "desc", ex.description || "");
    const facts = el("dl", "facts");
    const datesRow = el("div");
    datesRow.append(el("dt", "", "展期"), el("dd", "dates", formatRange(ex)));
    const priceRow = el("div");
    const priceEl = el("dd", "price");
    priceRow.append(el("dt", "", "票價"), priceEl);
    facts.append(datesRow, priceRow);
    const links = el("p", "links");
    body.append(status, titleEl, venue, desc, facts, links);
    article.append(img, body);
    node.append(article);

    const imgUrl = safeUrl(ex.image);
    if (imgUrl) {
      img.src = imgUrl;
      img.addEventListener("error", () => {
        img.hidden = true;
        article.classList.add("no-image");
      });
    } else {
      img.hidden = true;
      article.classList.add("no-image");
    }

    for (const [cls, label] of statusBadges(ex)) {
      status.append(el("span", `badge ${cls}`.trim(), label));
    }

    // 點標題直接開啟展覽資訊
    const infoUrl = safeUrl(ex.url);
    if (infoUrl) {
      const a = document.createElement("a");
      a.className = "title-link";
      a.href = infoUrl;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.title = "開啟展覽資訊（新分頁）";
      a.textContent = ex.title;
      titleEl.append(a);
    } else {
      titleEl.textContent = ex.title;
    }

    venue.textContent = [ex.venue, ex.district].filter(Boolean).join("・");
    if (APPROX.has(ex.geo_precision)) {
      const approx = document.createElement("span");
      approx.className = "approx";
      approx.textContent = "（約略位置）";
      venue.append(" ", approx);
    }

    const price = priceText(ex.price);
    priceEl.textContent = price.text;
    if (price.free) priceEl.classList.add("free");
    if (ex.price && ex.price.text && ex.price.text !== price.text) priceEl.title = ex.price.text;

    const addLink = (url, label) => {
      const href = safeUrl(url);
      if (!href) return;
      const a = document.createElement("a");
      a.href = href;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = label;
      links.append(a);
    };
    if (ex.lat != null) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "map-btn";
      btn.textContent = "地圖位置";
      btn.addEventListener("click", () => selectExhibition(ex.id));
      links.append(btn);
    }
    if (ex.ticket_url && ex.ticket_url !== ex.url) addLink(ex.ticket_url, "購票 ↗");
    if (ex.lat != null) {
      const q = APPROX.has(ex.geo_precision) ? `${ex.venue || ""} ${ex.address || ""}` : `${ex.lat},${ex.lng}`;
      addLink(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`, "導航 ↗");
    }
    return node;
  }

  function renderList(list) {
    cardsEl.replaceChildren(...list.map((ex) => {
      let card = cardById.get(ex.id);
      if (!card) {
        card = buildCard(ex);
        cardById.set(ex.id, card);
      }
      card.classList.toggle("active", ex.id === state.activeId);
      return card;
    }));
    const empty = $("#empty");
    if (empty) empty.hidden = list.length > 0;
    const total = state.all.filter((ex) => ex.e == null || ex.e >= TODAY).length;
    setText("#count", list.length === total
      ? `共 ${total} 檔展覽`
      : `符合條件 ${list.length} 檔（共 ${total} 檔）`);
  }

  // ---------- 互動 ----------

  const layout = $(".layout");
  const narrowQuery = window.matchMedia("(max-width: 820px)");
  const isNarrow = () => narrowQuery.matches;

  // 檢視模式：寬螢幕可選「地圖＋列表 / 只看列表」，手機可選「列表 / 地圖」，各自記住偏好
  const VIEW_KEY = "taipei-exhibition:view";
  const viewPref = { wide: "split", narrow: "list" };
  try {
    Object.assign(viewPref, JSON.parse(localStorage.getItem(VIEW_KEY)) || {});
  } catch {
    /* 無法使用 localStorage 時用預設值 */
  }

  function currentView() {
    if (isNarrow()) return viewPref.narrow === "map" ? "map" : "list";
    return viewPref.wide === "list" ? "list" : "split";
  }

  function applyView() {
    const view = currentView();
    layout.dataset.view = view;
    document.querySelectorAll(".view-toggle button").forEach((b) => {
      b.setAttribute("aria-selected", String(b.dataset.view === view));
    });
    if (view !== "list" && map) {
      setTimeout(() => {
        map.invalidateSize();
        fitAll();
      }, 0);
    }
  }

  function setView(view) {
    viewPref[isNarrow() ? "narrow" : "wide"] = view;
    try {
      localStorage.setItem(VIEW_KEY, JSON.stringify(viewPref));
    } catch {
      /* 忽略 */
    }
    applyView();
  }

  // 「地圖位置」：標示選取的卡片並在地圖上定位；地圖目前隱藏的話先切回有地圖的檢視
  function selectExhibition(id) {
    state.activeId = id;
    cardById.forEach((card, cid) => card.classList.toggle("active", cid === id));
    history.replaceState(null, "", `#ex-${id}`);
    const mapHidden = currentView() === "list";
    if (mapHidden) setView(isNarrow() ? "map" : "split");
    setTimeout(() => focusOnMap(id), mapHidden ? 50 : 0);
  }

  function apply() {
    const list = state.all.filter(matches).sort(sorters[state.sort]);
    renderList(list);
    renderMap(list);
    return list;
  }

  function bindControls() {
    // 找不到的控制項（例如瀏覽器快取到舊版頁面）就略過，不讓整個網站壞掉
    let timer;
    $("#q")?.addEventListener("input", (e) => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        state.q = e.target.value.trim();
        apply();
      }, 150);
    });
    $("#when")?.addEventListener("click", (e) => {
      const btn = e.target.closest(".chip");
      if (!btn) return;
      state.when = btn.dataset.value;
      $("#when").querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", String(c === btn)));
      apply();
    });
    for (const id of ["topic", "price", "district", "sort"]) {
      $(`#${id}`)?.addEventListener("change", (e) => {
        state[id] = e.target.value;
        apply();
      });
    }
    document.querySelectorAll(".view-toggle button").forEach((b) => {
      b.addEventListener("click", () => setView(b.dataset.view));
    });
    narrowQuery.addEventListener("change", applyView);
  }

  function fillDistricts(list) {
    const counts = new Map();
    for (const ex of list) {
      if (ex.district) counts.set(ex.district, (counts.get(ex.district) || 0) + 1);
    }
    const select = $("#district");
    if (!select) return;
    for (const d of DISTRICTS) {
      if (!counts.has(d)) continue;
      const opt = document.createElement("option");
      opt.value = d;
      opt.textContent = `${d}（${counts.get(d)}）`;
      select.append(opt);
    }
  }

  function renderMeta(data) {
    const updated = data.updated_at ? new Date(data.updated_at) : null;
    const fmt = updated
      ? new Intl.DateTimeFormat("zh-TW", {
        timeZone: "Asia/Taipei", year: "numeric", month: "numeric", day: "numeric",
        hour: "2-digit", minute: "2-digit", hour12: false,
      }).format(updated)
      : "未知";
    setText("#meta", `資料更新：${fmt}・每週自動更新`);

    const sources = $("#sources");
    if (!sources) return;
    (data.sources || []).forEach((src, i) => {
      if (i > 0) sources.append("、");
      const href = safeUrl(src.url);
      const el = document.createElement(href ? "a" : "span");
      if (href) {
        el.href = href;
        el.target = "_blank";
        el.rel = "noopener noreferrer";
      }
      el.textContent = src.name + (src.ok === false ? "（本次更新失敗，沿用上次資料）" : "");
      sources.append(el);
    });
  }

  async function main() {
    initMap();
    applyView();
    bindControls();
    let data;
    try {
      const resp = await fetch(DATA_URL, { cache: "no-cache" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      data = await resp.json();
    } catch (err) {
      setText("#meta", "資料載入失敗，請稍後再試。");
      console.error(err);
      return;
    }
    state.all = (data.exhibitions || []).map(decorate);
    renderMeta(data);
    fillDistricts(state.all);
    const list = apply();

    fitAll();

    const m = location.hash.match(/^#ex-([\w-]+)$/);
    if (m && list.some((ex) => ex.id === m[1])) {
      const card = cardById.get(m[1]);
      state.activeId = m[1];
      card.classList.add("active");
      card.scrollIntoView({ block: "center" });
      if (currentView() !== "list") focusOnMap(m[1]);
    }
  }

  main().catch((err) => {
    console.error(err);
    setText("#meta", "網頁載入時發生錯誤，請重新整理（Ctrl+F5 或下拉重新載入）。");
  });
})();
