from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import requests

from app.core.config import settings

ALPHA_VANTAGE_TRANSCRIPT_URL = "https://www.alphavantage.co/query"


class TranscriptProviderError(RuntimeError):
    pass


@dataclass
class TranscriptSegmentDraft:
    segment_index: int
    text: str
    speaker: str | None = None
    section: str | None = None
    token_count: int = 0


@dataclass
class TranscriptDraft:
    ticker: str
    fiscal_year: int
    fiscal_quarter: int
    source_provider: str
    source_url: str | None
    source_doc_id: str | None
    call_date: date | None
    language: str
    storage_mode: str
    content_hash: str
    segments: list[TranscriptSegmentDraft]


def fiscal_quarter_code(fiscal_year: int, fiscal_quarter: int) -> str:
    return f"{int(fiscal_year)}Q{int(fiscal_quarter)}"


def _parse_call_date(value: Any) -> date | None:
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y%m%dT%H%M"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # Common API shape: 20250130T213000
    if len(s) >= 8 and s[:8].isdigit():
        try:
            return datetime.strptime(s[:8], "%Y%m%d").date()
        except ValueError:
            return None
    return None


def _extract_payload_node(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, list):
        return payload[0] if payload else {}
    if isinstance(payload, dict):
        # Most common AV shape is a list under "transcript", but support alternates.
        for key in ("transcript", "data", "result", "results"):
            val = payload.get(key)
            if isinstance(val, list) and val:
                first = val[0]
                if isinstance(first, dict):
                    return first
        return payload
    return {}


def _extract_text(node: dict[str, Any]) -> str:
    for key in ("transcript", "content", "text", "body"):
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _classify_section(lower_text: str) -> str | None:
    if "question-and-answer" in lower_text or "q&a" in lower_text or "question and answer" in lower_text:
        return "q_and_a"
    if "prepared remarks" in lower_text:
        return "prepared_remarks"
    return None


def _extract_speaker(block: str) -> tuple[str | None, str]:
    # Basic speaker format matcher: "Name: text"
    m = re.match(r"^\s*([A-Za-z][A-Za-z .'\-]{1,80}):\s+(.*)$", block, flags=re.DOTALL)
    if not m:
        return None, block
    speaker = m.group(1).strip()
    text = m.group(2).strip()
    return speaker, text


def _split_into_blocks(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    parts = [p.strip() for p in re.split(r"\n\s*\n+", normalized) if p.strip()]
    return parts


def _chunk_text_blocks(blocks: list[str], per_segment_limit: int, total_char_limit: int) -> list[TranscriptSegmentDraft]:
    segments: list[TranscriptSegmentDraft] = []
    current = ""
    section: str | None = None
    consumed = 0

    def flush_segment() -> None:
        nonlocal current, section
        if not current.strip():
            current = ""
            return
        speaker, body = _extract_speaker(current.strip())
        seg_text = body if speaker else current.strip()
        segments.append(
            TranscriptSegmentDraft(
                segment_index=len(segments),
                speaker=speaker,
                section=section,
                text=seg_text,
                token_count=max(1, int(len(seg_text.split()))),
            )
        )
        current = ""

    for block in blocks:
        if consumed >= total_char_limit:
            break
        block = block[: max(0, total_char_limit - consumed)].strip()
        if not block:
            continue
        consumed += len(block)
        detected = _classify_section(block.lower())
        if detected:
            section = detected
        candidate = f"{current}\n\n{block}".strip() if current else block
        if len(candidate) <= per_segment_limit:
            current = candidate
            continue
        flush_segment()
        if len(block) <= per_segment_limit:
            current = block
            continue
        start = 0
        while start < len(block) and consumed <= total_char_limit:
            piece = block[start : start + per_segment_limit].strip()
            if piece:
                speaker, body = _extract_speaker(piece)
                seg_text = body if speaker else piece
                segments.append(
                    TranscriptSegmentDraft(
                        segment_index=len(segments),
                        speaker=speaker,
                        section=section,
                        text=seg_text,
                        token_count=max(1, int(len(seg_text.split()))),
                    )
                )
            start += per_segment_limit
    flush_segment()
    return segments


def fetch_alpha_vantage_transcript(ticker: str, fiscal_year: int, fiscal_quarter: int) -> TranscriptDraft:
    key = settings.alpha_vantage_api_key
    if not key:
        raise TranscriptProviderError("ALPHA_VANTAGE_API_KEY not configured")
    if int(fiscal_quarter) not in (1, 2, 3, 4):
        raise TranscriptProviderError("fiscal_quarter must be 1..4")

    quarter = fiscal_quarter_code(fiscal_year, fiscal_quarter)
    params = {
        "function": "EARNINGS_CALL_TRANSCRIPT",
        "symbol": ticker.upper().strip(),
        "quarter": quarter,
        "apikey": key,
    }
    try:
        resp = requests.get(ALPHA_VANTAGE_TRANSCRIPT_URL, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        # Never echo raw exception text here; request URLs can contain API-key query params.
        raise TranscriptProviderError("provider_request_failed") from exc
    except ValueError as exc:
        raise TranscriptProviderError("provider_invalid_json") from exc

    if isinstance(payload, dict):
        if payload.get("Error Message"):
            raise TranscriptProviderError("provider_error_message")
        if payload.get("Information"):
            raise TranscriptProviderError("provider_information_message")
        if payload.get("Note"):
            raise TranscriptProviderError("provider_rate_limited")

    node = _extract_payload_node(payload if isinstance(payload, dict) else {"transcript": payload})
    transcript_text = _extract_text(node)
    if not transcript_text:
        raise TranscriptProviderError("empty_transcript")

    storage_mode = (settings.transcripts_storage_mode or "restricted").strip().lower()
    if storage_mode not in {"restricted", "standard"}:
        storage_mode = "restricted"
    excerpt_limit = max(2000, int(settings.transcripts_excerpt_char_limit or 12000))
    segment_limit = max(200, int(settings.transcripts_segment_char_limit or 800))

    text_for_storage = transcript_text if storage_mode == "standard" else transcript_text[:excerpt_limit]
    blocks = _split_into_blocks(text_for_storage)
    segments = _chunk_text_blocks(
        blocks=blocks,
        per_segment_limit=segment_limit,
        total_char_limit=len(text_for_storage),
    )
    if not segments:
        segments = [
            TranscriptSegmentDraft(
                segment_index=0,
                speaker=None,
                section=None,
                text=text_for_storage,
                token_count=max(1, int(len(text_for_storage.split()))),
            )
        ]

    call_date = _parse_call_date(node.get("date") or node.get("call_date") or node.get("time_published"))
    source_url = node.get("url") if isinstance(node.get("url"), str) else None
    source_doc_id = None
    for key_name in ("id", "document_id", "source_doc_id"):
        val = node.get(key_name)
        if isinstance(val, (str, int)):
            source_doc_id = str(val)
            break
    if not source_doc_id:
        source_doc_id = f"{ticker.upper()}-{quarter}"

    content_hash = hashlib.sha256(text_for_storage.encode("utf-8")).hexdigest()

    return TranscriptDraft(
        ticker=ticker.upper().strip(),
        fiscal_year=int(fiscal_year),
        fiscal_quarter=int(fiscal_quarter),
        source_provider="alpha_vantage",
        source_url=source_url,
        source_doc_id=source_doc_id,
        call_date=call_date,
        language="en",
        storage_mode=storage_mode,
        content_hash=content_hash,
        segments=segments,
    )
