"""Store logic + seed pipeline against the committed synthetic fixtures."""

import pytest

from mcp_server import store
from mcp_server.seed import seed


@pytest.fixture()
def conn(tmp_path):
    db = str(tmp_path / "health.db")
    seed(db)
    connection = store.connect(db)
    yield connection
    connection.close()


class TestSeedAndReads:
    def test_seed_loads_all_fixtures(self, conn):
        assert len(store.list_medications(conn)) == 4
        assert len(store.list_reports(conn)) == 3

    def test_reports_newest_first_with_abnormal_count(self, conn):
        reports = store.list_reports(conn)
        assert [r["report_id"] for r in reports] == [
            "2026-06-clinic-a", "2025-06-clinic-b", "2024-06-clinic-a",
        ]
        assert reports[0]["abnormal_count"] == 2  # uric_acid + alt
        assert reports[2]["abnormal_count"] == 0

    def test_metric_history_oldest_first_shows_trend(self, conn):
        history = store.get_metric_history(conn, "uric_acid")
        assert [h["value"] for h in history] == [6.8, 7.4, 7.9]
        assert [h["flag"] for h in history] == ["normal", "high", "high"]

    def test_unknown_metric_returns_empty_not_fabricated(self, conn):
        assert store.get_metric_history(conn, "hba1c") == []  # CHK-3

    def test_report_details(self, conn):
        details = store.get_report_details(conn, "2026-06-clinic-a")
        assert len(details) == 10
        flagged = {d["metric"] for d in details if d["flag"] != "normal"}
        assert flagged == {"uric_acid", "alt"}


class TestSchedule:
    def test_morning(self, conn):
        names = {m["name"] for m in store.get_medication_schedule(conn, "morning")}
        assert names == {"omeprazole", "fish_oil"}

    def test_evening(self, conn):
        names = {m["name"] for m in store.get_medication_schedule(conn, "evening")}
        assert names == {"allopurinol"}  # MED-2

    def test_any_returns_active_only(self, conn):
        meds = store.get_medication_schedule(conn, "any")
        assert len(meds) == 3
        assert all(m["status"] == "active" for m in meds)


class TestWrites:
    def test_add_medication(self, conn):
        store.add_medication(conn, "ibuprofen", "200mg", "as_needed", "2026-07-04", "test")
        names = {m["name"] for m in store.list_medications(conn)}
        assert "ibuprofen" in names

    def test_log_symptom(self, conn):
        rowid = store.log_symptom(conn, "2026-07-04", "mild heartburn", "mild", "dinner")
        assert rowid > 0

    def test_reseed_is_idempotent(self, conn, tmp_path):
        db = str(tmp_path / "health.db")
        store.add_medication(conn, "x", "1mg", "as_needed", "2026-07-04", None)
        seed(db)
        fresh = store.connect(db)
        assert len(store.list_medications(fresh)) == 4
        fresh.close()
