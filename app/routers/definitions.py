"""Definitions (glossary) router

Serves Markdown explanations for financial terms/metrics
(e.g., Piotroski F, Altman Z, ROIC, FCF, CAGR). The frontend can render
`body_md` directly.

Design:
- `GET /definitions` returns all entries.
- `GET /definitions/{key}` returns a single entry (404 if missing).
- Content is stored in the `definitions` table and seeded via an ops script.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import Definition
from app.core.schemas import DefinitionOut

router = APIRouter()


@router.get("", response_model=List[DefinitionOut])
def list_definitions(db: Session = Depends(get_db)):
    """Return all glossary entries (Markdown bodies)."""
    rows = db.scalars(select(Definition)).all()
    return [DefinitionOut(key=r.key, title=r.title, body_md=r.body_md) for r in rows]


@router.get("/{key}", response_model=DefinitionOut)
def get_definition(
    key: str = Path(..., description="Definition key, e.g. 'piotroski_f'"),
    db: Session = Depends(get_db),
):
    """Return a single glossary entry by key (404 if not found)."""
    row = db.get(Definition, key)
    if not row:
        raise HTTPException(status_code=404, detail="Definition not found")
    return DefinitionOut(key=row.key, title=row.title, body_md=row.body_md)
