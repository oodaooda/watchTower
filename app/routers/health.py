from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db

router = APIRouter()


@router.get("")
def healthcheck(db: Session = Depends(get_db)):
    """Simple service + DB health status.

    Returns:
        { "ok": true, "db": true|false }
    """
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"ok": True, "db": db_ok}
