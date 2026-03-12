from __future__ import annotations

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

app = FastAPI(title="Lottery Recommendation Demo", version="0.1.0")

BASE_DIR = Path(__file__).parent
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
    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)
        self.history = self._build_history(draw_count=300)
        self.red_freq, self.blue_freq = self._freq_from_history(self.history)

    def _build_history(self, draw_count: int) -> List[Draw]:
        history: List[Draw] = []
        rng = random.Random(2024)
        for _ in range(draw_count):
            red = sorted(rng.sample(range(1, 34), 6))
            blue = rng.randint(1, 16)
            history.append(Draw(red=red, blue=blue))
        return history

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
        score += sum(self.red_freq[n] for n in red) / 1000.0
        score += self.blue_freq[blue] / 300.0

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


recommender = SSQRecommender()


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    if req.lotteryType.lower() != "ssq":
        raise HTTPException(status_code=400, detail="当前 demo 仅支持 ssq")

    items = recommender.predict(count=req.count)
    return PredictResponse(
        modelVersion="demo-rule-v1",
        generatedAt=datetime.now().isoformat(timespec="seconds"),
        numbers=items,
        disclaimer="仅供娱乐，不保证中奖。彩票具有随机性，请理性看待。",
    )
