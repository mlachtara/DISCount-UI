"""
FastAPI application entry point.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import create_all_tables, engine
from app.routers import cv_models, estimates, images, jobs, labels
from app.routers import auth as auth_router

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
app.include_router(auth_router.router)
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

async def _run_migrations() -> None:
    """
    Safely apply schema migrations that create_all() can't handle
    (adding columns to existing tables).  Each statement is wrapped in its
    own try/except so a column that already exists doesn't abort the rest.
    """
    new_columns = [
        # Tiling columns
        "ALTER TABLE jobs  ADD COLUMN num_tiles   INTEGER DEFAULT 1",
        "ALTER TABLE tiles ADD COLUMN crop_blob_url VARCHAR",
        "ALTER TABLE tiles ADD COLUMN tile_row    INTEGER DEFAULT 0",
        "ALTER TABLE tiles ADD COLUMN tile_col    INTEGER DEFAULT 0",
        "ALTER TABLE tiles ADD COLUMN grid_rows   INTEGER DEFAULT 1",
        "ALTER TABLE tiles ADD COLUMN grid_cols   INTEGER DEFAULT 1",
        # Auth columns
        "ALTER TABLE uploaded_images ADD COLUMN user_id INTEGER REFERENCES users(id)",
        "ALTER TABLE cv_models       ADD COLUMN user_id INTEGER REFERENCES users(id)",
        "ALTER TABLE jobs            ADD COLUMN user_id INTEGER REFERENCES users(id)",
        # Detector family metadata
        "ALTER TABLE cv_models       ADD COLUMN model_kind VARCHAR DEFAULT 'yolo_v8'",
        # YOLO fine-tuning metadata
        "ALTER TABLE jobs            ADD COLUMN yolo_finetune_status VARCHAR DEFAULT 'idle'",
        "ALTER TABLE jobs            ADD COLUMN yolo_finetune_error TEXT",
        "ALTER TABLE jobs            ADD COLUMN yolo_last_trained_bbox_count INTEGER DEFAULT 0",
        "ALTER TABLE jobs            ADD COLUMN yolo_latest_model_id INTEGER REFERENCES cv_models(id)",
    ]
    async with engine.begin() as conn:
        for stmt in new_columns:
            try:
                await conn.execute(__import__("sqlalchemy").text(stmt))
            except Exception:
                pass  # column already exists — skip
        # New table for bbox annotations used by auto fine-tuning.
        try:
            await conn.execute(
                __import__("sqlalchemy").text(
                    """
                    CREATE TABLE IF NOT EXISTS bbox_annotations (
                        id INTEGER PRIMARY KEY,
                        job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                        tile_id INTEGER NOT NULL REFERENCES tiles(id) ON DELETE CASCADE,
                        class_id INTEGER NOT NULL DEFAULT 0,
                        x1 FLOAT NOT NULL,
                        y1 FLOAT NOT NULL,
                        x2 FLOAT NOT NULL,
                        y2 FLOAT NOT NULL,
                        annotated_at DATETIME
                    )
                    """
                )
            )
            await conn.execute(
                __import__("sqlalchemy").text(
                    "CREATE INDEX IF NOT EXISTS ix_bbox_annotations_job_id ON bbox_annotations(job_id)"
                )
            )
            await conn.execute(
                __import__("sqlalchemy").text(
                    "CREATE INDEX IF NOT EXISTS ix_bbox_annotations_tile_id ON bbox_annotations(tile_id)"
                )
            )
        except Exception:
            pass


@app.on_event("startup")
async def on_startup():
    await create_all_tables()
    await _run_migrations()


@app.get("/api/health")
async def health():
    return {"status": "ok"}
