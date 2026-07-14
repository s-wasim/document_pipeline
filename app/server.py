"""FastAPI monolith replacing the Streamlit UI.

Serves the dc-runtime frontend as static files and exposes /api/* routers that
call the existing backend functions unchanged. Runs on port 8501 (same as the
old Streamlit app and docker-compose mapping).
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.api.health import router as health_router
from app.api.documents import router as documents_router
from app.api.records import router as records_router
from app.api.actions import router as actions_router

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.dc.html"

app = FastAPI(title="Document Pipeline")


@app.on_event("startup")
def _startup():
    os.makedirs("data/docs", exist_ok=True)
    os.makedirs("data/previews", exist_ok=True)
    init_db()


# API routers are registered before the catch-all static mount so /api/* wins.
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(records_router)
app.include_router(actions_router)


@app.get("/")
def index():
    return FileResponse(str(INDEX_FILE))


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
