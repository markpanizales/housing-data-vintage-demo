# Results

| series | name | window | n | mape_vintage | mape_revised | gap_pp | leak_pct |
|---|---|---|---|---|---|---|---|
| CSUSHPINSA | Case-Shiller national home price index | 2015-02 to 2024-06 | 113 | 5.671 | 5.649 | 0.022 | 0.4 |
| HOUST | Housing starts | 2005-04 to 2024-06 | 230 | 21.591 | 22.115 | -0.525 | -2.4 |
| HSN1F | New one-family houses sold | 2005-04 to 2024-06 | 229 | 25.596 | 23.955 | 1.641 | 6.4 |
| PERMIT | Building permits | 2005-04 to 2024-06 | 231 | 19.44 | 19.295 | 0.146 | 0.7 |

`leak_pct` = how much of the honest error disappears when you score on
revised data. Positive means the naive backtest flatters itself.

## Worst single origins

- **CSUSHPINSA** origin 2021-07: the same forecast scores 3.97% against vintage data and 3.08% against revised data (+0.89 pp).
- **HOUST** origin 2021-06: the same forecast scores 78.83% against vintage data and 64.48% against revised data (+14.35 pp).
- **HSN1F** origin 2021-05: the same forecast scores 188.94% against vintage data and 91.04% against revised data (+97.91 pp).
- **PERMIT** origin 2018-03: the same forecast scores 14.33% against vintage data and 2.97% against revised data (+11.36 pp).

## Most-revised individual periods

- `CSUSHPINSA` 2016-12: 116 vintages, 184.4 to 185.5 (+0.6%)
- `CSUSHPINSA` 2016-10: 118 vintages, 184.0 to 185.1 (+0.6%)
- `HOUST` 1960-01: 791 vintages, 1,366.0 to 1,684.0 (+23.3%)
- `HOUST` 1961-01: 784 vintages, 1,076.0 to 1,319.0 (+22.6%)
- `HSN1F` 2010-04: 193 vintages, 414.0 to 504.0 (+21.7%)
- `HSN1F` 2020-06: 72 vintages, 776.0 to 936.0 (+20.6%)
- `PERMIT` 2023-02: 78 vintages, 1,482.0 to 1,620.0 (+9.3%)
- `PERMIT` 2014-03: 280 vintages, 990.0 to 1,078.0 (+8.9%)
