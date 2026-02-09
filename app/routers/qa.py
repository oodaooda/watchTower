from __future__ import annotations

import json
import re
from typing import Dict, Optional, Tuple, List

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI
import logging
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.models import Company, FinancialAnnual, PriceAnnual
from app.core.schemas import QARequest, QAResponse

router = APIRouter(prefix="/qa", tags=["qa"])
log = logging.getLogger("watchtower.qa")


def _openai_client() -> Optional[OpenAI]:
    key = settings.modeling_openai_api_key or settings.pharma_openai_api_key
    if not key:
        return None
    return OpenAI(api_key=key)


def _extract_ticker(question: str) -> Optional[str]:
    if not question:
        return None
    # Prefer ticker in parentheses: "Tesla (TSLA)"
    m = re.search(r"\(([A-Z]{1,5})\)", question.upper())
    if m:
        return m.group(1)
    # Match "ticker XYZ"
    m = re.search(r"\bticker\s+([A-Z]{1,5})\b", question.upper())
    if m:
        return m.group(1)
    # Fallback: first uppercase token (skip common words)
    stop = {"WHAT", "WHATS", "THE", "AND", "FOR", "WITH", "WAS", "IS", "ARE", "IT", "ITS", "LAST", "YEARS", "YEAR"}
    candidates = [
        c for c in re.findall(r"\b[A-Z]{2,5}\b", question.upper()) if c not in stop
    ]
    return candidates[0] if candidates else None


def _extract_company_keywords(question: str) -> List[str]:
    if not question:
        return []
    q = question.lower()
    q = re.sub(r"[^\w\s']", " ", q)
    tokens = [t for t in q.split() if len(t) > 2]
    stop = {
        "what", "whats", "the", "and", "for", "with", "was", "is", "are", "earnings",
        "revenue", "income", "net", "last", "years", "year", "show", "of", "it", "its",
        "ten", "ttm", "pe", "p", "e",
    }
    cleaned = []
    for t in tokens:
        if t in stop:
            continue
        if t.endswith("'s"):
            t = t[:-2]
        elif t.endswith("s") and len(t) > 3:
            t = t[:-1]
        if t and t not in stop:
            cleaned.append(t)
    return cleaned


def _resolve_company_by_name(db: Session, question: str) -> Optional[Company]:
    keywords = _extract_company_keywords(question)
    for kw in sorted(keywords, key=len, reverse=True):
        stmt = select(Company).where(func.lower(Company.name).like(f"%{kw.lower()}%"))
        match = db.execute(stmt).scalar_one_or_none()
        if match:
            return match
    return None


def _parse_with_llm(question: str) -> Optional[Dict[str, str]]:
    client = _openai_client()
    if not client:
        return None
    system = (
        "You are a financial data query parser. Return JSON only. "
        "Allowed actions: pe, earnings_history, revenue_history, eps_history. "
        "Return keys: action, ticker, years (optional)."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
        )
        raw = response.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception:
        return None


def _resolve_company(db: Session, ticker: str) -> Optional[Company]:
    if not ticker:
        return None
    stmt = select(Company).where(func.upper(Company.ticker) == ticker.upper())
    return db.execute(stmt).scalar_one_or_none()


def _latest_pe(db: Session, company_id: int) -> Tuple[Optional[float], Optional[int]]:
    stmt = (
        select(PriceAnnual)
        .where(PriceAnnual.company_id == company_id)
        .order_by(PriceAnnual.fiscal_year.desc())
        .limit(1)
    )
    row = db.execute(stmt).scalar_one_or_none()
    if not row:
        return None, None
    return (float(row.pe_ttm) if row.pe_ttm is not None else None, row.fiscal_year)


def _history(db: Session, company_id: int, field: str, years: int = 10):
    stmt = (
        select(FinancialAnnual.fiscal_year, getattr(FinancialAnnual, field))
        .where(FinancialAnnual.company_id == company_id)
        .order_by(FinancialAnnual.fiscal_year.desc())
        .limit(years)
    )
    rows = db.execute(stmt).all()
    return [
        {"fiscal_year": year, field: float(value) if value is not None else None}
        for year, value in rows
    ][::-1]


@router.post("", response_model=QAResponse)
def qa_answer(payload: QARequest, db: Session = Depends(get_db)):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    parsed = _parse_with_llm(question) or {}
    action = parsed.get("action") or ""
    ticker = parsed.get("ticker") or _extract_ticker(question)
    years = int(parsed.get("years") or 10)
    years = max(1, min(years, 20))

    if not ticker:
        company = _resolve_company_by_name(db, question)
        if company:
            ticker = company.ticker
        else:
            log.info("qa_no_ticker", extra={"question": question})
            return QAResponse(
                answer="Please specify a ticker (e.g., AAPL).",
                citations=[],
                data={},
            )

    company = _resolve_company(db, ticker)
    if not company:
        company = _resolve_company_by_name(db, question)
    if not company:
        log.info("qa_company_not_found", extra={"question": question, "ticker": ticker})
        return QAResponse(
            answer=f"I couldn't find a company for ticker {ticker}.",
            citations=["companies"],
            data={},
        )

    if action == "pe":
        pe, fy = _latest_pe(db, company.id)
        if pe is None:
            log.info("qa_pe_missing", extra={"ticker": ticker})
            return QAResponse(
                answer=f"No P/E data available for {ticker}.",
                citations=["prices_annual"],
                data={},
            )
        log.info("qa_pe", extra={"ticker": ticker, "pe": pe, "fiscal_year": fy})
        return QAResponse(
            answer=f"The latest P/E (TTM) for {ticker} is {pe:.2f} (FY {fy}).",
            citations=["prices_annual"],
            data={"ticker": ticker, "pe_ttm": pe, "fiscal_year": fy},
        )

    if action == "revenue_history":
        rows = _history(db, company.id, "revenue", years)
        log.info("qa_revenue_history", extra={"ticker": ticker, "years": len(rows)})
        return QAResponse(
            answer=f"Revenue history for {ticker} over the last {len(rows)} years is available.",
            citations=["financials_annual"],
            data={"ticker": ticker, "history": rows},
        )

    if action == "eps_history":
        stmt = (
            select(PriceAnnual.fiscal_year, PriceAnnual.eps)
            .where(PriceAnnual.company_id == company.id)
            .order_by(PriceAnnual.fiscal_year.desc())
            .limit(years)
        )
        rows = db.execute(stmt).all()
        history = [
            {"fiscal_year": year, "eps": float(value) if value is not None else None}
            for year, value in rows
        ][::-1]
        log.info("qa_eps_history", extra={"ticker": ticker, "years": len(history)})
        return QAResponse(
            answer=f"EPS history for {ticker} over the last {len(history)} years is available.",
            citations=["prices_annual"],
            data={"ticker": ticker, "history": history},
        )

    # default: earnings history (net income)
    rows = _history(db, company.id, "net_income", years)
    log.info("qa_earnings_history", extra={"ticker": ticker, "years": len(rows)})
    return QAResponse(
        answer=f"Earnings (net income) history for {ticker} over the last {len(rows)} years is available.",
        citations=["financials_annual"],
        data={"ticker": ticker, "history": rows},
    )
