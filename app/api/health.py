from fastapi import APIRouter
from sqlalchemy import text

from app.db import get_session

router = APIRouter()


@router.get("/api/health")
def health():
    """Real DB connectivity check backing the frontend health pill."""
    session = get_session()
    try:
        session.execute(text("SELECT 1"))
        return {"db_ok": True, "db_error": None}
    except Exception as e:  # pragma: no cover - exercised only when DB is down
        return {"db_ok": False, "db_error": str(e)}
    finally:
        session.close()
