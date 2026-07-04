"""PII masking applied at the MCP server boundary (specs/30-security.md §6, SEC-4).

The synthetic fixtures already contain ``[[PLACEHOLDER]]`` tokens, so masking is
idempotent for the demo. It exists because this server is designed to be pointed
at a real health store later: identity fields are masked structurally, and free
text is scrubbed with pattern rules, before anything crosses the process
boundary into an LLM context. The regex layer is deliberately a *prefilter* —
regex alone cannot catch all PII, which is why the agent side adds a semantic
gate on outbound responses.
"""

import re

# Structural masking: identity field name -> replacement token, declared PER
# DATA SURFACE. Field names collide across surfaces ("name" is a person on the
# profile but a drug on a medication row), so each tool passes the map that
# applies to the rows it returns; there is no blanket default.
PROFILE_TOKENS: dict[str, str] = {
    "name": "[[PATIENT_NAME]]",
    "national_id": "[[PATIENT_ID]]",
}
MEDICATION_TOKENS: dict[str, str] = {
    "prescriber": "[[DOCTOR_NAME]]",
}
REPORT_TOKENS: dict[str, str] = {}  # report/metric rows carry no identity fields

# Pattern scrubbing for free text (TW-flavored, matching the origin system).
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[A-Z][12]\d{8}\b"), "[[REDACTED_ID]]"),          # TW national ID
    (re.compile(r"(?<!\d)(?:\+886[\s-]?9\d{8}|09\d{8})(?!\d)"), "[[REDACTED_PHONE]]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[[REDACTED_EMAIL]]"),
]


def scrub_text(text: str) -> str:
    """Replace PII-shaped substrings in free text with redaction tokens."""
    for pattern, token in _PATTERNS:
        text = pattern.sub(token, text)
    return text


def find_pii(text: str) -> str | None:
    """Return the redaction token of the first PII pattern found, else None.

    Detection-only variant of scrub_text, used as the deterministic Stage-1
    prefilter of the semantic gate (specs/30-security.md §5).
    """
    for pattern, token in _PATTERNS:
        if pattern.search(text):
            return token
    return None


def mask_record(record: dict, tokens: dict[str, str]) -> dict:
    """Mask identity fields and scrub every string value in a flat record.

    Args:
        record: A row/document about to leave the server boundary.
        tokens: The field->token map for this record's data surface
            (PROFILE_TOKENS / MEDICATION_TOKENS / REPORT_TOKENS).

    Returns:
        A new dict; identity fields replaced by tokens (None values preserved),
        all other string values pattern-scrubbed.
    """
    masked: dict = {}
    for key, value in record.items():
        if key in tokens:
            masked[key] = tokens[key] if value is not None else None
        elif isinstance(value, str):
            masked[key] = scrub_text(value)
        else:
            masked[key] = value
    return masked
