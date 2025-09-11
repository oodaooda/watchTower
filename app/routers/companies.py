# app/routers/companies.py
from fastapi import APIRouter, Query, Depends, HTTPException, Path
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from app.core.db import get_db
from app.core.models import Company
from app.core.schemas import CompanyOut

router = APIRouter(prefix="/companies", tags=["companies"])

@router.get("")
def list_companies(
    industry: Optional[str] = Query(None),
    sic: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="search ticker or name (ilike)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    base = select(Company).where(Company.is_tracked.is_(True))
    if industry:
        base = base.where(Company.industry_name == industry)
    if sic:
        base = base.where(Company.sic == sic)
    if q:
        like = f"%{q}%"
        base = base.where(or_(Company.ticker.ilike(like), Company.name.ilike(like)))

    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(
        base.order_by(Company.ticker.asc())
            .limit(page_size)
            .offset((page - 1) * page_size)
    ).all()

    return {
        "page": page,
        "page_size": page_size,
        "total": total or 0,
        "items": [
            {
                "id": co.id,
                "ticker": co.ticker,
                "name": co.name,
                "industry": co.industry_name,
                "sic": co.sic,
                "description": co.description,
            }
            for co in rows
        ],
    }


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(
    company_id: int = Path(..., description="Numeric company primary key (companies.id)"),
    db: Session = Depends(get_db),
):
    co = db.get(Company, company_id)
    if not co:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyOut.model_validate(co)