"""SQLite access layer for the synthetic health store.

Pure data logic — no masking here (that happens at the server boundary) and no
LLM anywhere. Reads are consumed by the MCP server; writes are consumed by the
agent's guarded local tools (HITL-confirmed, specs/20-architecture.md §4).

The DB path comes from ``HEALTH_DB_PATH`` (default ``data/health.db``).
"""

import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = "data/health.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS medications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    dose       TEXT NOT NULL,
    frequency  TEXT NOT NULL,
    start_date TEXT NOT NULL,
    prescriber TEXT,
    status     TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    date      TEXT NOT NULL,
    provider  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics (
    report_id TEXT NOT NULL REFERENCES reports(report_id),
    metric    TEXT NOT NULL,
    value     REAL NOT NULL,
    unit      TEXT NOT NULL,
    ref       TEXT NOT NULL,
    flag      TEXT NOT NULL,
    PRIMARY KEY (report_id, metric)
);
CREATE TABLE IF NOT EXISTS symptoms (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    date              TEXT NOT NULL,
    description       TEXT NOT NULL,
    severity          TEXT NOT NULL,
    suspected_trigger TEXT
);
"""


def db_path() -> str:
    return os.environ.get("HEALTH_DB_PATH", DEFAULT_DB_PATH)


def connect(path: str | None = None) -> sqlite3.Connection:
    """Open (and initialize) the store. Caller owns the connection."""
    resolved = path or db_path()
    Path(resolved).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(resolved)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _rows(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, args).fetchall()]


# --- reads (MCP surface) -----------------------------------------------------

def list_medications(conn: sqlite3.Connection) -> list[dict]:
    return _rows(
        conn,
        "SELECT name, dose, frequency, start_date, prescriber, status"
        " FROM medications ORDER BY status, name",
    )


def get_medication_schedule(conn: sqlite3.Connection, time_of_day: str) -> list[dict]:
    """Active medications due at a time of day.

    Frequency vocabulary: ``once_daily_morning`` / ``once_daily_evening`` /
    ``twice_daily`` (morning + evening) / ``as_needed`` (matches only 'any').
    ``time_of_day='any'`` returns every active medication.
    """
    meds = _rows(
        conn,
        "SELECT name, dose, frequency, start_date, prescriber, status"
        " FROM medications WHERE status = 'active' ORDER BY name",
    )
    if time_of_day == "any":
        return meds
    return [
        m for m in meds
        if time_of_day in m["frequency"] or m["frequency"] == "twice_daily"
    ]


def list_reports(conn: sqlite3.Connection) -> list[dict]:
    return _rows(
        conn,
        "SELECT r.report_id, r.date, r.provider,"
        " SUM(CASE WHEN m.flag != 'normal' THEN 1 ELSE 0 END) AS abnormal_count"
        " FROM reports r JOIN metrics m ON m.report_id = r.report_id"
        " GROUP BY r.report_id ORDER BY r.date DESC",
    )


def get_report_details(conn: sqlite3.Connection, report_id: str) -> list[dict]:
    return _rows(
        conn,
        "SELECT metric, value, unit, ref, flag FROM metrics"
        " WHERE report_id = ? ORDER BY metric",
        (report_id,),
    )


def get_metric_history(conn: sqlite3.Connection, metric: str) -> list[dict]:
    return _rows(
        conn,
        "SELECT r.date, m.value, m.unit, m.ref, m.flag"
        " FROM metrics m JOIN reports r ON r.report_id = m.report_id"
        " WHERE m.metric = ? ORDER BY r.date",
        (metric,),
    )


def get_profile(conn: sqlite3.Connection) -> dict:
    return {row["key"]: row["value"] for row in conn.execute("SELECT * FROM profile")}


# --- writes (guarded local tools only — never on the MCP surface) ------------

def add_medication(
    conn: sqlite3.Connection,
    name: str,
    dose: str,
    frequency: str,
    start_date: str,
    reason: str | None,
) -> int:
    cur = conn.execute(
        "INSERT INTO medications (name, dose, frequency, start_date, prescriber, status)"
        " VALUES (?, ?, ?, ?, ?, 'active')",
        (name, dose, frequency, start_date, reason),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def log_symptom(
    conn: sqlite3.Connection,
    date: str,
    description: str,
    severity: str,
    suspected_trigger: str | None,
) -> int:
    cur = conn.execute(
        "INSERT INTO symptoms (date, description, severity, suspected_trigger)"
        " VALUES (?, ?, ?, ?)",
        (date, description, severity, suspected_trigger),
    )
    conn.commit()
    return int(cur.lastrowid or 0)
