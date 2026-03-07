from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_qa_db
from app.core.models import Company, EarningsCallTranscript, EarningsCallTranscriptSegment
from app.routers.qa import router as qa_router


def _build_test_client():
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(qa_router)

    def override_get_qa_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_qa_db] = override_get_qa_db
    client = TestClient(app)
    return client, SessionLocal


def test_qa_transcript_question_returns_transcript_citations():
    client, SessionLocal = _build_test_client()

    with SessionLocal() as db:
        company = Company(ticker="NVDA", name="NVIDIA Corporation")
        db.add(company)
        db.commit()
        db.refresh(company)

        transcript = EarningsCallTranscript(
            company_id=company.id,
            ticker="NVDA",
            fiscal_year=2026,
            fiscal_quarter=1,
            source_provider="alpha_vantage",
            source_url="https://example.com/nvda-transcript",
            source_doc_id="NVDA-2026Q1",
            content_hash="hash",
            language="en",
            storage_mode="restricted",
        )
        db.add(transcript)
        db.flush()
        db.add(
            EarningsCallTranscriptSegment(
                transcript_id=transcript.id,
                segment_index=0,
                speaker="CEO",
                section="prepared_remarks",
                text="Management discussed AI demand acceleration and margin expansion.",
                token_count=9,
            )
        )
        db.commit()

    res = client.post("/qa", json={"question": "What did management say on the earnings call transcript for NVDA?"})
    assert res.status_code == 200
    body = res.json()
    assert "earnings_call_transcripts" in body["citations"]
    assert "earnings_call_transcript_segments" in body["citations"]
