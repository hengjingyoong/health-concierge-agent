"""MCP stdio round-trip: spawn the real server, list tools, call them.

No LLM involved — this is the Day-5 'minimal MCP client' pattern as a test.
Verifies the wire contract the ADK agent will consume in Phase 2, including
that masking has already happened by the time data crosses the boundary.
"""

import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_server.seed import seed

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_TOOLS = {
    "list_medications",
    "get_medication_schedule",
    "list_reports",
    "get_report_details",
    "get_metric_history",
}


def _payload(result) -> list[dict]:
    """Normalize a CallToolResult into a list of dicts."""
    if result.structuredContent is not None:
        data = result.structuredContent
        if isinstance(data, dict) and "result" in data:
            data = data["result"]
        return data if isinstance(data, list) else [data]
    return [json.loads(block.text) for block in result.content if block.type == "text"]


@pytest.fixture()
def server_params(tmp_path):
    db = str(tmp_path / "health.db")
    seed(db, fixtures_dir=REPO_ROOT / "data" / "synthetic")
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        env={**os.environ, "HEALTH_DB_PATH": db},
        cwd=str(REPO_ROOT),
    )


@pytest.mark.asyncio
async def test_full_roundtrip(server_params):
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Contract: exactly the 5 read tools, nothing writable (SEC surface).
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == EXPECTED_TOOLS

            meds = _payload(await session.call_tool("list_medications", {}))
            assert len(meds) == 4
            # SEC-4: prescriber already masked when it crosses the boundary.
            prescribers = {m["prescriber"] for m in meds}
            assert prescribers <= {"[[DOCTOR_NAME]]", None}

            history = _payload(
                await session.call_tool("get_metric_history", {"metric": "uric_acid"})
            )
            assert [h["value"] for h in history] == [6.8, 7.4, 7.9]

            missing = _payload(
                await session.call_tool("get_metric_history", {"metric": "hba1c"})
            )
            assert missing == []
