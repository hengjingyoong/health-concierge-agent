"""Boundary masking is the structural guarantee behind SEC-4 — test it hard."""

from mcp_server.masking import mask_record, scrub_text


class TestScrubText:
    def test_tw_national_id(self):
        assert scrub_text("id is A123456789 ok") == "id is [[REDACTED_ID]] ok"

    def test_phone_local_and_intl(self):
        assert scrub_text("call 0912345678") == "call [[REDACTED_PHONE]]"
        assert scrub_text("call +886912345678") == "call [[REDACTED_PHONE]]"

    def test_email(self):
        assert scrub_text("mail x.y+z@example.com now") == "mail [[REDACTED_EMAIL]] now"

    def test_clean_text_untouched(self):
        text = "uric acid 7.9 mg/dL on 2026-06-15"
        assert scrub_text(text) == text

    def test_multiple_hits_in_one_string(self):
        out = scrub_text("A123456789 / 0912345678 / a@b.tw")
        assert "[[REDACTED_ID]]" in out
        assert "[[REDACTED_PHONE]]" in out
        assert "[[REDACTED_EMAIL]]" in out


class TestMaskRecord:
    def test_identity_fields_replaced_even_with_real_values(self):
        # Simulates being pointed at a REAL store: raw values must not survive.
        record = {"name": "王小明", "national_id": "A123456789", "dose": "100mg"}
        masked = mask_record(record)
        assert masked["name"] == "[[PATIENT_NAME]]"
        assert masked["national_id"] == "[[PATIENT_ID]]"
        assert masked["dose"] == "100mg"

    def test_prescriber_masked_but_none_preserved(self):
        assert mask_record({"prescriber": "Dr. Real Name"})["prescriber"] == "[[DOCTOR_NAME]]"
        assert mask_record({"prescriber": None})["prescriber"] is None

    def test_free_text_fields_are_scrubbed(self):
        record = {"description": "headache, contact 0912345678"}
        assert mask_record(record)["description"] == "headache, contact [[REDACTED_PHONE]]"

    def test_idempotent_on_placeholder_fixtures(self):
        record = {"name": "[[PATIENT_NAME]]", "prescriber": "[[DOCTOR_NAME]]"}
        assert mask_record(mask_record(record)) == mask_record(record)

    def test_non_string_values_pass_through(self):
        record = {"value": 7.9, "flag": "high"}
        assert mask_record(record) == {"value": 7.9, "flag": "high"}
