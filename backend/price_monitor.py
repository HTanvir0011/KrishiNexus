"""Staple price monitor: WFP retail prices, krishi-price-v1 forecasts and Dhaka wholesale-retail margin flags.

Everything here is read from the outputs of the Kaggle run `krishinexus-price-intelligence`, installed in
`backend/models/price/` (TRAINING_PLAN.md section 8b). The forecast scorecard comes from that run's report, never from
code. When the files are missing, the monitor says so instead of inventing numbers.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

PRICE_DIR = Path(__file__).resolve().parent / "models" / "price"


class PriceSeriesView(BaseModel):
    key: str
    staple: str
    division: str
    unit: str
    last_month: str
    last_price_tk: float
    change_1m_pct: float | None
    change_12m_pct: float | None
    forecast: list[dict[str, Any]]
    history: list[list[Any]]


class PriceMonitorReport(BaseModel):
    status: Literal["installed", "not_installed"]
    division: str
    divisions: list[str]
    series: list[PriceSeriesView]
    model_chosen_on_validation: str | None
    data_through: str | None
    test_mean_smape: dict[str, float] | None
    targets: dict[str, Any] | None
    margin_flags: list[dict[str, Any]]
    margin_note: str | None
    source: dict[str, Any] | None
    note: str


@lru_cache(maxsize=1)
def _load() -> tuple[dict[str, Any], dict[str, Any]] | None:
    report, forecasts = PRICE_DIR / "price_eval_report.json", PRICE_DIR / "price_forecasts.json"
    if not (report.exists() and forecasts.exists()):
        return None
    return json.loads(report.read_text(encoding="utf-8")), json.loads(forecasts.read_text(encoding="utf-8"))


def _change(history: list[list[Any]], months_back: int) -> float | None:
    """Percent change from the price `months_back` calendar months before the last one, when that month was observed."""
    year, month = map(int, history[-1][0].split("-"))
    total = year * 12 + month - 1 - months_back
    earlier = dict(history).get(f"{total // 12:04d}-{total % 12 + 1:02d}")
    return round((history[-1][1] / earlier - 1) * 100, 2) if earlier else None


def price_monitor(division: str = "Dhaka") -> PriceMonitorReport:
    loaded = _load()
    if loaded is None:
        return PriceMonitorReport(status="not_installed", division=division, divisions=[], series=[],
                                  model_chosen_on_validation=None, data_through=None, test_mean_smape=None, targets=None,
                                  margin_flags=[], margin_note=None, source=None,
                                  note="Run the Kaggle notebook krishinexus-price-intelligence and copy its outputs to "
                                       "backend/models/price/ (TRAINING_PLAN.md section 8b).")
    report, forecasts = loaded
    divisions = sorted({s["division"] for s in forecasts["series"]})
    if division not in divisions:
        raise ValueError(f"unknown division '{division}'; choose one of {', '.join(divisions)}")
    chosen = report["chosen_on_validation"]
    series = [PriceSeriesView(**{k: s[k] for k in ("key", "staple", "division", "unit", "last_month", "last_price_tk",
                                                    "forecast", "history")},
                              change_1m_pct=_change(s["history"], 1), change_12m_pct=_change(s["history"], 12))
              for s in forecasts["series"] if s["division"] == division]
    spread = report["spread_anomalies"]
    data = report["data"]
    return PriceMonitorReport(
        status="installed", division=division, divisions=divisions, series=series, model_chosen_on_validation=chosen,
        data_through=forecasts["made_from_data_through"],
        test_mean_smape={"chosen": report["mean_smape"]["test"][chosen], "naive": report["mean_smape"]["test"]["naive"]},
        targets=report["targets"], margin_flags=sorted(spread["flagged"], key=lambda f: f["month"])[-8:],
        margin_note=spread["note"],
        source={"name": data["source"], "licence": data["licence"], "sha256": data["sha256"],
                "hdx_last_modified": data.get("hdx_last_modified")},
        note="Forecasts are shown beside 'no change' because, on the held-out test year, the chosen model's error was "
             "measured against that baseline (test_mean_smape).",
    )
