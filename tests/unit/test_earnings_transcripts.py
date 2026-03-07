from app.services.earnings_transcripts import (
    fiscal_quarter_code,
    _chunk_text_blocks,
    _extract_speaker,
    _split_into_blocks,
    fetch_alpha_vantage_transcript,
    TranscriptProviderError,
)
from app.services import earnings_transcripts as et
from requests import RequestException


def test_fiscal_quarter_code_formats_expected_value():
    assert fiscal_quarter_code(2025, 3) == "2025Q3"


def test_extract_speaker_parses_colon_prefix():
    speaker, text = _extract_speaker("Jane Doe: Revenue grew 20% year-over-year.")
    assert speaker == "Jane Doe"
    assert text == "Revenue grew 20% year-over-year."


def test_extract_speaker_keeps_plain_block_without_prefix():
    speaker, text = _extract_speaker("We saw stronger demand in enterprise.")
    assert speaker is None
    assert text == "We saw stronger demand in enterprise."


def test_split_into_blocks_normalizes_blank_lines():
    blocks = _split_into_blocks("A\n\n\nB\r\n\r\nC")
    assert blocks == ["A", "B", "C"]


def test_chunk_text_blocks_preserves_order_and_indices():
    blocks = [
        "Operator: Welcome everyone to the call.",
        "Prepared Remarks\nRevenue increased and margins expanded.",
        "Question-and-Answer Session\nQ: What changed in pricing?",
    ]
    segments = _chunk_text_blocks(blocks, per_segment_limit=120, total_char_limit=2000)
    assert len(segments) >= 2
    assert [s.segment_index for s in segments] == list(range(len(segments)))
    assert "Welcome everyone" in segments[0].text


def test_chunk_text_blocks_respects_total_char_limit():
    blocks = ["A" * 1000, "B" * 1000]
    segments = _chunk_text_blocks(blocks, per_segment_limit=400, total_char_limit=900)
    total = sum(len(s.text) for s in segments)
    assert total <= 900


def test_provider_error_does_not_echo_sensitive_query(monkeypatch):
    monkeypatch.setattr(et.settings, "alpha_vantage_api_key", "super_secret_key")

    def fake_get(*_args, **_kwargs):
        raise RequestException("GET https://example?apikey=super_secret_key failed")

    monkeypatch.setattr(et.requests, "get", fake_get)

    try:
        fetch_alpha_vantage_transcript("NVDA", 2026, 1)
        assert False, "expected TranscriptProviderError"
    except TranscriptProviderError as exc:
        msg = str(exc)
        assert msg == "provider_request_failed"
        assert "super_secret_key" not in msg
        assert "apikey=" not in msg
