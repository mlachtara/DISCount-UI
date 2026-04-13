"""
Detector service — runs a YOLO .pt model on each image in a job and stores
the resulting g(s) values (raw detection count + epsilon) in the Tile table.

Supports image tiling: when a job has num_tiles > 1, each source image is split
into a grid of (grid_rows × grid_cols) sub-tiles before inference.  Each sub-tile
becomes an independent Tile row with its own crop stored in local/Azure storage.

Runs synchronously inside a FastAPI BackgroundTask so it does not block the
request thread.  For large jobs you can move this to Azure Functions / Celery.
"""
import io
import json
import logging
import math
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Job, Tile, UploadedImage
from app.services import storage as storage_service

log = logging.getLogger(__name__)
settings = get_settings()


# ── Model cache (avoids reloading for each tile) ──────────────────────────────

_model_cache: dict[str, object] = {}  # blob_url → ultralytics YOLO instance


def _load_yolo(model_blob_url: str):
    """Load and cache a YOLO model from its stored path/URL."""
    if model_blob_url not in _model_cache:
        try:
            from ultralytics import YOLO
        except ImportError as e:
            raise RuntimeError(
                "ultralytics is not installed. Run: pip install ultralytics"
            ) from e

        model_bytes = storage_service.get_file_bytes(model_blob_url)
        with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as tmp:
            tmp.write(model_bytes)
            tmp_path = tmp.name

        _model_cache[model_blob_url] = YOLO(tmp_path)
        Path(tmp_path).unlink(missing_ok=True)

    return _model_cache[model_blob_url]


# ── Tiling helpers ────────────────────────────────────────────────────────────

def _compute_grid(num_tiles: int) -> tuple[int, int]:
    """
    Return (grid_rows, grid_cols) whose product is >= num_tiles, keeping the
    grid as close to square as possible.

    Examples:
        1   → (1, 1)   – no tiling
        4   → (2, 2)
        10  → (3, 4)   – 12 cells, closest to square that fits 10
        1000 → (32, 32) – 1024 cells
    """
    if num_tiles <= 1:
        return (1, 1)
    cols = math.ceil(math.sqrt(num_tiles))
    rows = math.ceil(num_tiles / cols)
    return (rows, cols)


def _crop_tile(image_bytes: bytes, row: int, col: int, grid_rows: int, grid_cols: int) -> bytes:
    """
    Crop a sub-tile from raw image bytes and return it as JPEG bytes.
    Coordinates are computed by evenly dividing the image into the grid.
    """
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    tile_w = w / grid_cols
    tile_h = h / grid_rows
    left   = int(col * tile_w)
    top    = int(row * tile_h)
    right  = int((col + 1) * tile_w)
    bottom = int((row + 1) * tile_h)
    crop = img.crop((left, top, right, bottom))
    buf = io.BytesIO()
    crop.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# ── Inference helpers ─────────────────────────────────────────────────────────

def _run_inference(yolo_model, image_bytes: bytes) -> dict:
    """
    Run YOLO on raw image bytes.
    Returns {"count": int, "detections": [{x1,y1,x2,y2,confidence,class_id}, ...]}
    """
    import numpy as np
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_array = np.array(img)

    results = yolo_model(
        img_array,
        conf=settings.detector_confidence,
        verbose=False,
    )

    detections = []
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
            detections.append(
                {
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "confidence": float(box.conf[0]),
                    "class_id": int(box.cls[0]),
                }
            )

    return {"count": len(detections), "detections": detections}


# ── Main background task ──────────────────────────────────────────────────────

async def run_detector_for_job(job_id: int, db: AsyncSession) -> None:
    """
    Background task: for every image in the job, run the detector and create
    a Tile row with g_count and detections_json.

    Updates job.status to "ready" on success or "error" on failure.
    """
    # Re-fetch inside the background task because the original session is closed.
    # Only need to load the model relationship here; images are queried directly below.
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.model))
    )
    job = result.scalar_one_or_none()
    if job is None:
        log.error("Job %d not found in background task", job_id)
        return

    try:
        yolo = _load_yolo(job.model.blob_url)
        epsilon = job.epsilon

        # Load images via a direct join rather than the ORM relationship to avoid
        # any async lazy-loading issues with secondary many-to-many tables.
        from app.models import JobImage, UploadedImage as _UImg
        images_result = await db.execute(
            select(_UImg)
            .join(JobImage, _UImg.id == JobImage.image_id)
            .where(JobImage.job_id == job_id)
        )
        images = images_result.scalars().all()
        log.info("Job %d: found %d image(s) to process", job_id, len(images))

        num_tiles = job.num_tiles or 1
        grid_rows, grid_cols = _compute_grid(num_tiles)
        tiling = grid_rows > 1 or grid_cols > 1
        tile_count = 0

        for image in images:
            log.debug("Job %d: processing image %d (%s)", job_id, image.id, image.original_filename)
            image_bytes = storage_service.get_file_bytes(image.blob_url)

            if not tiling:
                # ── No tiling: run detector on the full image ──
                inference = _run_inference(yolo, image_bytes)
                g_raw = float(inference["count"])
                g_with_eps = max(g_raw, epsilon)
                tile = Tile(
                    job_id=job_id,
                    image_id=image.id,
                    g_count=g_with_eps,
                    g_count_raw=g_raw,
                    detections_json=json.dumps(inference["detections"]),
                    tile_row=0,
                    tile_col=0,
                    grid_rows=1,
                    grid_cols=1,
                )
                db.add(tile)
                tile_count += 1
            else:
                # ── Tiling: split image into grid, run detector on each crop ──
                stem = Path(image.original_filename).stem
                for row in range(grid_rows):
                    for col in range(grid_cols):
                        crop_bytes = _crop_tile(image_bytes, row, col, grid_rows, grid_cols)
                        inference = _run_inference(yolo, crop_bytes)
                        g_raw = float(inference["count"])
                        g_with_eps = max(g_raw, epsilon)

                        # Save crop to storage so the frontend can display it
                        crop_name = f"{stem}_r{row}_c{col}.jpg"
                        _, crop_blob_url = storage_service.save_upload(
                            crop_bytes, crop_name, "tiles"
                        )

                        tile = Tile(
                            job_id=job_id,
                            image_id=image.id,
                            g_count=g_with_eps,
                            g_count_raw=g_raw,
                            detections_json=json.dumps(inference["detections"]),
                            crop_blob_url=crop_blob_url,
                            tile_row=row,
                            tile_col=col,
                            grid_rows=grid_rows,
                            grid_cols=grid_cols,
                        )
                        db.add(tile)
                        tile_count += 1

        job.status = "ready"
        await db.commit()
        log.info("Job %d finished processing (%d tiles, grid %dx%d)", job_id, tile_count, grid_rows, grid_cols)

    except Exception as exc:
        log.exception("Detector failed for job %d", job_id)
        job.status = "error"
        job.error_message = str(exc)
        await db.commit()


# ── Sampling ──────────────────────────────────────────────────────────────────

def sample_next_tile(unlabeled_tiles: list[dict]) -> dict | None:
    """
    Importance-sample the next tile to show the labeler.
    Probability of each tile ∝ g(s).

    `unlabeled_tiles`: list of {"id": int, "g_count": float}
    Returns one dict, or None if the list is empty.
    """
    if not unlabeled_tiles:
        return None

    import numpy as np

    g = np.array([t["g_count"] for t in unlabeled_tiles], dtype=float)
    total = g.sum()
    probs = g / total if total > 0 else np.ones(len(g)) / len(g)

    idx = int(np.random.choice(len(unlabeled_tiles), p=probs))
    return unlabeled_tiles[idx]
