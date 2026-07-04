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

# Structural masking: identity field name -> replacement token.
IDENTITY_FIELD_TOKENS: dict[str, str] = {
    "name": "[[PATIENT_NAME]]",
    "national_id": "[[PATIENT_ID]]",
    "prescriber": "[[DOCTOR_NAME]]",
}

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


def mask_record(record: dict, extra_fields: dict[str, str] | None = None) -> dict:
    """Mask identity fields and scrub every string value in a flat record.

    Args:
        record: A row/document about to leave the server boundary.
        extra_fields: Optional additional field->token overrides.

    Returns:
        A new dict; identity fields replaced by tokens (None values preserved),
        all other string values pattern-scrubbed.
    """
    tokens = {**IDENTITY_FIELD_TOKENS, **(extra_fields or {})}
    masked: dict = {}
    for key, value in record.items():
        if key in tokens:
            masked[key] = tokens[key] if value is not None else None
        elif isinstance(value, str):
            masked[key] = scrub_text(value)
        else:
            masked[key] = value
    return masked
