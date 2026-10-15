"""簡單的 HTTP 工具（只用標準函式庫），內建重試。"""

from __future__ import annotations

import gzip
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = (
    "taipei-exhibition-map/1.0 "
    "(+https://github.com/s700081/taipei_exhibition-; weekly open-data crawler)"
)

# Python 3.13 起預設啟用 VERIFY_X509_STRICT，部分政府網站（TWCA 憑證鏈）會因缺少
# Subject Key Identifier 而驗證失敗。這裡只關閉這項額外的嚴格檢查，
# 憑證鏈與主機名稱驗證仍照常進行。
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)


def request(url: str, *, data: bytes | None = None, headers: dict | None = None,
            timeout: int = 60, retries: int = 3) -> bytes:
    req_headers = {"User-Agent": USER_AGENT, "Accept-Language": "zh-TW,zh;q=0.9"}
    req_headers.update(headers or {})
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=req_headers)
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as resp:
                body = resp.read()
            # 部分網站不論是否要求都回傳 gzip 壓縮內容
            return gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_error = e
        if attempt < retries - 1:
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"{'POST' if data else 'GET'} {url} failed: {last_error}")


def _decode_json(raw: bytes):
    return json.loads(raw.decode("utf-8-sig"))


def get_json(url: str, *, headers: dict | None = None, **kwargs):
    return _decode_json(request(url, headers={"Accept": "application/json", **(headers or {})}, **kwargs))


def post_json(url: str, payload: dict, **kwargs):
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"}
    return _decode_json(request(url, data=body, headers=headers, **kwargs))


def post_form(url: str, fields: dict, **kwargs):
    """以 application/x-www-form-urlencoded 送出表單並解析 JSON 回應。"""
    body = urllib.parse.urlencode(fields).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
               "Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
    return _decode_json(request(url, data=body, headers=headers, **kwargs))


def get_text(url: str, **kwargs) -> str:
    return request(url, **kwargs).decode("utf-8", errors="replace")
