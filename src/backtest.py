"""Walk-forward backtest, scored two ways.

The model is deliberately dumb: persist the last year-over-year growth rate out to
the target month. The point of this repo is the evaluation, not the forecast. A good
model would only start an argument about the model.

Both runs see exactly the same PERIODS. They differ only in which VALUES they see:

  vintage  - the values as actually published at the time, and the actual is the
             value as first published after the target month. No information from
             the future anywhere.
  revised  - the same periods, but today's revised values, and today's actual. This
             is the backtest almost everyone writes.

Holding the period set identical is what makes the comparison honest: the only thing
that changes between the two numbers is data revision, not data availability.
"""
import pandas as pd

HORIZON = 12      # months ahead of the forecast date
EVAL_LAG = 3      # "first published actual" = target month + 3


def _shift(period, months):
    return (pd.Period(period, "M") + months).to_timestamp().date().isoformat()


def _months_between(a, b):
    return (pd.Period(b, "M") - pd.Period(a, "M")).n


def forecast(series, anchor, target):
    """Persist trailing 12-month growth from `anchor` out to `target`."""
    prior = _shift(anchor, -12)
    if anchor not in series or prior not in series or not series[prior]:
        return None
    h = _months_between(anchor, target)
    if h <= 0:
        return None
    growth = series[anchor] / series[prior]
    return series[anchor] * (growth ** (h / 12))


def run(store, series_id, start, end, mode, today=None):
    today = today or pd.Timestamp.today().date().isoformat()
    revised = store.as_known_on(series_id, today)
    rows = []
    origin = start
    while origin <= end:
        # What was genuinely on the screen on this date?
        known = store.as_known_on(series_id, origin)
        if not known:
            origin = _shift(origin, 1)
            continue
        cutoff = max(known)                       # latest period published by `origin`
        target = _shift(origin, HORIZON)

        if mode == "vintage":
            series = known
            actual = store.as_known_on(series_id, _shift(target, EVAL_LAG)).get(target)
        else:
            # same periods, today's values - isolates revision, not availability
            series = {p: v for p, v in revised.items() if p <= cutoff}
            actual = revised.get(target)

        fc = forecast(series, cutoff, target)
        if fc is not None and actual:
            rows.append(
                {
                    "origin": origin,
                    "anchor": cutoff,
                    "target": target,
                    "forecast": fc,
                    "actual": actual,
                    "ape": abs(fc - actual) / actual * 100,
                }
            )
        origin = _shift(origin, 1)
    return pd.DataFrame(rows)


def mape(df):
    return float(df["ape"].mean()) if len(df) else float("nan")


def compare(store, series_id, start, end):
    v = run(store, series_id, start, end, "vintage")
    r = run(store, series_id, start, end, "revised")
    if len(v) and len(r):
        merged = v.merge(r, on="origin", suffixes=("_v", "_r"))
    else:
        merged = pd.DataFrame()
    mv, mr = mape(v), mape(r)
    return {
        "vintage": v,
        "revised": r,
        "merged": merged,
        "mape_vintage": mv,
        "mape_revised": mr,
        "gap_pp": mv - mr,
        "flattery_pct": (mv - mr) / mv * 100 if mv else float("nan"),
        "n": len(merged),
    }
