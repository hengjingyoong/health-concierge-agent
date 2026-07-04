"""Seed the SQLite store from data/synthetic/ YAML fixtures.

Usage: ``uv run python -m mcp_server.seed`` (target overridable via
``HEALTH_DB_PATH``). Reseeding is destructive-by-design for demo repeatability:
existing rows are wiped so every run starts from the committed fixtures.
"""

from pathlib import Path

import yaml

from mcp_server import store

FIXTURES_DIR = Path("data/synthetic")


def seed(db: str | None = None, fixtures_dir: Path = FIXTURES_DIR) -> str:
    conn = store.connect(db)
    with conn:
        conn.execute("DELETE FROM metrics")
        conn.execute("DELETE FROM reports")
        conn.execute("DELETE FROM medications")
        conn.execute("DELETE FROM symptoms")
        conn.execute("DELETE FROM profile")

        profile = yaml.safe_load((fixtures_dir / "profile.yaml").read_text())["profile"]
        for key, value in profile.items():
            conn.execute(
                "INSERT INTO profile (key, value) VALUES (?, ?)",
                (key, yaml.safe_dump(value).strip() if isinstance(value, list) else str(value)),
            )

        meds = yaml.safe_load((fixtures_dir / "medications.yaml").read_text())["medications"]
        for m in meds:
            conn.execute(
                "INSERT INTO medications (name, dose, frequency, start_date, prescriber, status)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (m["name"], m["dose"], m["frequency"], str(m["start_date"]),
                 m["prescriber"], m["status"]),
            )

        for report_file in sorted((fixtures_dir / "reports").glob("*.yaml")):
            report = yaml.safe_load(report_file.read_text())["report"]
            conn.execute(
                "INSERT INTO reports (report_id, date, provider) VALUES (?, ?, ?)",
                (report["report_id"], str(report["date"]), report["provider"]),
            )
            for metric, m in report["metrics"].items():
                conn.execute(
                    "INSERT INTO metrics (report_id, metric, value, unit, ref, flag)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (report["report_id"], metric, m["value"], m["unit"],
                     m["ref"], m["flag"]),
                )
    path = db or store.db_path()
    conn.close()
    return path


if __name__ == "__main__":
    print(f"Seeded {seed()}")
