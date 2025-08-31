from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import Company
from app.core.schemas import CompanyOut

router = APIRouter()


@router.get("", response_model=List[CompanyOut])
def list_companies(
    q: Optional[str] = Query(default=None, description="Search by ticker or name"),
    industry: Optional[str] = Query(default=None, description="Exact industry match"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """List/search tracked companies.

    Filters:
      - q: substring match on ticker OR name
      - industry: exact match on `industry_name`
    Pagination via limit/offset.
    """
    stmt = select(Company).where(Company.is_tracked == True)

    if q:
        like = f"%{q}%"
        stmt = stmt.where((Company.ticker.ilike(like)) | (Company.name.ilike(like)))

    if industry:
        stmt = stmt.where(Company.industry_name == industry)

    stmt = stmt.order_by(Company.ticker).limit(limit).offset(offset)
    rows = db.scalars(stmt).all()
    return rows
