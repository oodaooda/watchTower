from __future__ import annotations

import json
import ipaddress
import re
import time
from typing import Any, Dict, Optional, Tuple, List
from urllib.parse import urlparse

import requests

from fastapi import APIRouter, Depends, HTTPException
import logging
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.routers.prices import _get_company_news

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency in some local test environments
    OpenAI = None  # type: ignore[assignment]

from app.core.config import settings
from app.core.db import get_db
from app.core.models import Company, FinancialAnnual, PriceAnnual
from app.core.schemas import QARequest, QAResponse

router = APIRouter(prefix="/qa", tags=["qa"])
log = logging.getLogger("watchtower.qa")

ALLOWED_ACTIONS = {
    "company_snapshot",
    "pe",
    "earnings_history",
    "revenue_history",
    "eps_history",
    "margin_trend",
    "news_context",
}
ALLOWED_RESPONSE_MODES = {"grounded", "general", "hybrid"}
TRACE_PARAM_ALLOWLIST = {
    "company_id",
    "years",
    "field",
    "ticker",
    "company_name",
    "limit",
}
COMPANY_TOKEN_STOPWORDS = {
    "CAN",
    "YOU",
    "ME",
    "VS",
    "VERSUS",
    "ABOUT",
    "TELL",
    "WHAT",
    "WHY",
    "HOW",
    "WAS",
    "IS",
    "ARE",
    "DOWN",
    "UP",
    "LAST",
    "WEEK",
    "NEWS",
    "LATEST",
    "OF",
}
RESOLVER_AUTO_RESOLVE_MIN_CONFIDENCE = 0.8
NEWS_FETCH_TIMEOUT_SECONDS = 4.0
NEWS_FETCH_MAX_BYTES = 150_000
NEWS_FETCH_MAX_ARTICLES = 3
NEWS_SNIPPET_CHARS = 800


def _openai_client() -> Optional[OpenAI]:
    if OpenAI is None:
        return None
    key = settings.modeling_openai_api_key or settings.pharma_openai_api_key
    if not key:
        return None
    return OpenAI(api_key=key)


def _extract_ticker(question: str) -> Optional[str]:
    if not question:
        return None
    m = re.search(r"\(([A-Z]{1,5})\)", question.upper())
    if m:
        return m.group(1)
    m = re.search(r"\bticker\s+([A-Z]{1,5})\b", question.upper())
    if m:
        return m.group(1)
    stop = {
        "WHAT",
        "WHATS",
        "THE",
        "AND",
        "FOR",
        "WITH",
        "WAS",
        "IS",
        "ARE",
        "IT",
        "ITS",
        "LAST",
        "YEARS",
        "YEAR",
    }
    candidates = [c for c in re.findall(r"\b[A-Z]{2,5}\b", question.upper()) if c not in stop]
    return candidates[0] if candidates else None


def _extract_tickers(question: str) -> List[str]:
    if not question:
        return []
    # Prefer explicit cues first.
    explicit: List[str] = []
    for m in re.finditer(r"\(([A-Za-z]{1,5})\)", question):
        explicit.append(m.group(1).upper())
    for m in re.finditer(r"\bticker\s+([A-Za-z]{1,5})\b", question, flags=re.IGNORECASE):
        explicit.append(m.group(1).upper())
    # Contextual cue for lowercase ticker mention in natural prose (e.g. "news on qcls").
    for m in re.finditer(r"\b(?:about|on|for)\s+([A-Za-z]{1,5})\b", question, flags=re.IGNORECASE):
        explicit.append(m.group(1).upper())

    stop = {
        "WHAT",
        "WHATS",
        "THE",
        "AND",
        "FOR",
        "WITH",
        "WAS",
        "IS",
        "ARE",
        "IT",
        "ITS",
        "LAST",
        "YEARS",
        "YEAR",
        "TELL",
        "ABOUT",
        "DOWN",
        "UP",
        "WEEK",
        "NEWS",
        "LATEST",
        "OF",
    }
    # Case-aware extraction: only include naturally uppercase tokens as ticker candidates.
    # This prevents normal words like "on" / "have" from becoming fake tickers.
    uppercase_tokens = [tok for tok in re.findall(r"\b[A-Za-z]{2,5}\b", question) if tok.isupper()]
    candidates = [c.upper() for c in uppercase_tokens if c.upper() not in stop]
    candidates.extend([c for c in explicit if c not in stop])
    dedup: List[str] = []
    for c in candidates:
        if c not in dedup:
            dedup.append(c)
    return dedup


def _extract_compare_entities(question: str) -> List[str]:
    q = (question or "").strip()
    if not q:
        return []
    m = re.search(r"(.+?)\b(?:vs|versus)\b(.+)", q, flags=re.IGNORECASE)
    if not m:
        return []
    left = m.group(1).strip()
    right = m.group(2).strip()

    def _pick(seg: str) -> Optional[str]:
        if not seg:
            return None
        # Prefer ticker in parentheses e.g. "Tesla (TSLA)"
        p = re.search(r"\(([A-Za-z]{1,5})\)", seg)
        if p:
            return p.group(1).upper()
        # Use trailing token as likely entity handle.
        tokens = re.findall(r"[A-Za-z]{2,15}", seg)
        if not tokens:
            return None
        return tokens[-1].upper() if len(tokens[-1]) <= 5 else tokens[-1]

    out: List[str] = []
    for seg in (left, right):
        c = _pick(seg)
        if c:
            out.append(c)
    return out


def _extract_company_keywords(question: str) -> List[str]:
    if not question:
        return []
    q = question.lower()
    q = re.sub(r"[^\w\s']", " ", q)
    tokens = [t for t in q.split() if len(t) > 2]
    stop = {
        "what",
        "whats",
        "the",
        "and",
        "for",
        "with",
        "was",
        "is",
        "are",
        "earnings",
        "revenue",
        "income",
        "net",
        "last",
        "years",
        "year",
        "show",
        "of",
        "it",
        "its",
        "ten",
        "ttm",
        "pe",
        "p",
        "e",
        "about",
        "tell",
        "compare",
        "versus",
        "vs",
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
        stmt = (
            select(Company)
            .where(func.lower(Company.name).like(f"%{kw.lower()}%"))
            .order_by(func.length(Company.name).asc(), Company.id.asc())
            .limit(5)
        )
        match = db.execute(stmt).scalars().first()
        if match:
            return match
    return None


def _parse_with_llm(question: str) -> Optional[Dict[str, Any]]:
    client = _openai_client()
    if not client:
        return None
    system = (
        "You are a financial query planner. Return strict JSON only. "
        "Allowed actions: company_snapshot, pe, earnings_history, revenue_history, eps_history, margin_trend. "
        "Return keys: companies (array of ticker/name strings), ticker (optional), company_name (optional), "
        "years (optional), actions (array), compare (bool), response_mode (grounded|general|hybrid)."
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


def _margin_trend(db: Session, company_id: int, years: int = 10) -> List[Dict[str, Optional[float]]]:
    stmt = (
        select(
            FinancialAnnual.fiscal_year,
            FinancialAnnual.revenue,
            FinancialAnnual.gross_profit,
            FinancialAnnual.operating_income,
            FinancialAnnual.net_income,
        )
        .where(FinancialAnnual.company_id == company_id)
        .order_by(FinancialAnnual.fiscal_year.desc())
        .limit(years)
    )
    rows = db.execute(stmt).all()
    out: List[Dict[str, Optional[float]]] = []
    for fiscal_year, revenue, gross_profit, operating_income, net_income in rows[::-1]:
        rev = float(revenue) if revenue is not None else None
        gm = (float(gross_profit) / rev) if (gross_profit is not None and rev and rev != 0) else None
        om = (float(operating_income) / rev) if (operating_income is not None and rev and rev != 0) else None
        nm = (float(net_income) / rev) if (net_income is not None and rev and rev != 0) else None
        out.append(
            {
                "fiscal_year": fiscal_year,
                "gross_margin_pct": gm,
                "operating_margin_pct": om,
                "net_margin_pct": nm,
            }
        )
    return out


def _safe_trace_params(params: Dict[str, Any]) -> Dict[str, Any]:
    safe: Dict[str, Any] = {}
    for key, value in params.items():
        if key not in TRACE_PARAM_ALLOWLIST:
            continue
        if isinstance(value, (str, int, float, bool)):
            if isinstance(value, str) and len(value) > 120:
                safe[key] = value[:117] + "..."
            else:
                safe[key] = value
    return safe


def _trace_entry(sql_template: str, params: Dict[str, Any], rows: int, duration_ms: float) -> Dict[str, Any]:
    return {
        "sql_template": sql_template,
        "params": _safe_trace_params(params),
        "rows": rows,
        "duration_ms": round(duration_ms, 2),
    }


def _default_actions(question: str, compare: bool) -> List[str]:
    q = question.lower()
    if _is_news_question(q):
        return ["company_snapshot", "pe", "news_context"]
    if compare:
        return ["company_snapshot", "pe", "revenue_history", "earnings_history", "margin_trend"]
    if "p/e" in q or "pe " in q or "valuation" in q:
        return ["pe"]
    if "eps" in q:
        return ["eps_history"]
    if "revenue" in q:
        return ["revenue_history"]
    if "earnings" in q or "net income" in q or "profit" in q:
        return ["earnings_history"]
    return ["company_snapshot", "pe", "revenue_history", "earnings_history", "margin_trend"]


def _is_news_question(question_lower: str) -> bool:
    return any(k in question_lower for k in ["why", "down", "up", "last week", "news", "headline", "sentiment"])


def _is_conceptual_question(question: str) -> bool:
    q = (question or "").strip().lower()
    if not q:
        return False
    conceptual_starters = (
        "what is",
        "what are",
        "explain",
        "how does",
        "how do",
        "why do",
        "difference between",
    )
    conceptual_terms = (
        "operating leverage",
        "gross margin",
        "net margin",
        "discount rate",
        "wacc",
        "dcf",
        "valuation multiple",
        "price to earnings",
        "p/e",
    )
    return q.startswith(conceptual_starters) or any(term in q for term in conceptual_terms)


def _is_metric_fact_question(question: str) -> bool:
    q = (question or "").strip().lower()
    if not q:
        return False
    metric_terms = (
        "last close",
        "close price",
        "price",
        "p/e",
        "pe ratio",
        "valuation",
        "revenue",
        "net income",
        "earnings",
        "eps",
        "margin",
    )
    return any(term in q for term in metric_terms)


def _requested_metric_fields(question: str) -> List[str]:
    q = (question or "").lower()
    fields: List[str] = []
    if any(k in q for k in ["last close", "close price", "share price", "stock price", "price"]):
        fields.append("close_price")
    if any(k in q for k in ["p/e", "pe ratio", "price to earnings", "valuation"]):
        fields.append("pe_ttm")
    if "revenue" in q:
        fields.append("revenue")
    if any(k in q for k in ["net income", "earnings", "profit"]):
        fields.append("net_income")
    if "eps" in q:
        fields.append("eps")
    # Preserve order and uniqueness.
    out: List[str] = []
    for f in fields:
        if f not in out:
            out.append(f)
    return out


def _contains_numeric_claims(text: str) -> bool:
    return bool(re.search(r"[$%]|\d", text or ""))


def _strip_numeric_sentences(text: str) -> str:
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = [p for p in parts if p and not _contains_numeric_claims(p)]
    return " ".join(kept).strip()


def _classify_response_mode(question: str, has_entities: bool, parsed_mode: Optional[str]) -> str:
    if parsed_mode in ALLOWED_RESPONSE_MODES:
        return parsed_mode
    if has_entities and _is_metric_fact_question(question):
        return "grounded"
    if _is_conceptual_question(question):
        return "hybrid" if has_entities else "general"
    return "grounded"


def _synthesize_general_context(question: str) -> str:
    client = _openai_client()
    if not client:
        return (
            "General context: This is a conceptual finance question. Focus on definitions, drivers, "
            "tradeoffs, and how to evaluate evidence before drawing conclusions."
        )
    prompt = (
        "You are a finance assistant. Answer conceptually with no numeric claims, prices, dates, or percentages. "
        "Explain the concept, common drivers, and practical interpretation in plain language."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.2,
        )
        raw = (response.choices[0].message.content or "").strip()
    except Exception:
        raw = ""
    cleaned = _strip_numeric_sentences(raw)
    return cleaned or "General context is available, but avoid numeric conclusions without grounded data."


def _build_structured_non_news_answer(
    question: str,
    companies: List[Company],
    payload_by_company: Dict[str, Any],
    unresolved: List[str],
    mode: str,
) -> Tuple[str, List[str]]:
    data_lines: List[str] = []
    gaps: List[str] = []
    used_sources: List[str] = []
    requested_fields = _requested_metric_fields(question)

    if companies:
        used_sources.append("database")
        for company in companies:
            company_payload = payload_by_company.get(company.ticker, {}) or {}
            snap = company_payload.get("company_snapshot", {}) or {}
            pe_payload = company_payload.get("pe", {}) or {}
            latest_fy = snap.get("latest_fiscal_year")
            revenue = snap.get("revenue")
            net_income = snap.get("net_income")
            close_price = snap.get("close_price")
            eps = snap.get("eps")
            pe_ttm = pe_payload.get("pe_ttm") if pe_payload else snap.get("pe_ttm")
            row = [f"{company.name} ({company.ticker})"]
            if requested_fields:
                if "close_price" in requested_fields:
                    if isinstance(close_price, (int, float)):
                        row.append(f"last close price: ${close_price:.2f}")
                    else:
                        gaps.append(f"{company.ticker}: close price is unavailable.")
                if "pe_ttm" in requested_fields:
                    if isinstance(pe_ttm, (int, float)):
                        row.append(f"P/E: {pe_ttm:.2f}")
                    else:
                        gaps.append(f"{company.ticker}: P/E is unavailable.")
                if "revenue" in requested_fields:
                    if latest_fy and isinstance(revenue, (int, float)):
                        row.append(f"revenue FY {latest_fy}: ${revenue/1e9:.2f}B")
                    else:
                        gaps.append(f"{company.ticker}: revenue is unavailable.")
                if "net_income" in requested_fields:
                    if latest_fy and isinstance(net_income, (int, float)):
                        row.append(f"net income FY {latest_fy}: ${net_income/1e9:.2f}B")
                    else:
                        gaps.append(f"{company.ticker}: net income is unavailable.")
                if "eps" in requested_fields:
                    if isinstance(eps, (int, float)):
                        row.append(f"EPS: {eps:.2f}")
                    else:
                        gaps.append(f"{company.ticker}: EPS is unavailable.")
            else:
                if latest_fy and isinstance(revenue, (int, float)):
                    row.append(f"revenue FY {latest_fy}: ${revenue/1e9:.2f}B")
                if latest_fy and isinstance(net_income, (int, float)):
                    row.append(f"net income FY {latest_fy}: ${net_income/1e9:.2f}B")
                if isinstance(pe_ttm, (int, float)):
                    row.append(f"P/E {pe_ttm:.2f}")
            data_lines.append("- " + " | ".join(row))
    else:
        data_lines.append("- No company-specific rows were resolved from the database for this prompt.")
        gaps.append("No resolved ticker/company for grounded metrics.")

    if unresolved:
        gaps.append("Unresolved entities: " + ", ".join(unresolved) + ".")

    if not gaps:
        gaps.append("No critical data gaps detected for resolved entities.")

    general_context = ""
    if mode in {"general", "hybrid"}:
        used_sources.append("general_context")
        general_context = _synthesize_general_context(question)
    else:
        general_context = "Grounded mode: interpretation is limited to retrieved database fields."

    answer = "\n".join(
        [
            "What data shows:",
            *data_lines,
            "",
            "General context:",
            f"- {general_context}",
            "",
            "Gaps:",
            *[f"- {g}" for g in gaps],
        ]
    ).strip()
    return answer, used_sources


def _news_context_for_company(company: Company, question: str, limit: int = 15) -> Dict[str, Any]:
    key = settings.alpha_vantage_api_key
    if not key:
        return {"items": [], "note": "Alpha Vantage API key not configured for news context."}
    try:
        items = _get_company_news(company.ticker.upper(), key, limit)
    except Exception:
        return {"items": [], "note": "News data unavailable right now."}

    top = _rank_news_items(items, question, top_n=5)
    article_snippets: List[Dict[str, Any]] = []
    for item in top[:NEWS_FETCH_MAX_ARTICLES]:
        url = item.get("url")
        if not isinstance(url, str) or not _is_safe_article_url(url):
            continue
        snippet = _fetch_article_excerpt(url)
        if snippet:
            article_snippets.append(snippet)

    return {
        "items": [
            {
                "title": i.get("title"),
                "summary": i.get("summary"),
                "url": i.get("url"),
                "source": i.get("source"),
                "published_at": i.get("published_at"),
                "sentiment": i.get("sentiment"),
                "relevance_score": i.get("relevance_score"),
            }
            for i in top
        ],
        "articles": article_snippets,
    }


def _rank_news_items(items: List[Dict[str, Any]], question: str, top_n: int = 5) -> List[Dict[str, Any]]:
    keywords = [k.lower() for k in _extract_company_keywords(question)]
    ranked: List[Tuple[int, Dict[str, Any]]] = []
    for it in items:
        blob = f"{(it.get('title') or '')} {(it.get('summary') or '')}".lower()
        score = 0
        for kw in keywords:
            if kw and kw in blob:
                score += 2
        sentiment = (it.get("sentiment") or "").lower()
        if "bearish" in sentiment or "bullish" in sentiment:
            score += 1
        ranked.append((score, it))
    ranked.sort(key=lambda x: x[0], reverse=True)
    out: List[Dict[str, Any]] = []
    for score, item in ranked[:top_n]:
        enriched = dict(item)
        enriched["relevance_score"] = score
        out.append(enriched)
    return out


def _is_safe_article_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return False
    # Block direct private/reserved IP access.
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        pass
    return True


def _strip_html_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?(</\1>)", " ", html)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fetch_article_excerpt(url: str) -> Optional[Dict[str, str]]:
    try:
        response = requests.get(url, timeout=NEWS_FETCH_TIMEOUT_SECONDS, headers={"User-Agent": "watchtower-qa/1.0"})
        response.raise_for_status()
        body = response.text[:NEWS_FETCH_MAX_BYTES]
    except Exception:
        return None

    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", body)
    title = title_match.group(1).strip() if title_match else ""
    text = _strip_html_text(body)
    if not text:
        return None
    return {"url": url, "title": title[:180], "snippet": text[:NEWS_SNIPPET_CHARS]}


def _build_plan(question: str) -> Dict[str, Any]:
    parsed = _parse_with_llm(question) or {}
    years_raw = parsed.get("years") if isinstance(parsed, dict) else None
    years = int(years_raw) if isinstance(years_raw, (int, str)) and str(years_raw).isdigit() else 10
    years = max(1, min(years, 20))

    compare = bool(parsed.get("compare")) if isinstance(parsed, dict) else False
    if not compare:
        q = question.lower()
        compare = (" vs " in q) or (" versus " in q) or (" compare " in q)

    parsed_mode: Optional[str] = None
    if isinstance(parsed, dict):
        mode = parsed.get("response_mode")
        if isinstance(mode, str):
            parsed_mode = mode

    def _normalize_company_candidate(raw: str) -> Optional[str]:
        c = (raw or "").strip()
        if not c:
            return None
        if re.fullmatch(r"[A-Za-z]{1,5}", c):
            u = c.upper()
            if u in COMPANY_TOKEN_STOPWORDS:
                return None
            return u
        if len(c) < 2:
            return None
        return c

    companies: List[str] = []
    if isinstance(parsed, dict):
        raw_companies = parsed.get("companies")
        if isinstance(raw_companies, list):
            for c in raw_companies:
                if isinstance(c, str):
                    nc = _normalize_company_candidate(c)
                    if nc:
                        companies.append(nc)
        ticker = parsed.get("ticker")
        if isinstance(ticker, str):
            nt = _normalize_company_candidate(ticker)
            if nt:
                companies.append(nt)
        company_name = parsed.get("company_name")
        if isinstance(company_name, str):
            nn = _normalize_company_candidate(company_name)
            if nn:
                companies.append(nn)

    explicit_tickers = _extract_tickers(question)
    compare_entities = _extract_compare_entities(question) if compare else []
    if compare_entities:
        for t in compare_entities:
            nt = _normalize_company_candidate(t)
            if nt:
                companies.append(nt)
    else:
        for t in explicit_tickers:
            nt = _normalize_company_candidate(t)
            if nt:
                companies.append(nt)
    if not companies:
        single = _extract_ticker(question)
        if single:
            companies.append(single)

    dedup_companies: List[str] = []
    for c in companies:
        key = c.upper() if re.fullmatch(r"[A-Za-z]{1,5}", c) else c.lower()
        if key not in {x.upper() if re.fullmatch(r"[A-Za-z]{1,5}", x) else x.lower() for x in dedup_companies}:
            dedup_companies.append(c)

    # Root-cause resolver rule: when prompt includes explicit tickers and is not compare mode,
    # keep ticker candidates only to avoid LLM parser leakage from generic words (e.g., "news", "of").
    if explicit_tickers and not compare:
        ticker_set = {t.upper() for t in explicit_tickers}
        dedup_companies = [
            c for c in dedup_companies if re.fullmatch(r"[A-Za-z]{1,5}", c) and c.upper() in ticker_set
        ] or list(ticker_set)

    parsed_actions = parsed.get("actions") if isinstance(parsed, dict) else None
    actions = [a for a in (parsed_actions or []) if isinstance(a, str) and a in ALLOWED_ACTIONS]
    if not actions:
        fallback = parsed.get("action") if isinstance(parsed, dict) else None
        if isinstance(fallback, str) and fallback in ALLOWED_ACTIONS:
            actions = [fallback]
    if not actions:
        actions = _default_actions(question, compare)
    # Root-cause guardrail: never let planner omit news context for price-move prompts.
    if _is_news_question(question.lower()):
        required = ["company_snapshot", "pe", "news_context"]
        for action in required:
            if action not in actions:
                actions.append(action)

    response_mode = _classify_response_mode(question, has_entities=bool(dedup_companies), parsed_mode=parsed_mode)

    return {
        "companies": dedup_companies,
        "years": years,
        "actions": actions,
        "compare": compare,
        "response_mode": response_mode,
    }


def _resolve_company_candidate(db: Session, question: str, candidate: str) -> Tuple[Optional[Company], float, str]:
    cand = candidate.strip()
    if not cand:
        return None, 0.0, "empty_candidate"
    if re.fullmatch(r"[A-Za-z]{1,5}", cand):
        resolved = _resolve_company(db, cand.upper())
        if resolved:
            return resolved, 1.0, "exact_ticker"
    stmt = (
        select(Company)
        .where(func.lower(Company.name).like(f"%{cand.lower()}%"))
        .order_by(func.length(Company.name).asc(), Company.id.asc())
        .limit(10)
    )
    matches = db.execute(stmt).scalars().all()
    if not matches:
        return None, 0.0, "no_name_match"
    exact = cand.lower()
    for m in matches:
        if (m.name or "").strip().lower() == exact:
            return m, 0.95, "exact_name"
    prefix_matches = [m for m in matches if (m.name or "").strip().lower().startswith(exact)]
    if len(prefix_matches) == 1 and len(exact) >= 3:
        return prefix_matches[0], 0.85, "unique_prefix_name"
    if len(matches) == 1 and len(exact) >= 4:
        return matches[0], 0.75, "single_contains_low_confidence"
    return matches[0], 0.4, "ambiguous_name"


def _resolve_companies_from_plan(
    db: Session, question: str, plan: Dict[str, Any]
) -> Tuple[List[Company], List[str], List[Dict[str, Any]]]:
    requested = [c for c in plan.get("companies", []) if isinstance(c, str) and c.strip()]
    resolved: List[Company] = []
    unresolved: List[str] = []
    seen_ids: set[int] = set()
    diagnostics: List[Dict[str, Any]] = []

    for candidate in requested:
        company, confidence, reason = _resolve_company_candidate(db, question, candidate)
        if not company:
            unresolved.append(candidate)
            diagnostics.append(
                {
                    "candidate": candidate,
                    "resolved_ticker": None,
                    "confidence": 0.0,
                    "reason": reason,
                    "decision": "unresolved",
                }
            )
            continue
        if confidence < RESOLVER_AUTO_RESOLVE_MIN_CONFIDENCE:
            unresolved.append(candidate)
            diagnostics.append(
                {
                    "candidate": candidate,
                    "resolved_ticker": company.ticker,
                    "resolved_name": company.name,
                    "confidence": confidence,
                    "reason": reason,
                    "decision": "clarification_required",
                }
            )
            continue
        if company.id in seen_ids:
            diagnostics.append(
                {
                    "candidate": candidate,
                    "resolved_ticker": company.ticker,
                    "confidence": confidence,
                    "reason": "duplicate",
                    "decision": "duplicate",
                }
            )
            continue
        seen_ids.add(company.id)
        resolved.append(company)
        diagnostics.append(
            {
                "candidate": candidate,
                "resolved_ticker": company.ticker,
                "confidence": confidence,
                "reason": reason,
                "decision": "resolved",
            }
        )

    return resolved, unresolved, diagnostics


def _execute_action(
    db: Session,
    company: Company,
    action: str,
    years: int,
    question: str,
) -> Tuple[Dict[str, Any], List[str], str, List[Dict[str, Any]]]:
    citations: List[str] = []
    queries: List[Dict[str, Any]] = []

    if action == "company_snapshot":
        started = time.perf_counter()
        fin_stmt = (
            select(FinancialAnnual)
            .where(FinancialAnnual.company_id == company.id)
            .order_by(FinancialAnnual.fiscal_year.desc())
            .limit(1)
        )
        fin = db.execute(fin_stmt).scalar_one_or_none()
        queries.append(
            _trace_entry(
                "SELECT * FROM financials_annual WHERE company_id=:company_id ORDER BY fiscal_year DESC LIMIT 1",
                {"company_id": company.id, "limit": 1},
                1 if fin else 0,
                (time.perf_counter() - started) * 1000,
            )
        )

        started = time.perf_counter()
        pr_stmt = (
            select(PriceAnnual)
            .where(PriceAnnual.company_id == company.id)
            .order_by(PriceAnnual.fiscal_year.desc())
            .limit(1)
        )
        pr = db.execute(pr_stmt).scalar_one_or_none()
        queries.append(
            _trace_entry(
                "SELECT * FROM prices_annual WHERE company_id=:company_id ORDER BY fiscal_year DESC LIMIT 1",
                {"company_id": company.id, "limit": 1},
                1 if pr else 0,
                (time.perf_counter() - started) * 1000,
            )
        )

        citations.extend(["companies", "financials_annual", "prices_annual"])
        return (
            {
                "ticker": company.ticker,
                "company_name": company.name,
                "industry_name": company.industry_name,
                "latest_fiscal_year": fin.fiscal_year if fin else (pr.fiscal_year if pr else None),
                "revenue": float(fin.revenue) if fin and fin.revenue is not None else None,
                "net_income": float(fin.net_income) if fin and fin.net_income is not None else None,
                "eps": float(pr.eps) if pr and pr.eps is not None else None,
                "pe_ttm": float(pr.pe_ttm) if pr and pr.pe_ttm is not None else None,
                "close_price": float(pr.close_price) if pr and pr.close_price is not None else None,
            },
            citations,
            "Pulled latest company snapshot (profile, latest financial year, valuation fields).",
            queries,
        )

    if action == "pe":
        started = time.perf_counter()
        pe, fy = _latest_pe(db, company.id)
        queries.append(
            _trace_entry(
                "SELECT pe_ttm, fiscal_year FROM prices_annual WHERE company_id=:company_id ORDER BY fiscal_year DESC LIMIT 1",
                {"company_id": company.id, "limit": 1},
                1 if fy else 0,
                (time.perf_counter() - started) * 1000,
            )
        )
        citations.append("prices_annual")
        return (
            {"ticker": company.ticker, "pe_ttm": pe, "fiscal_year": fy},
            citations,
            "Pulled latest P/E (TTM).",
            queries,
        )

    if action == "revenue_history":
        started = time.perf_counter()
        history = _history(db, company.id, "revenue", years)
        queries.append(
            _trace_entry(
                "SELECT fiscal_year, revenue FROM financials_annual WHERE company_id=:company_id ORDER BY fiscal_year DESC LIMIT :years",
                {"company_id": company.id, "years": years, "field": "revenue"},
                len(history),
                (time.perf_counter() - started) * 1000,
            )
        )
        citations.append("financials_annual")
        return (
            {"ticker": company.ticker, "history": history},
            citations,
            f"Pulled revenue history for {years} years.",
            queries,
        )

    if action == "eps_history":
        started = time.perf_counter()
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
        queries.append(
            _trace_entry(
                "SELECT fiscal_year, eps FROM prices_annual WHERE company_id=:company_id ORDER BY fiscal_year DESC LIMIT :years",
                {"company_id": company.id, "years": years},
                len(history),
                (time.perf_counter() - started) * 1000,
            )
        )
        citations.append("prices_annual")
        return (
            {"ticker": company.ticker, "history": history},
            citations,
            f"Pulled EPS history for {years} years.",
            queries,
        )

    if action == "margin_trend":
        started = time.perf_counter()
        history = _margin_trend(db, company.id, years)
        queries.append(
            _trace_entry(
                "SELECT fiscal_year, revenue, gross_profit, operating_income, net_income FROM financials_annual WHERE company_id=:company_id ORDER BY fiscal_year DESC LIMIT :years",
                {"company_id": company.id, "years": years},
                len(history),
                (time.perf_counter() - started) * 1000,
            )
        )
        citations.append("financials_annual")
        return (
            {"ticker": company.ticker, "history": history},
            citations,
            f"Calculated gross/operating/net margin trends for {years} years.",
            queries,
        )

    if action == "news_context":
        started = time.perf_counter()
        context = _news_context_for_company(company, question=question, limit=15)
        items = context.get("items", [])
        article_count = len(context.get("articles", [])) if isinstance(context.get("articles"), list) else 0
        queries.append(
            _trace_entry(
                "ALPHA_VANTAGE NEWS_SENTIMENT (ticker scoped, relevance ranked)",
                {"ticker": company.ticker, "limit": 15},
                len(items) if isinstance(items, list) else 0,
                (time.perf_counter() - started) * 1000,
            )
        )
        citations.append("news_sentiment")
        return (
            {"ticker": company.ticker, **context},
            citations,
            f"Pulled and ranked recent company headlines; fetched {article_count} article snippets for context.",
            queries,
        )

    # default: earnings history
    started = time.perf_counter()
    history = _history(db, company.id, "net_income", years)
    queries.append(
        _trace_entry(
            "SELECT fiscal_year, net_income FROM financials_annual WHERE company_id=:company_id ORDER BY fiscal_year DESC LIMIT :years",
            {"company_id": company.id, "years": years, "field": "net_income"},
            len(history),
            (time.perf_counter() - started) * 1000,
        )
    )
    citations.append("financials_annual")
    return (
        {"ticker": company.ticker, "history": history},
        citations,
        f"Pulled net income history for {years} years.",
        queries,
    )


def _synthesize_answer(
    question: str,
    companies: List[Company],
    plan: Dict[str, Any],
    payload_by_company: Dict[str, Any],
    unresolved: List[str],
) -> str:
    has_news_context = any(
        isinstance(company_payload, dict) and "news_context" in company_payload
        for company_payload in payload_by_company.values()
    )
    if has_news_context:
        return _synthesize_news_answer(companies, payload_by_company, unresolved)

    client = _openai_client()
    if not client:
        sections: List[str] = []
        for company in companies:
            snap = payload_by_company.get(company.ticker, {}).get("company_snapshot", {})
            pe = payload_by_company.get(company.ticker, {}).get("pe", {}).get("pe_ttm")
            fy = snap.get("latest_fiscal_year") if isinstance(snap, dict) else None
            if isinstance(pe, (float, int)) and fy is not None:
                sections.append(f"{company.name} ({company.ticker}): latest P/E {pe:.2f} (FY {fy}).")
            else:
                sections.append(f"{company.name} ({company.ticker}): summary available in returned data.")
        if unresolved:
            sections.append(f"Unresolved companies: {', '.join(unresolved)}.")
        return " ".join(sections)

    prompt = (
        "You are a finance assistant. Use only provided data for numeric claims. "
        "Be concise, professional, and explicit about missing data. "
        "For compare questions, summarize each company then key differences."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "plan": plan,
                            "resolved_companies": [{"ticker": c.ticker, "name": c.name} for c in companies],
                            "unresolved_companies": unresolved,
                            "data": payload_by_company,
                        },
                        ensure_ascii=True,
                    ),
                },
            ],
            temperature=0.2,
        )
        return (response.choices[0].message.content or "").strip() or "Summary is available in returned data payload."
    except Exception:
        return "Summary is available in returned data payload."


def _synthesize_news_answer(
    companies: List[Company], payload_by_company: Dict[str, Any], unresolved: List[str]
) -> str:
    lines: List[str] = []

    for company in companies:
        company_payload = payload_by_company.get(company.ticker, {}) or {}
        snap = company_payload.get("company_snapshot", {}) or {}
        pe_payload = company_payload.get("pe", {}) or {}
        revenue_history = (company_payload.get("revenue_history", {}) or {}).get("history", []) or []
        earnings_history = (company_payload.get("earnings_history", {}) or {}).get("history", []) or []
        news = company_payload.get("news_context", {}) or {}
        news_items = news.get("items", []) or []
        articles = news.get("articles", []) or []

        lines.append(f"{company.name} ({company.ticker})")

        data_signals: List[str] = []
        latest_revenue = snap.get("revenue")
        latest_net_income = snap.get("net_income")
        latest_fy = snap.get("latest_fiscal_year")
        latest_pe = pe_payload.get("pe_ttm") if pe_payload else snap.get("pe_ttm")
        close_price = snap.get("close_price")
        if latest_fy and isinstance(latest_revenue, (int, float)):
            data_signals.append(f"Latest revenue (FY {latest_fy}): ${latest_revenue/1e9:.2f}B.")
        if latest_fy and isinstance(latest_net_income, (int, float)):
            data_signals.append(f"Latest net income (FY {latest_fy}): ${latest_net_income/1e9:.2f}B.")
        if isinstance(latest_pe, (int, float)):
            data_signals.append(f"P/E (TTM): {latest_pe:.2f}.")
        if isinstance(close_price, (int, float)):
            data_signals.append(f"Latest close price: ${close_price:.2f}.")

        if len(revenue_history) >= 2:
            first = revenue_history[0].get("revenue")
            last = revenue_history[-1].get("revenue")
            if isinstance(first, (int, float)) and isinstance(last, (int, float)) and first > 0:
                growth = (last / first - 1.0) * 100.0
                data_signals.append(f"Revenue trend over loaded history: {growth:.1f}% total growth.")

        if len(earnings_history) >= 2:
            first_ni = earnings_history[0].get("net_income")
            last_ni = earnings_history[-1].get("net_income")
            if isinstance(first_ni, (int, float)) and isinstance(last_ni, (int, float)):
                direction = "improved" if last_ni >= first_ni else "declined"
                data_signals.append(f"Net income has {direction} versus the start of loaded history.")

        lines.append("Data signals:")
        if data_signals:
            lines.extend([f"- {s}" for s in data_signals])
        else:
            lines.append("- Limited financial snapshot data available.")

        lines.append("News catalysts:")
        if news_items:
            for item in news_items[:3]:
                title = item.get("title") or "Untitled headline"
                sentiment = item.get("sentiment")
                source = item.get("source")
                parts = [title]
                if source:
                    parts.append(f"source: {source}")
                if sentiment:
                    parts.append(f"sentiment: {sentiment}")
                lines.append(f"- {' | '.join(parts)}")
        else:
            lines.append("- No recent headlines were returned for this ticker.")

        lines.append("Confidence:")
        confidence_items: List[str] = []
        if news_items:
            confidence_items.append(f"Headline coverage found ({len(news_items)} items).")
        else:
            confidence_items.append("No headline evidence; explanation confidence is low.")
        if articles:
            confidence_items.append(f"Fetched article snippets: {len(articles)}.")
        else:
            confidence_items.append("Could not fetch article pages; relied on headline summaries only.")
        if unresolved:
            confidence_items.append(f"Unresolved entities in prompt: {', '.join(unresolved)}.")
        lines.extend([f"- {c}" for c in confidence_items])
        lines.append("")

    if unresolved:
        lines.append(f"Unresolved companies: {', '.join(unresolved)}.")
    return "\n".join(lines).strip()


def _answer_question(question: str, db: Session) -> QAResponse:
    plan = _build_plan(question)
    response_mode = plan.get("response_mode", "grounded")
    companies, unresolved, resolver_diagnostics = _resolve_companies_from_plan(db, question, plan)
    if not companies:
        if response_mode in {"general", "hybrid"}:
            answer, used_sources = _build_structured_non_news_answer(
                question=question,
                companies=[],
                payload_by_company={},
                unresolved=unresolved or plan.get("companies", []),
                mode=response_mode,
            )
            return QAResponse(
                answer=answer,
                citations=["general_context"] if "general_context" in used_sources else [],
                data={
                    "plan": {
                        "companies_requested": plan.get("companies", []),
                        "companies_resolved": [],
                        "unresolved_companies": unresolved or plan.get("companies", []),
                        "actions": [],
                        "years": int(plan.get("years") or 10),
                        "compare": bool(plan.get("compare")),
                        "response_mode": response_mode,
                        "resolver_diagnostics": resolver_diagnostics,
                    },
                    "queries": [],
                    "sources": used_sources,
                    "unresolved_companies": unresolved or plan.get("companies", []),
                    "resolver_diagnostics": resolver_diagnostics,
                },
                trace=["General/hybrid mode answer generated without resolved company rows."],
            )
        clarification_candidates = [
            d for d in resolver_diagnostics if d.get("decision") == "clarification_required"
        ]
        clarification_lines: List[str] = []
        for d in clarification_candidates[:5]:
            if d.get("resolved_ticker"):
                label = d.get("resolved_name") or d.get("resolved_ticker")
                clarification_lines.append(f"- {d.get('candidate')} -> {label} ({d.get('resolved_ticker')})")
        if clarification_lines:
            clarification_text = (
                "I couldn't confidently resolve one or more companies from this question. "
                "Please clarify the ticker or full company name:\n" + "\n".join(clarification_lines)
            )
        else:
            clarification_text = "I couldn't resolve a company from this question."
        log.info("qa_company_not_found", extra={"question": question, "companies": plan.get("companies", [])})
        return QAResponse(
            answer=clarification_text,
            citations=["companies"],
            data={
                "plan": plan,
                "queries": [],
                "sources": ["companies"],
                "unresolved_companies": plan.get("companies", []),
                "resolver_diagnostics": resolver_diagnostics,
                "clarification_needed": bool(clarification_lines),
                "clarification_candidates": clarification_lines,
            },
            trace=["Planner could not resolve any company from the prompt."],
        )

    actions = [a for a in plan.get("actions", []) if a in ALLOWED_ACTIONS]
    years = int(plan.get("years") or 10)
    compare_mode = bool(plan.get("compare"))
    if compare_mode and len(companies) >= 1:
        # For compare prompts, return the richer metric set even for partial resolution.
        actions = ["company_snapshot", "pe", "revenue_history", "earnings_history", "margin_trend"]

    results_by_company: Dict[str, Any] = {}
    citations: set[str] = set()
    query_trace: List[Dict[str, Any]] = []
    trace: List[str] = [
        f"Planner companies requested: {', '.join(plan.get('companies', [])) or 'none'}.",
        f"Planner companies resolved: {', '.join([c.ticker for c in companies])}.",
        f"Planner actions: {', '.join(actions)}.",
    ]
    if unresolved:
        trace.append(f"Unresolved companies: {', '.join(unresolved)}.")
    if resolver_diagnostics:
        for diag in resolver_diagnostics:
            trace.append(
                "Resolver: "
                f"{diag.get('candidate')} -> {diag.get('resolved_ticker') or 'unresolved'} "
                f"(confidence={diag.get('confidence')}, reason={diag.get('reason')})."
            )

    for company in companies:
        company_results: Dict[str, Any] = {}
        for action in actions:
            result, action_citations, action_trace, action_queries = _execute_action(
                db, company, action, years, question
            )
            company_results[action] = result
            citations.update(action_citations)
            trace.append(f"{company.ticker}: {action_trace}")
            for q in action_queries:
                q["company"] = company.ticker
                q["action"] = action
                query_trace.append(q)
        results_by_company[company.ticker] = company_results

    plan_out = {
        "companies_requested": plan.get("companies", []),
        "companies_resolved": [c.ticker for c in companies],
        "unresolved_companies": unresolved,
        "actions": actions,
        "years": years,
        "compare": bool(plan.get("compare")),
        "response_mode": plan.get("response_mode", "grounded"),
        "resolver_diagnostics": resolver_diagnostics,
    }

    missing_for_comparison: List[str] = []
    if compare_mode and unresolved:
        missing_for_comparison.append("No company record found for unresolved symbol/name.")
    if compare_mode and len(companies) == 1:
        missing_for_comparison.extend(
            [
                "At least one additional resolved company is required for side-by-side comparison.",
                "For each compared company: snapshot, valuation (P/E), revenue trend, earnings trend, and margin trend.",
            ]
        )

    if "news_context" in actions:
        answer = _synthesize_answer(question, companies, plan_out, results_by_company, unresolved)
        used_sources = ["database"]
    else:
        answer, used_sources = _build_structured_non_news_answer(
            question=question,
            companies=companies,
            payload_by_company=results_by_company,
            unresolved=unresolved,
            mode=response_mode,
        )
    if "general_context" in used_sources:
        citations.add("general_context")
    if missing_for_comparison:
        answer = (
            f"{answer}\n\nWhat is missing to complete comparison:\n"
            + "\n".join([f"- {item}" for item in missing_for_comparison])
        )
    log.info(
        "qa_planned_response",
        extra={
            "tickers": [c.ticker for c in companies],
            "actions": actions,
            "years": years,
            "compare": bool(plan.get("compare")),
        },
    )
    return QAResponse(
        answer=answer,
        citations=sorted(citations),
        data={
            "plan": plan_out,
            "results": results_by_company,
            "queries": query_trace,
            "sources": sorted(citations),
            "source_tags": {
                "what_data_shows": "database",
                "general_context": "general_context" if "general_context" in used_sources else "database",
            },
            "missing_for_comparison": missing_for_comparison,
        },
        trace=trace,
    )


@router.post("", response_model=QAResponse)
def qa_answer(payload: QARequest, db: Session = Depends(get_db)):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    return _answer_question(question, db)
