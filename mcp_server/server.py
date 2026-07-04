"""Health-data MCP server (read-only, PII-masked at the boundary).

Exposes the synthetic health store as MCP tools over stdio
(specs/20-architecture.md §4). Every response passes masking before leaving
the process: the LLM context on the client side never contains raw identity
values, regardless of how the agent behaves (SEC-4).

Writes are deliberately NOT exposed here — they live in the agent's local
FunctionTools behind human confirmation (specs/30-security.md §7).

Run: ``uv run python -m mcp_server.server`` (DB path via ``HEALTH_DB_PATH``).
"""

from mcp.server.fastmcp import FastMCP

from mcp_server import store
from mcp_server.masking import MEDICATION_TOKENS, REPORT_TOKENS, mask_record

mcp = FastMCP("health-data-mcp")


def _masked(rows: list[dict], tokens: dict[str, str]) -> list[dict]:
    return [mask_record(row, tokens) for row in rows]


@mcp.tool()
def list_medications() -> list[dict]:
    """List all medications on record (active and stopped), with dose,
    frequency, start date, masked prescriber, and status."""
    with store.connect() as conn:
        return _masked(store.list_medications(conn), MEDICATION_TOKENS)


@mcp.tool()
def get_medication_schedule(time_of_day: str) -> list[dict]:
    """List active medications due at a time of day.

    Args:
        time_of_day: One of 'morning', 'evening', or 'any' (all active).
    """
    with store.connect() as conn:
        return _masked(store.get_medication_schedule(conn, time_of_day), MEDICATION_TOKENS)


@mcp.tool()
def list_reports() -> list[dict]:
    """List all checkup reports (newest first) with report_id, date, provider,
    and the count of metrics flagged outside their reference range."""
    with store.connect() as conn:
        return _masked(store.list_reports(conn), REPORT_TOKENS)


@mcp.tool()
def get_report_details(report_id: str) -> list[dict]:
    """Get the full metric list for one checkup report: metric name, value,
    unit, reference range, and normal/high/low flag.

    Args:
        report_id: The report identifier from list_reports.
    """
    with store.connect() as conn:
        return _masked(store.get_report_details(conn, report_id), REPORT_TOKENS)


@mcp.tool()
def get_metric_history(metric: str) -> list[dict]:
    """Get the value of one health metric across all reports, oldest first —
    use this for trend questions. Returns an empty list if the metric was
    never measured.

    Args:
        metric: Metric key, lowercase snake_case (e.g. 'uric_acid', 'alt').
    """
    with store.connect() as conn:
        return _masked(store.get_metric_history(conn, metric), REPORT_TOKENS)


if __name__ == "__main__":
    mcp.run()
