"""
FastAPI application entry point.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import create_all_tables
from app.routers import cv_models, estimates, images, jobs, labels

settings = get_settings()

app = FastAPI(
    title="DISCOUNT UI",
    description=(
        "Web interface for the DISCOUNT detector-based importance-sampling "
        "framework. See arXiv:2306.03151 for the underlying method."
    ),
    version="0.1.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(images.router)
app.include_router(cv_models.router)
app.include_router(jobs.router)
app.include_router(labels.router)
app.include_router(estimates.router)

# ── Static files (local storage only) ────────────────────────────────────────
if not settings.use_azure_storage:
    local_path = Path(settings.local_storage_path)
    local_path.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(local_path)), name="static")

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    await create_all_tables()


@app.get("/api/health")
async def health():
    return {"status": "ok"}
