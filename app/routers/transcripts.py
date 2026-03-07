from __future__ import annotations

from datetime import datetime
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.models import Company, EarningsCallTranscript, EarningsCallTranscriptSegment
from app.core.schemas import (
    EarningsTranscriptDetailOut,
    EarningsTranscriptOut,
    EarningsTranscriptSegmentOut,
    TranscriptSyncIn,
)
from app.services.earnings_transcripts import TranscriptProviderError, fetch_alpha_vantage_transcript

router = APIRouter(tags=["transcripts"])
log = logging.getLogger("watchtower.transcripts")


def _require_admin(authorization: str | None) -> None:
    token = settings.admin_settings_token
    if not token:
        raise HTTPException(status_code=503, detail="Settings admin token not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    if authorization.replace("Bearer ", "", 1).strip() != token:
        raise HTTPException(status_code=403, detail="Invalid token")


def _transcript_detail(db: Session, transcript_row: EarningsCallTranscript) -> EarningsTranscriptDetailOut:
    segment_rows = db.execute(
        select(EarningsCallTranscriptSegment)
        .where(EarningsCallTranscriptSegment.transcript_id == transcript_row.id)
        .order_by(EarningsCallTranscriptSegment.segment_index.asc())
    ).scalars().all()

    out = EarningsTranscriptOut.model_validate(transcript_row)
    out.segment_count = len(segment_rows)
    return EarningsTranscriptDetailOut(
        transcript=out,
        segments=[EarningsTranscriptSegmentOut.model_validate(s) for s in segment_rows],
    )


@router.post("/transcripts/sync", response_model=EarningsTranscriptDetailOut)
def sync_transcript(
    payload: TranscriptSyncIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin(authorization)
    ticker = (payload.ticker or "").upper().strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    if payload.fiscal_quarter not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="fiscal_quarter must be 1..4")

    company = db.execute(select(Company).where(Company.ticker == ticker).limit(1)).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found for ticker")

    existing = db.execute(
        select(EarningsCallTranscript).where(
            EarningsCallTranscript.company_id == company.id,
            EarningsCallTranscript.fiscal_year == payload.fiscal_year,
            EarningsCallTranscript.fiscal_quarter == payload.fiscal_quarter,
            EarningsCallTranscript.source_provider == "alpha_vantage",
        )
    ).scalar_one_or_none()

    try:
        draft = fetch_alpha_vantage_transcript(ticker, payload.fiscal_year, payload.fiscal_quarter)
    except TranscriptProviderError as exc:
        log.warning(
            "transcript_provider_error",
            extra={
                "ticker": ticker,
                "fiscal_year": payload.fiscal_year,
                "fiscal_quarter": payload.fiscal_quarter,
                "error_type": type(exc).__name__,
            },
        )
        if existing:
            log.info(
                "transcript_sync_fallback_cached",
                extra={
                    "ticker": ticker,
                    "fiscal_year": payload.fiscal_year,
                    "fiscal_quarter": payload.fiscal_quarter,
                    "transcript_id": existing.id,
                },
            )
            return _transcript_detail(db, existing)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if existing:
        existing.call_date = draft.call_date
        existing.source_url = draft.source_url
        existing.source_doc_id = draft.source_doc_id
        existing.content_hash = draft.content_hash
        existing.language = draft.language
        existing.storage_mode = draft.storage_mode
        existing.updated_at = datetime.utcnow()
        transcript_row = existing
        db.execute(delete(EarningsCallTranscriptSegment).where(EarningsCallTranscriptSegment.transcript_id == existing.id))
    else:
        transcript_row = EarningsCallTranscript(
            company_id=company.id,
            ticker=ticker,
            fiscal_year=draft.fiscal_year,
            fiscal_quarter=draft.fiscal_quarter,
            call_date=draft.call_date,
            source_provider=draft.source_provider,
            source_url=draft.source_url,
            source_doc_id=draft.source_doc_id,
            content_hash=draft.content_hash,
            language=draft.language,
            storage_mode=draft.storage_mode,
        )
        db.add(transcript_row)
        db.flush()

    for seg in draft.segments:
        db.add(
            EarningsCallTranscriptSegment(
                transcript_id=transcript_row.id,
                segment_index=seg.segment_index,
                speaker=seg.speaker,
                section=seg.section,
                text=seg.text,
                token_count=seg.token_count,
            )
        )

    db.commit()
    db.refresh(transcript_row)
    log.info(
        "transcript_sync_success",
        extra={
            "ticker": ticker,
            "fiscal_year": draft.fiscal_year,
            "fiscal_quarter": draft.fiscal_quarter,
            "transcript_id": transcript_row.id,
            "segment_count": len(draft.segments),
            "storage_mode": draft.storage_mode,
        },
    )
    return _transcript_detail(db, transcript_row)


@router.get("/companies/{company_id}/transcripts", response_model=list[EarningsTranscriptOut])
def list_company_transcripts(company_id: int, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    rows = db.execute(
        select(
            EarningsCallTranscript,
            func.count(EarningsCallTranscriptSegment.id).label("segment_count"),
        )
        .outerjoin(
            EarningsCallTranscriptSegment,
            EarningsCallTranscriptSegment.transcript_id == EarningsCallTranscript.id,
        )
        .where(EarningsCallTranscript.company_id == company_id)
        .group_by(EarningsCallTranscript.id)
        .order_by(
            EarningsCallTranscript.fiscal_year.desc(),
            EarningsCallTranscript.fiscal_quarter.desc(),
            EarningsCallTranscript.ingested_at.desc(),
        )
    ).all()

    out: list[EarningsTranscriptOut] = []
    for transcript, segment_count in rows:
        item = EarningsTranscriptOut.model_validate(transcript)
        item.segment_count = int(segment_count or 0)
        out.append(item)
    return out


@router.get("/transcripts/{transcript_id}", response_model=EarningsTranscriptDetailOut)
def get_transcript_detail(transcript_id: int, db: Session = Depends(get_db)):
    transcript_row = db.get(EarningsCallTranscript, transcript_id)
    if not transcript_row:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return _transcript_detail(db, transcript_row)
