"""ZIP is not ZCTA, and neither is a county. Measure what a naive join loses.

Zillow publishes home values keyed by USPS ZIP. The Census publishes demographics
keyed by ZCTA. They look like the same thing and are not: ZCTAs are Census polygons
approximating ZIP delivery areas, and the two sets do not line up. Counties are a
third geography again, and ZCTAs straddle county lines freely.

The failure mode this measures is the quiet one. Join on the key and most rows match.
The ones that do not simply vanish, the result still looks like a complete table, and
nobody notices until a number is wrong in a way somebody happens to catch.
"""
import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

# Census 2020 ZCTA-to-county relationship file: one row per ZCTA x county overlap.
ZCTA_COUNTY = ("https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/"
               "tab20_zcta520_county20_natl.txt")


def load_crosswalk(cache="data/zcta_county.txt"):
    p = Path(cache)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(requests.get(ZCTA_COUNTY, timeout=120).content)
    df = pd.read_csv(p, sep="|", dtype=str, encoding="utf-8-sig")
    df = df[df["GEOID_ZCTA5_20"].notna()].copy()
    # land area of the ZCTA piece that falls inside this county
    df["overlap_land"] = pd.to_numeric(df["AREALAND_PART"], errors="coerce").fillna(0)
    return df.rename(columns={"GEOID_ZCTA5_20": "zcta", "GEOID_COUNTY_20": "county_fips",
                              "NAMELSAD_COUNTY_20": "county_name"})[
        ["zcta", "county_fips", "county_name", "overlap_land"]]


def analyse(zillow_csv, cache="data/zcta_county.txt"):
    xw = load_crosswalk(cache)
    z = pd.read_csv(zillow_csv, low_memory=False,
                    usecols=["RegionName", "State", "CountyName", "Metro"])
    z["zip"] = z["RegionName"].astype(int).astype(str).str.zfill(5)

    zcta_set = set(xw["zcta"])
    z["in_zcta"] = z["zip"].isin(zcta_set)

    # how many ZCTAs straddle a county line?
    per_zcta = xw.groupby("zcta").size()
    multi = per_zcta[per_zcta > 1]

    # naive join: ZIP == ZCTA, take whichever county row comes first
    naive = z.merge(xw.drop_duplicates("zcta"), left_on="zip", right_on="zcta", how="inner")

    # weighted: allocate each ZIP across every county it actually touches, by land area
    weighted = z.merge(xw, left_on="zip", right_on="zcta", how="inner")
    weighted["share"] = weighted["overlap_land"] / weighted.groupby("zip")["overlap_land"].transform("sum")

    # where the naive pick disagrees with the largest-overlap county
    biggest = (weighted.sort_values("overlap_land", ascending=False)
                       .drop_duplicates("zip")[["zip", "county_name", "share"]]
                       .rename(columns={"county_name": "true_county", "share": "true_share"}))
    check = naive[["zip", "county_name"]].merge(biggest, on="zip")
    wrong = check[check["county_name"] != check["true_county"]]

    worst = (weighted[weighted["zip"].isin(multi.index)]
             .sort_values("share").groupby("zip").filter(lambda g: len(g) > 2)
             .groupby(["zip"]).size().sort_values(ascending=False).head(3))

    return {
        "zillow_zips": len(z),
        "zctas": int(per_zcta.size),
        "zips_with_no_zcta": int((~z["in_zcta"]).sum()),
        "pct_dropped": round((~z["in_zcta"]).sum() / len(z) * 100, 2),
        "zctas_spanning_counties": int(len(multi)),
        "pct_zctas_multi_county": round(len(multi) / per_zcta.size * 100, 2),
        "max_counties_one_zcta": int(per_zcta.max()),
        "naive_rows": len(naive),
        "weighted_rows": len(weighted),
        "naive_county_wrong": int(len(wrong)),
        "examples_many_county": {k: int(v) for k, v in worst.items()},
    }
