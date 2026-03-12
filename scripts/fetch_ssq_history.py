from __future__ import annotations

import csv
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"


def fetch_page(page_no: int, page_size: int = 30) -> list[dict]:
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
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.cwl.gov.cn/",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("state") != 0:
        raise RuntimeError(f"API 返回异常: {payload}")
    return payload.get("result", [])


def normalize(row: dict) -> dict[str, str] | None:
    # 兼容字段: red/blue/code/date 或 red/blue/week/sales 等
    red = (row.get("red") or "").replace(",", " ").split()
    blue = str(row.get("blue") or "").strip()
    if len(red) != 6 or not blue.isdigit():
        return None
    if not all(x.isdigit() for x in red):
        return None

    reds = [int(x) for x in red]
    blue_num = int(blue)
    if len(set(reds)) != 6 or any(n < 1 or n > 33 for n in reds) or not (1 <= blue_num <= 16):
        return None

    reds.sort()
    return {
        "issue": str(row.get("code") or row.get("issue") or ""),
        "date": str(row.get("date") or ""),
        "red1": str(reds[0]),
        "red2": str(reds[1]),
        "red3": str(reds[2]),
        "red4": str(reds[3]),
        "red5": str(reds[4]),
        "red6": str(reds[5]),
        "blue": str(blue_num),
    }


def main() -> int:
    out_path = Path("data/ssq_history.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, str]] = []
    page = 1
    while True:
        page_rows = fetch_page(page_no=page, page_size=100)
        if not page_rows:
            break
        for raw in page_rows:
            parsed = normalize(raw)
            if parsed:
                all_rows.append(parsed)
        page += 1

    # 去重（按 issue）
    unique = {}
    for r in all_rows:
        if r["issue"]:
            unique[r["issue"]] = r
    ordered = [unique[k] for k in sorted(unique.keys())] if unique else all_rows

    if not ordered:
        raise RuntimeError("未抓取到有效双色球开奖记录")

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["issue", "date", "red1", "red2", "red3", "red4", "red5", "red6", "blue"],
        )
        writer.writeheader()
        writer.writerows(ordered)

    print(f"已写入 {len(ordered)} 条记录 -> {out_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"抓取失败: {exc}", file=sys.stderr)
        raise SystemExit(1)
