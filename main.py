#!/usr/bin/env python3
"""Load FRED series with their full vintage history, backtest twice, report the gap.

    ./run.sh                      # all default series
    ./run.sh --series HSN1F       # just one
"""
import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import backtest
import crosswalk
import fetch
from store import Store

HERE = Path(__file__).parent
OUT = HERE / "output"

SERIES = {
    "CSUSHPINSA": "Case-Shiller national home price index",
    "HOUST": "Housing starts",
    "HSN1F": "New one-family houses sold",
    "PERMIT": "Building permits",
}


def ensure_loaded(store, sid):
    if store.vintage_count(sid):
        return True
    store.append(fetch.current_only(sid))
    try:
        store.append(fetch.all_vintages(sid))
        return True
    except RuntimeError as e:
        print(f"  {sid}: {e}")
        return False


def window_for(db, sid):
    first = db.execute(
        "SELECT MIN(as_of) FROM facts WHERE series_id=?", (sid,)
    ).fetchone()[0]
    start = (pd.Period(max(first[:7], "2005-01"), "M") + 3).to_timestamp().date()
    return start.isoformat(), "2024-06-01"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", nargs="*", default=list(SERIES))
    ap.add_argument("--db", default=str(HERE / "data" / "facts.db"))
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    store = Store(args.db)
    db = sqlite3.connect(args.db)

    print("[1/3] loading vintage archives")
    loaded = [s for s in args.series if ensure_loaded(store, s)]
    for s in loaded:
        print(f"  {s:<12} {store.vintage_count(s):>4} vintages")
    if not loaded:
        print("\nNo vintage data. A free FRED API key is needed for the archive:")
        print("  https://fredaccount.stlouisfed.org/apikey")
        return 1

    print("\n[2/3] backtests")
    rows, results = [], {}
    for sid in loaded:
        start, end = window_for(db, sid)
        r = backtest.compare(store, sid, start, end)
        if not r["n"]:
            continue
        results[sid] = r
        rows.append(
            {
                "series": sid,
                "name": SERIES.get(sid, sid),
                "window": f"{start[:7]} to {end[:7]}",
                "n": r["n"],
                "mape_vintage": round(r["mape_vintage"], 3),
                "mape_revised": round(r["mape_revised"], 3),
                "gap_pp": round(r["gap_pp"], 3),
                "leak_pct": round(r["flattery_pct"], 1),
            }
        )
        r["vintage"].to_csv(OUT / f"{sid}_vintage.csv", index=False)
        r["revised"].to_csv(OUT / f"{sid}_revised.csv", index=False)

    table = pd.DataFrame(rows)
    print(table.to_string(index=False))
    table.to_csv(OUT / "summary.csv", index=False)

    print("\n[3/3] chart + notes")
    headline = max(results, key=lambda s: abs(results[s]["flattery_pct"]))
    chart(results[headline], headline, SERIES.get(headline, headline))
    write_notes(table, results, store)
    print(f"  headline series: {headline}")

    zhvi = Path("/tmp/zhvi_zip.csv")
    if zhvi.exists():
        print("\n[4/4] ZIP / ZCTA / county crosswalk")
        xw = crosswalk.analyse(str(zhvi), cache=str(HERE / "data" / "zcta_county.txt"))
        print(f"  Zillow ZIPs {xw['zillow_zips']:,} vs {xw['zctas']:,} ZCTAs")
        print(f"  ZIPs with no ZCTA:          {xw['zips_with_no_zcta']} ({xw['pct_dropped']}%)")
        print(f"  ZCTAs spanning >1 county:   {xw['zctas_spanning_counties']:,} "
              f"({xw['pct_zctas_multi_county']}%), max {xw['max_counties_one_zcta']}")
        print(f"  naive join wrong county:    {xw['naive_county_wrong']:,} ZIPs "
              f"({xw['naive_county_wrong']/xw['zillow_zips']*100:.1f}%)")
        print(f"  naive rows {xw['naive_rows']:,} vs area-weighted {xw['weighted_rows']:,}")
        import json
        (OUT / "crosswalk.json").write_text(json.dumps(xw, indent=2))
    else:
        print("\n[4/4] crosswalk SKIPPED - Zillow ZHVI csv not at /tmp/zhvi_zip.csv")

    print(f"\n  {OUT/'results.md'}")
    return 0


def chart(res, sid, name):
    m = res["merged"]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7.5), height_ratios=[2, 1], sharex=True)
    x = pd.to_datetime(m["origin"])

    ax1.plot(x, m["ape_v"], lw=1.5, label=f"scored on vintage data (MAPE {res['mape_vintage']:.2f}%)")
    ax1.plot(x, m["ape_r"], lw=1.5, alpha=.85, label=f"scored on revised data (MAPE {res['mape_revised']:.2f}%)")
    ax1.set_title(f"{sid} — {name}\nidentical forecasts, two scorekeepers, 12-month horizon", loc="left")
    ax1.set_ylabel("absolute % error")
    ax1.legend(frameon=False, fontsize=9)
    ax1.grid(alpha=.25)

    d = m["ape_v"] - m["ape_r"]
    ax2.fill_between(x, d, 0, where=d >= 0, alpha=.55, label="revisions hide error")
    ax2.fill_between(x, d, 0, where=d < 0, alpha=.55, color="tab:red", label="revisions add error")
    ax2.axhline(0, color="black", lw=.8)
    ax2.set_ylabel("vintage − revised\n(percentage points)")
    ax2.legend(frameon=False, fontsize=8, loc="upper left")
    ax2.grid(alpha=.25)
    ax2.tick_params(axis="x", rotation=30)

    fig.tight_layout()
    fig.savefig(OUT / "backtest_comparison.png", dpi=150)
    print(f"  {OUT/'backtest_comparison.png'}")


def write_notes(table, results, store):
    cols = ["series", "name", "window", "n", "mape_vintage", "mape_revised", "gap_pp", "leak_pct"]
    md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, row in table.iterrows():
        md.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    lines = ["# Results", "", "\n".join(md), "",
             "`leak_pct` = how much of the honest error disappears when you score on",
             "revised data. Positive means the naive backtest flatters itself.", "",
             "## Worst single origins", ""]
    for sid, r in results.items():
        m = r["merged"].assign(d=lambda d: d.ape_v - d.ape_r).nlargest(1, "d")
        if len(m):
            row = m.iloc[0]
            lines.append(
                f"- **{sid}** origin {row.origin[:7]}: the same forecast scores "
                f"{row.ape_v:.2f}% against vintage data and {row.ape_r:.2f}% against "
                f"revised data ({row.ape_v - row.ape_r:+.2f} pp)."
            )
    lines += ["", "## Most-revised individual periods", ""]
    for sid in results:
        for p, n, lo, hi, pct in store.most_revised(sid, 2):
            lines.append(f"- `{sid}` {p[:7]}: {n} vintages, {lo:,.1f} to {hi:,.1f} ({pct:+.1f}%)")
    (OUT / "results.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
