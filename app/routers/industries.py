# app/routers/industries.py
from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.db import get_db
from app.core.models import Company

router = APIRouter(prefix="/industries", tags=["industries"])

class Industry(BaseModel):
    industry: str
    count: int

@router.get("", response_model=List[Industry])
def list_industries(db: Session = Depends(get_db)):
    rows = (
        db.query(Company.industry_name.label("industry"), func.count(Company.id).label("count"))
        .filter(Company.industry_name.isnot(None))
        .group_by(Company.industry_name)
        .order_by(Company.industry_name.asc())
        .all()
    )
    return [Industry(industry=r.industry, count=r.count) for r in rows]
