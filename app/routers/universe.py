from __future__ import annotations

import requests
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
import time

from app.core.config import settings
from app.core.db import get_db
from app.core.models import Company, FinancialAnnual, FinancialQuarterly
from ops.run_backfill import backfill_company
from ops.run_backfill_quarterly import backfill_company_quarterly
from fastapi import Depends


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_TICKERS_EXCH_URL = "https://www.sec.gov/files/company_tickers_exchange.json"

router = APIRouter(prefix="/universe", tags=["universe"])
logger = logging.getLogger(__name__)


class PreviewResponse(BaseModel):
    as_of: Optional[str] = None
    new: List[Dict] = []
    updated: List[Dict] = []
    existing: int = 0


class ApplyRequest(BaseModel):
    tickers: List[str]
    update_names: bool = False
    track_new: bool = False
    track_retickered: bool = False


class BackfillRequest(BaseModel):
    tickers: List[str]
    annual: bool = True
    quarterly: bool = True
    only_if_missing: bool = True  # if True, skip when data already exists
    sleep_seconds: float = 0.5


@router.get("/sec/preview", response_model=PreviewResponse)
def sec_preview(db: Session = Depends(get_db)):
    sec_data = _fetch_sec_tickers()

    tickers_map = {row["ticker"].upper(): row for row in sec_data}

    existing_rows = db.execute(select(Company)).scalars().all()
    existing_map = {c.ticker.upper(): c for c in existing_rows if c.ticker}

    new_rows = []
    updated_rows = []
    for tkr, row in tickers_map.items():
        existing = existing_map.get(tkr)
        if not existing:
            new_rows.append(row)
        else:
            name_differs = row.get("name") and row.get("name") != existing.name
            cik_differs = row.get("cik") and int(row["cik"]) != int(existing.cik or 0)
            if name_differs or cik_differs:
                updated_rows.append(
                    {
                        "ticker": tkr,
                        "name_old": existing.name,
                        "name_new": row.get("name"),
                        "cik_old": existing.cik,
                        "cik_new": row.get("cik"),
                    }
                )

    return PreviewResponse(
        as_of=None,
        new=new_rows,
        updated=updated_rows,
        existing=len(existing_map),
    )


@router.post("/sec/apply")
def sec_apply(payload: ApplyRequest, db: Session = Depends(get_db)):
    sec_data = _fetch_sec_tickers()
    tickers_map = {row["ticker"].upper(): row for row in sec_data}
    existing_rows = db.execute(select(Company)).scalars().all()
    existing_map = {c.ticker.upper(): c for c in existing_rows if c.ticker}
    # Map CIK -> Company (may have null ticker)
    existing_by_cik: Dict[str, Company] = {}
    for co in existing_rows:
        if co.cik:
            existing_by_cik[str(co.cik)] = co

    inserted = 0
    updated = 0
    retickered = 0
    skipped_conflicts: List[Dict[str, str]] = []
    for t in payload.tickers:
        t_upper = t.upper()
        row = tickers_map.get(t_upper)
        if not row:
            continue
        row_cik = row.get("cik")
        row_cik_norm = str(row_cik) if row_cik is not None else None
        existing = existing_map.get(t_upper)
        cic_owner = existing_by_cik.get(row_cik_norm) if row_cik_norm else None

        # Case: ticker not in DB, but CIK already exists on another row -> treat as reticker/rename
        if not existing and cic_owner and (cic_owner.ticker or "").upper() != t_upper:
            old_ticker = (cic_owner.ticker or "").upper()
            if old_ticker in existing_map:
                existing_map.pop(old_ticker)
            cic_owner.ticker = t_upper
            if row.get("name"):
                cic_owner.name = row.get("name")
            if row.get("exchange"):
                cic_owner.exchange = row.get("exchange")
            if payload.track_retickered:
                cic_owner.is_tracked = True
            existing_map[t_upper] = cic_owner
            retickered += 1
            # Update owner map to reflect new ticker association
            if row_cik_norm:
                existing_by_cik[row_cik_norm] = cic_owner
            continue

        if not existing:
            co = Company(
                ticker=t_upper,
                name=row.get("name"),
                cik=row.get("cik"),
                exchange=row.get("exchange"),
                is_tracked=payload.track_new,
            )
            db.add(co)
            inserted += 1
            if row_cik_norm:
                existing_by_cik[row_cik_norm] = co
                existing_map[t_upper] = co
        elif payload.update_names:
            changed = False
            if row.get("name") and row.get("name") != existing.name:
                existing.name = row.get("name")
                changed = True
            if row_cik_norm and row_cik_norm != str(existing.cik or ""):
                # ensure no collision before updating
                owner = existing_by_cik.get(row_cik_norm)
                if owner and owner is not existing:
                    skipped_conflicts.append(
                        {
                            "ticker": t_upper,
                            "cik": row_cik_norm,
                            "claimed_by": owner.ticker,
                        }
                    )
                    continue
                existing.cik = row.get("cik")
                existing_by_cik[row_cik_norm] = existing
                changed = True
            if changed:
                updated += 1
    db.commit()
    return {
        "inserted": inserted,
        "updated": updated,
        "retickered": retickered,
        "skipped_conflicts": len(skipped_conflicts),
        "conflicts": skipped_conflicts,
    }


@router.post("/sec/backfill")
def sec_backfill(payload: BackfillRequest, db: Session = Depends(get_db)):
    results = []
    tickers = [t.upper() for t in payload.tickers or []]

    for idx, t in enumerate(tickers):
        item = {"ticker": t, "annual_ran": False, "quarterly_ran": False, "skipped": False, "error": None}
        co = db.execute(select(Company).where(Company.ticker == t)).scalar_one_or_none()
        if not co:
            item["error"] = "Not found"
            results.append(item)
            continue
        try:
            need_annual = False
            need_quarterly = False
            if payload.annual:
                annual_count = db.execute(
                    select(func.count()).select_from(FinancialAnnual).where(FinancialAnnual.company_id == co.id)
                ).scalar_one()
                need_annual = annual_count == 0 if payload.only_if_missing else True
            if payload.quarterly:
                quarterly_count = db.execute(
                    select(func.count()).select_from(FinancialQuarterly).where(FinancialQuarterly.company_id == co.id)
                ).scalar_one()
                need_quarterly = quarterly_count == 0 if payload.only_if_missing else True

            if not need_annual and not need_quarterly:
                item["skipped"] = True
                results.append(item)
                continue

            if need_annual:
                backfill_company(db, co, debug=False)
                item["annual_ran"] = True

            if need_quarterly:
                backfill_company_quarterly(db, co, debug=False)
                item["quarterly_ran"] = True

        except Exception as exc:  # noqa: BLE001
            item["error"] = str(exc)
        results.append(item)

        # gentle throttle between companies
        if idx < len(tickers) - 1 and payload.sleep_seconds and payload.sleep_seconds > 0:
            time.sleep(payload.sleep_seconds)

    return {"results": results}


def _fetch_sec_tickers() -> List[Dict[str, str]]:
    headers = {"User-Agent": getattr(settings, "sec_user_agent", "watchTower/0.1")}
    try:
        base_resp = requests.get(SEC_TICKERS_URL, headers=headers, timeout=15)
        if not base_resp.ok:
            snippet = (base_resp.text or "").strip()[:200]
            detail = f"SEC tickers fetch failed ({base_resp.status_code})"
            if snippet:
                detail = f"{detail}: {snippet}"
            logger.warning("SEC tickers fetch failed: %s", detail)
            raise HTTPException(status_code=503, detail=detail)
        base = base_resp.json()
        exch = {}
        try:
            exch_resp = requests.get(SEC_TICKERS_EXCH_URL, headers=headers, timeout=15)
            if exch_resp.ok:
                exch = exch_resp.json()
            else:
                logger.warning(
                    "SEC exchange fetch failed (%s): %s",
                    exch_resp.status_code,
                    (exch_resp.text or "").strip()[:200],
                )
        except Exception:
            exch = {}
        out: List[Dict[str, str]] = []
        # Build a quick lookup for exchange data (ticker -> exchange)
        exch_map: Dict[str, Optional[str]] = {}
        try:
            if isinstance(exch, dict):
                # SEC sometimes returns a dict keyed by integer-like strings
                for _, erow in exch.items():
                    if isinstance(erow, dict):
                        t = erow.get("ticker")
                        if t:
                            exch_map[t] = erow.get("exchange")
            elif isinstance(exch, list):
                for erow in exch:
                    if isinstance(erow, dict):
                        t = erow.get("ticker")
                        if t:
                            exch_map[t] = erow.get("exchange")
        except Exception:
            logger.warning("Failed to parse SEC exchange JSON")

        for _, row in base.items():
            ticker = row.get("ticker")
            name = row.get("title")
            cik = row.get("cik_str")
            exchange = exch_map.get(ticker)
            out.append({"ticker": ticker, "name": name, "cik": cik, "exchange": exchange})
        return out
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("SEC tickers fetch error", exc_info=True)
        raise HTTPException(status_code=503, detail=str(exc) or "Unable to fetch SEC tickers")
