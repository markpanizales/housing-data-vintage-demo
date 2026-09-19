"""Pull a FRED series into the bitemporal store.

Two sources, deliberately separated:

  current_only()  - no API key. The series as it looks TODAY. This is what a naive
                    backtest reads, and it is all you can get without a key.
  all_vintages()  - needs a free FRED API key. Every value as originally published
                    and at each subsequent revision (ALFRED's archive).

A trap worth knowing: https://fred.stlouisfed.org/graph/fredgraph.csv accepts a
`vintage_date` parameter and silently ignores it. Same bytes back, no error. If you
build a "vintage-correct" backtest on that endpoint you get current data wearing a
vintage label, which is the exact failure this repo is about.
"""
import csv
import io
import os
import datetime as dt
import requests

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_API = "https://api.stlouisfed.org/fred/series/observations"


def _key():
    key = os.environ.get("FRED_API_KEY")
    if not key:
        path = os.path.expanduser("~/git/claude_workspace/personal-assistant/.secrets/fred/api_key.txt")
        if os.path.exists(path):
            key = open(path).read().strip()
    return key


def current_only(series_id):
    """[(series_id, period, as_of, value)] with as_of = today. No key needed."""
    r = requests.get(FRED_CSV, params={"id": series_id}, timeout=30)
    r.raise_for_status()
    today = dt.date.today().isoformat()
    rows = []
    for rec in csv.DictReader(io.StringIO(r.text)):
        period = rec.get("observation_date") or rec.get("DATE")
        raw = rec.get(series_id) or rec.get(series_id.upper()) or ""
        if period and raw not in ("", "."):
            rows.append((series_id, period, today, float(raw)))
    return rows


def all_vintages(series_id):
    """Every (period, as_of, value) FRED has ever published for this series.

    output_type=2 returns the full vintage matrix in one request: one column per
    vintage date, one row per period.
    """
    key = _key()
    if not key:
        raise RuntimeError(
            "No FRED API key. Get a free one in ~2 minutes at "
            "https://fredaccount.stlouisfed.org/apikey then either export "
            "FRED_API_KEY=... or save it to .secrets/fred/api_key.txt"
        )
    r = requests.get(
        FRED_API,
        params={
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "output_type": 2,          # all vintages
            "realtime_start": "1776-07-04",
            "realtime_end": "9999-12-31",
        },
        timeout=90,
    )
    if not r.ok:
        # requests puts the full URL in the exception, api_key and all. Never let a
        # traceback from this repo print somebody's key.
        raise RuntimeError(
            f"FRED API returned {r.status_code} for {series_id}. "
            f"Some series do not support output_type=2 over the full range."
        )
    rows = []
    for obs in r.json()["observations"]:
        period = obs["date"]
        for field, raw in obs.items():
            if not field.startswith(f"{series_id}_") or raw in ("", "."):
                continue
            vintage = field.split("_", 1)[1]           # SERIES_YYYYMMDD
            as_of = f"{vintage[:4]}-{vintage[4:6]}-{vintage[6:]}"
            rows.append((series_id, period, as_of, float(raw)))
    return rows
