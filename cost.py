"""AI cost estimation + month-to-date tracking.

Costs are ESTIMATES computed from token counts × published Haiku rates
(config.AI_PRICE_*), not your actual Anthropic bill. Good for a daily
sanity-check; not accounting-grade.

Month-to-date is persisted in cost/mtd.json, committed by the workflow like
the seen/ state. It resets automatically when the month changes.
"""
from __future__ import annotations

import datetime as dt
import json
import os

import config

COST_DIR = os.path.join(os.path.dirname(__file__), "cost")
MTD_PATH = os.path.join(COST_DIR, "mtd.json")


def estimate_cost(usage: dict) -> float:
    """USD estimate for a token usage dict {'input': n, 'output': n}."""
    inp = usage.get("input", 0) / 1_000_000 * config.AI_PRICE_INPUT_PER_MTOK
    out = usage.get("output", 0) / 1_000_000 * config.AI_PRICE_OUTPUT_PER_MTOK
    return inp + out


def _load() -> dict:
    if not os.path.exists(MTD_PATH):
        return {}
    with open(MTD_PATH, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def record_and_summarize(usage: dict) -> dict:
    """Add this run's usage to the month-to-date total (resetting on a new
    month) and return a summary dict for the email footer.
    """
    today = dt.date.today()
    month_key = today.strftime("%Y-%m")
    month_name = today.strftime("%B")

    today_cost = estimate_cost(usage)

    data = _load()
    # Reset if the stored month isn't the current one.
    if data.get("month") != month_key:
        data = {"month": month_key, "input": 0, "output": 0, "cost": 0.0}

    data["input"] = data.get("input", 0) + usage.get("input", 0)
    data["output"] = data.get("output", 0) + usage.get("output", 0)
    data["cost"] = data.get("cost", 0.0) + today_cost

    os.makedirs(COST_DIR, exist_ok=True)
    with open(MTD_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=0)

    return {
        "today_cost": today_cost,
        "today_input": usage.get("input", 0),
        "today_output": usage.get("output", 0),
        "month_cost": data["cost"],
        "month_name": month_name,
    }
