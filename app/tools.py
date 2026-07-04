"""Local write tools — the only mutation paths in the system.

Deliberately NOT exposed over MCP (specs/20-architecture.md §1): every write is
wrapped in FunctionTool(require_confirmation=True) in agent.py, so execution
pauses for explicit human approval (MED-4, TRI-1). The structural policy gate
additionally checks the session role before these ever run (SEC-1).
"""

import datetime

from mcp_server import store
from mcp_server.masking import scrub_text


def add_medication(name: str, dose: str, frequency: str, reason: str) -> dict:
    """Add a new medication to the patient's record.

    Args:
        name: Medication name, lowercase (e.g. 'allopurinol').
        dose: Dose per intake (e.g. '100mg').
        frequency: One of 'once_daily_morning', 'once_daily_evening',
            'twice_daily', 'as_needed'.
        reason: Why it was prescribed, as stated by the user.

    Returns:
        dict with 'status' and the stored record.
    """
    today = datetime.date.today().isoformat()
    with store.connect() as conn:
        store.add_medication(conn, name, dose, frequency, today, scrub_text(reason))
    return {
        "status": "success",
        "medication": {"name": name, "dose": dose, "frequency": frequency,
                       "start_date": today},
    }


def log_symptom(description: str, severity: str, suspected_trigger: str) -> dict:
    """Record a symptom event in the health log.

    Args:
        description: What the patient is experiencing, in plain words.
        severity: One of 'mild', 'moderate', 'red_flag'.
        suspected_trigger: Suspected cause if mentioned (food, medication,
            activity), or 'unknown'.

    Returns:
        dict with 'status' and the stored record.
    """
    today = datetime.date.today().isoformat()
    with store.connect() as conn:
        store.log_symptom(
            conn, today, scrub_text(description), severity, scrub_text(suspected_trigger)
        )
    return {
        "status": "success",
        "symptom": {"date": today, "description": scrub_text(description),
                    "severity": severity},
    }
