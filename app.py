from __future__ import annotations

import csv
import os
import random
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.requests import Request

app = FastAPI(title="Lottery Recommendation Demo", version="0.2.0")

BASE_DIR = Path(__file__).parent
DEFAULT_HISTORY_CSV = BASE_DIR / "data" / "ssq_last_10_years.csv"
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@dataclass
class Draw:
    red: List[int]
    blue: int


class PredictRequest(BaseModel):
    lotteryType: str = Field(default="ssq")
    count: int = Field(default=5, ge=1, le=20)


class NumberItem(BaseModel):
    red: List[int]
    blue: int
    score: float


class PredictResponse(BaseModel):
    modelVersion: str
    generatedAt: str
    numbers: List[NumberItem]
    disclaimer: str


class SSQRecommender:
    def __init__(self, seed: int = 42, history_csv: Path | None = None) -> None:
        self.rng = random.Random(seed)
        csv_path = history_csv or Path(os.getenv("SSQ_HISTORY_CSV", str(DEFAULT_HISTORY_CSV)))
        self.history = self._load_history_from_csv(csv_path)
        if not self.history:
            raise ValueError(f"历史开奖数据为空，请检查文件：{csv_path}")
        self.red_freq, self.blue_freq = self._freq_from_history(self.history)

    def _load_history_from_csv(self, csv_path: Path) -> List[Draw]:
        if not csv_path.exists():
            raise FileNotFoundError(
                f"未找到真实开奖数据文件：{csv_path}。请准备包含双色球历史数据的 CSV（red1-red6,blue）"
            )

        history: List[Draw] = []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                draw = self._parse_draw_row(row)
                if draw:
                    history.append(draw)
        return history

    def _parse_draw_row(self, row: dict[str, str]) -> Draw | None:
        def as_int(value: str | None) -> int | None:
            if value is None:
                return None
            v = value.strip()
            if not v:
                return None
            if v.isdigit():
                return int(v)
            return None

        # 格式 1：red1..red6 + blue
        reds = [as_int(row.get(f"red{i}")) for i in range(1, 7)]
        blue = as_int(row.get("blue"))
        if all(n is not None for n in reds) and blue is not None:
            red_nums = sorted(int(n) for n in reds)
            if self._is_valid_ticket(red_nums, blue):
                return Draw(red=red_nums, blue=blue)

        # 格式 2：red="01 05 12 17 25 31" + blue
        red_text = row.get("red")
        if red_text:
            parts = [p for p in red_text.replace(",", " ").split() if p]
            if len(parts) == 6 and blue is not None and all(p.isdigit() for p in parts):
                red_nums = sorted(int(p) for p in parts)
                if self._is_valid_ticket(red_nums, blue):
                    return Draw(red=red_nums, blue=blue)
        return None

    def _is_valid_ticket(self, red: List[int], blue: int) -> bool:
        return (
            len(red) == 6
            and len(set(red)) == 6
            and all(1 <= n <= 33 for n in red)
            and 1 <= blue <= 16
        )

    def _freq_from_history(self, history: List[Draw]) -> tuple[Counter, Counter]:
        red_counter: Counter = Counter()
        blue_counter: Counter = Counter()
        for draw in history:
            red_counter.update(draw.red)
            blue_counter.update([draw.blue])
        return red_counter, blue_counter

    def _features(self, red: List[int]) -> dict[str, float]:
        total = sum(red)
        odd_count = sum(1 for n in red if n % 2 == 1)
        consec = sum(1 for i in range(1, len(red)) if red[i] == red[i - 1] + 1)
        return {
            "sum": total,
            "odd_count": odd_count,
            "consecutive_pairs": consec,
            "span": red[-1] - red[0],
        }

    def _score(self, red: List[int], blue: int) -> float:
        f = self._features(red)

        score = 0.0
        score += sum(self.red_freq[n] for n in red) / max(1.0, len(self.history) * 6 / 2)
        score += self.blue_freq[blue] / max(1.0, len(self.history))

        sum_center_bonus = max(0.0, 1 - abs(f["sum"] - 100) / 60)
        odd_balance_bonus = 1 - abs(f["odd_count"] - 3) / 3
        span_bonus = max(0.0, 1 - abs(f["span"] - 24) / 18)

        score += 0.8 * sum_center_bonus
        score += 0.5 * odd_balance_bonus
        score += 0.3 * span_bonus
        score -= 0.12 * f["consecutive_pairs"]
        return round(score, 3)

    def predict(self, count: int = 5, candidate_size: int = 10000) -> List[NumberItem]:
        pool: List[NumberItem] = []
        seen = set()

        while len(pool) < candidate_size:
            red = tuple(sorted(self.rng.sample(range(1, 34), 6)))
            blue = self.rng.randint(1, 16)
            key = (red, blue)
            if key in seen:
                continue
            seen.add(key)
            pool.append(NumberItem(red=list(red), blue=blue, score=self._score(list(red), blue)))

        pool.sort(key=lambda x: x.score, reverse=True)
        return pool[:count]


try:
    recommender = SSQRecommender()
    DATA_READY_ERROR = ""
except Exception as exc:  # 服务可启动，但接口会提示数据问题
    recommender = None
    DATA_READY_ERROR = str(exc)


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    if req.lotteryType.lower() != "ssq":
        raise HTTPException(status_code=400, detail="当前 demo 仅支持 ssq")
    if recommender is None:
        raise HTTPException(status_code=500, detail=f"数据未就绪：{DATA_READY_ERROR}")

    items = recommender.predict(count=req.count)
    return PredictResponse(
        modelVersion="demo-rule-v2-real-data",
        generatedAt=datetime.now().isoformat(timespec="seconds"),
        numbers=items,
        disclaimer="仅供娱乐，不保证中奖。彩票具有随机性，请理性看待。",
    )
