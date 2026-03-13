from __future__ import annotations

import csv
import json
import ssl
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar
from pathlib import Path
from datetime import datetime

# 接口地址
API = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"

# --- 核心修复：强制 SSL 上下文，防止 TLS 指纹拦截 ---
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

cookie_jar = http.cookiejar.CookieJar()
handler = urllib.request.HTTPCookieProcessor(cookie_jar)
opener = urllib.request.build_opener(handler, urllib.request.HTTPSHandler(context=ssl_context))


def fetch_page(page_no: int, page_size: int = 100) -> list[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.cwl.gov.cn/ygkj/wqkj/ssq/",
        "Connection": "keep-alive",
    }

    # 首次访问获取 Cookie
    if not any(c.name for c in cookie_jar):
        try:
            home_req = urllib.request.Request("https://www.cwl.gov.cn/ygkj/wqkj/ssq/", headers=headers)
            opener.open(home_req, timeout=10)
            time.sleep(2)
        except Exception:
            pass

    params = {
        "name": "ssq",
        "issueCount": "",
        "issueStart": "",
        "issueEnd": "",
        "dayStart": "",
        "dayEnd": "",
        "pageNo": str(page_no),
        "pageSize": str(page_size),
        "systemType": "PC",
    }

    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=headers)

    try:
        with opener.open(req, timeout=30) as resp:
            content = resp.read().decode("utf-8")
            payload = json.loads(content)
            return payload.get("result", [])
    except Exception as e:
        print(f"❌ 访问接口失败: {e}")
        return []


def normalize(row: dict) -> dict[str, str] | None:
    red = (row.get("red") or "").replace(",", " ").split()
    blue = str(row.get("blue") or "").strip()
    if len(red) != 6 or not blue:
        return None

    try:
        reds = sorted([int(x) for x in red])
        return {
            "issue": str(row.get("code") or ""),
            "date": str(row.get("date") or "")[:10],
            "red1": f"{reds[0]:02d}",
            "red2": f"{reds[1]:02d}",
            "red3": f"{reds[2]:02d}",
            "red4": f"{reds[3]:02d}",
            "red5": f"{reds[4]:02d}",
            "red6": f"{reds[5]:02d}",
            "blue": f"{int(blue):02d}",
        }
    except Exception:
        return None


def main() -> int:
    _ = datetime.now()
    out_path = Path("data/ssq_10years_history.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, str]] = []
    page = 1
    # 目标：2016年3月（距今10年）
    target_year = 2016

    print("🚀 正在启动抓取任务：目标 2016 - 2026 (10年数据)...")

    while True:
        print(f"📡 正在抓取第 {page} 页...")
        page_rows = fetch_page(page_no=page, page_size=100)

        if not page_rows:
            print("🏁 抓取完成（无更多数据）。")
            break

        last_date_in_page = ""
        for raw in page_rows:
            parsed = normalize(raw)
            if parsed:
                all_rows.append(parsed)
                last_date_in_page = parsed["date"]

        # 检查日期，如果已经到了2016年以前，就停止
        if last_date_in_page and int(last_date_in_page[:4]) < target_year:
            print(f"⌛ 已到达 {target_year} 年边界，停止抓取。")
            break

        page += 1
        time.sleep(3)  # 增加延迟，防止被封 IP

    if not all_rows:
        print("⚠️ 未抓取到数据，请检查网络或更换 IP 尝试。")
        return 1

    # 按期号去重并排序
    unique = {r["issue"]: r for r in all_rows if r["issue"]}
    ordered = [unique[k] for k in sorted(unique.keys(), reverse=True)]

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["issue", "date", "red1", "red2", "red3", "red4", "red5", "red6", "blue"])
        writer.writeheader()
        writer.writerows(ordered)

    print(f"✅ 成功! 共采集 {len(ordered)} 条记录，文件已保存至: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
