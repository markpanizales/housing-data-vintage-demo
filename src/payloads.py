"""Precompute one map payload per (metric, period) and measure what it costs.

The argument: a national ZIP-level choropleth is not a database query. It is one
array of numbers in a fixed, agreed order. Ship the geo-id index once and cache it
forever; ship the values as a bare typed array behind a CDN.

Two things worth measuring rather than assuming:

  1. float32 barely compresses. Mantissa bits look like noise to gzip, so you get
     ~10% off and nothing more.
  2. Quantising to the precision the UI actually renders costs nothing visible and
     roughly halves the payload again. A home-value map coloured in bands does not
     need sub-dollar resolution.
"""
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

ZHVI_ZIP = ("https://files.zillowstatic.com/research/public_csvs/zhvi/"
            "Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv")
META = ["RegionID", "SizeRank", "RegionName", "RegionType",
        "StateName", "State", "City", "Metro", "CountyName"]


def load(path):
    df = pd.read_csv(path, low_memory=False)
    periods = [c for c in df.columns if c not in META]
    df = df.sort_values("RegionID").reset_index(drop=True)
    return df, periods


def write_index(df, outdir):
    """The geo-id order every payload is keyed to. Fetched once, cached forever."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    index = {
        "geo_level": "zip",
        "count": int(len(df)),
        "ids": [f"{z:05d}" for z in df["RegionName"].astype(int)],
    }
    body = gzip.compress(json.dumps(index, separators=(",", ":")).encode(), 9)
    (outdir / "index.json.gz").write_bytes(body)
    return len(body)


def write_payload(df, period, outdir, quantise=True, scale=1000):
    """One (metric, period) payload as a bare typed array, gzipped."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    vals = df[period].to_numpy(dtype=np.float32)
    if quantise:
        arr = np.nan_to_num(vals / scale, nan=0).round().astype(np.uint16)
        dtype, sentinel = "uint16", 0
    else:
        arr = vals
        dtype, sentinel = "float32", "NaN"
    raw = arr.tobytes()
    body = gzip.compress(raw, 9)
    name = f"zhvi_{period[:7]}.{dtype}.gz"
    (outdir / name).write_bytes(body)
    return {
        "file": name, "period": period[:7], "dtype": dtype, "n": len(arr),
        "raw_kb": len(raw) / 1024, "gz_kb": len(body) / 1024,
        "scale": scale if quantise else 1, "missing_sentinel": sentinel,
    }


def build(path, outdir, months=24):
    """Latest `months` periods, both encodings, with a measured manifest."""
    df, periods = load(path)
    idx_bytes = write_index(df, outdir)
    rows = []
    for p in periods[-months:]:
        rows.append(write_payload(df, p, outdir, quantise=True))
    sample = write_payload(df, periods[-1], Path(outdir) / "_float32_for_comparison",
                           quantise=False)
    manifest = {
        "source": "Zillow ZHVI (all homes, smoothed, seasonally adjusted), ZIP level",
        "source_url": ZHVI_ZIP,
        "geo_count": int(len(df)),
        "period_range": [periods[0][:7], periods[-1][:7]],
        "index_gz_bytes": idx_bytes,
        "payloads": rows,
        "float32_comparison": sample,
    }
    Path(outdir, "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
