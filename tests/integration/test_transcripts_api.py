from __future__ import annotations

from datetime import date
import json
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.models import Company, EarningsCallTranscript
from app.routers import transcripts as transcripts_router
from app.services.earnings_transcripts import TranscriptSegmentDraft


@dataclass
class _Draft:
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


def _build_test_client():
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(transcripts_router.router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    return client, TestingSessionLocal


def test_sync_list_and_detail_transcript_flow(monkeypatch):
    client, SessionLocal = _build_test_client()

    with SessionLocal() as db:
        db.add(Company(ticker="NVDA", name="NVIDIA Corporation"))
        db.commit()

    monkeypatch.setattr(transcripts_router.settings, "admin_settings_token", "admin-token")

    def fake_fetch(ticker: str, fiscal_year: int, fiscal_quarter: int):
        return _Draft(
            ticker=ticker,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            source_provider="alpha_vantage",
            source_url="https://example.com/transcript",
            source_doc_id=f"{ticker}-{fiscal_year}Q{fiscal_quarter}",
            call_date=date(2026, 1, 30),
            language="en",
            storage_mode="restricted",
            content_hash="abc123",
            segments=[
                TranscriptSegmentDraft(
                    segment_index=0,
                    speaker="Operator",
                    section="prepared_remarks",
                    text="Welcome to the earnings call.",
                    token_count=5,
                ),
                TranscriptSegmentDraft(
                    segment_index=1,
                    speaker="CEO",
                    section="prepared_remarks",
                    text="Revenue growth was strong this quarter.",
                    token_count=7,
                ),
            ],
        )

    monkeypatch.setattr(transcripts_router, "fetch_alpha_vantage_transcript", fake_fetch)

    sync = client.post(
        "/transcripts/sync",
        headers={"Authorization": "Bearer admin-token"},
        json={"ticker": "NVDA", "fiscal_year": 2026, "fiscal_quarter": 1},
    )
    assert sync.status_code == 200
    body = sync.json()
    assert body["transcript"]["ticker"] == "NVDA"
    assert body["transcript"]["segment_count"] == 2
    payload_text = json.dumps(body)
    assert "apikey" not in payload_text.lower()
    assert "openai" not in payload_text.lower()
    transcript_id = body["transcript"]["id"]
    company_id = body["transcript"]["company_id"]

    listing = client.get(f"/companies/{company_id}/transcripts")
    assert listing.status_code == 200
    rows = listing.json()
    assert len(rows) == 1
    assert rows[0]["id"] == transcript_id
    assert rows[0]["segment_count"] == 2

    detail = client.get(f"/transcripts/{transcript_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["transcript"]["id"] == transcript_id
    assert [s["segment_index"] for s in payload["segments"]] == [0, 1]

    # Idempotent re-sync should update existing row, not create a duplicate.
    sync_again = client.post(
        "/transcripts/sync",
        headers={"Authorization": "Bearer admin-token"},
        json={"ticker": "NVDA", "fiscal_year": 2026, "fiscal_quarter": 1},
    )
    assert sync_again.status_code == 200
    body2 = sync_again.json()
    assert body2["transcript"]["id"] == transcript_id
    with SessionLocal() as db:
        total = db.execute(select(func.count(EarningsCallTranscript.id))).scalar_one()
    assert int(total) == 1


def test_sync_requires_valid_admin_token(monkeypatch):
    client, SessionLocal = _build_test_client()

    with SessionLocal() as db:
        db.add(Company(ticker="AAPL", name="Apple Inc."))
        db.commit()

    monkeypatch.setattr(transcripts_router.settings, "admin_settings_token", "correct-token")

    missing = client.post(
        "/transcripts/sync",
        json={"ticker": "AAPL", "fiscal_year": 2026, "fiscal_quarter": 1},
    )
    assert missing.status_code == 401

    wrong = client.post(
        "/transcripts/sync",
        headers={"Authorization": "Bearer wrong-token"},
        json={"ticker": "AAPL", "fiscal_year": 2026, "fiscal_quarter": 1},
    )
    assert wrong.status_code == 403


def test_sync_falls_back_to_cached_transcript_when_provider_fails(monkeypatch):
    client, SessionLocal = _build_test_client()
    monkeypatch.setattr(transcripts_router.settings, "admin_settings_token", "admin-token")

    with SessionLocal() as db:
        company = Company(ticker="MSFT", name="Microsoft Corporation")
        db.add(company)
        db.commit()

    def fake_ok(ticker: str, fiscal_year: int, fiscal_quarter: int):
        return _Draft(
            ticker=ticker,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            source_provider="alpha_vantage",
            source_url="https://example.com/msft-transcript",
            source_doc_id=f"{ticker}-{fiscal_year}Q{fiscal_quarter}",
            call_date=date(2026, 2, 1),
            language="en",
            storage_mode="restricted",
            content_hash="hash-ok",
            segments=[
                TranscriptSegmentDraft(
                    segment_index=0,
                    speaker="Operator",
                    section="prepared_remarks",
                    text="Cached transcript segment.",
                    token_count=3,
                )
            ],
        )

    monkeypatch.setattr(transcripts_router, "fetch_alpha_vantage_transcript", fake_ok)
    first = client.post(
        "/transcripts/sync",
        headers={"Authorization": "Bearer admin-token"},
        json={"ticker": "MSFT", "fiscal_year": 2026, "fiscal_quarter": 1},
    )
    assert first.status_code == 200
    cached_id = first.json()["transcript"]["id"]

    def fake_fail(*_args, **_kwargs):
        raise transcripts_router.TranscriptProviderError("provider_rate_limited")

    monkeypatch.setattr(transcripts_router, "fetch_alpha_vantage_transcript", fake_fail)
    fallback = client.post(
        "/transcripts/sync",
        headers={"Authorization": "Bearer admin-token"},
        json={"ticker": "MSFT", "fiscal_year": 2026, "fiscal_quarter": 1},
    )
    assert fallback.status_code == 200
    assert fallback.json()["transcript"]["id"] == cached_id
