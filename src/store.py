"""Bitemporal fact store.

One rule: nothing is ever updated in place. A revision to an already-published
figure arrives as a new row with a later `as_of`, so the store can always answer
"what did we believe on date X?" instead of only "what do we believe now?".
"""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    series_id TEXT NOT NULL,
    period    TEXT NOT NULL,   -- the month the number describes
    as_of     TEXT NOT NULL,   -- the date that number was published
    value     REAL,
    PRIMARY KEY (series_id, period, as_of)
);
CREATE INDEX IF NOT EXISTS facts_lookup ON facts (series_id, period, as_of);
"""


class Store:
    def __init__(self, path="data/facts.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def append(self, rows):
        """rows: (series_id, period, as_of, value). Existing keys are left alone."""
        cur = self.db.executemany(
            "INSERT OR IGNORE INTO facts VALUES (?,?,?,?)", rows
        )
        self.db.commit()
        return cur.rowcount

    def as_known_on(self, series_id, on_date):
        """The whole series as it stood on `on_date`: latest as_of <= on_date per period."""
        # bare column alongside MAX() is SQLite's documented "row that holds the max"
        # idiom, and it is far faster here than a correlated subquery per period.
        rows = self.db.execute(
            """SELECT period, value, MAX(as_of) FROM facts
               WHERE series_id = ? AND as_of <= ?
               GROUP BY period ORDER BY period""",
            (series_id, on_date),
        ).fetchall()
        return {p: v for p, v, _ in rows if v is not None}

    def revisions(self, series_id, period):
        return self.db.execute(
            "SELECT as_of, value FROM facts WHERE series_id=? AND period=? ORDER BY as_of",
            (series_id, period),
        ).fetchall()

    def vintage_count(self, series_id):
        return self.db.execute(
            "SELECT COUNT(DISTINCT as_of) FROM facts WHERE series_id=?", (series_id,)
        ).fetchone()[0]

    def most_revised(self, series_id, limit=5):
        """Periods whose published value moved the most, first release to latest."""
        return self.db.execute(
            """SELECT period, COUNT(*) AS n, MIN(value) AS lo, MAX(value) AS hi,
                      ROUND(100.0 * (MAX(value) - MIN(value)) / MIN(value), 2) AS pct_spread
               FROM facts WHERE series_id = ? AND value IS NOT NULL
               GROUP BY period HAVING n > 1
               ORDER BY pct_spread DESC LIMIT ?""",
            (series_id, limit),
        ).fetchall()
