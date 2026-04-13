"""
Detector service — runs a YOLO .pt model on each image in a job and stores
the resulting g(s) values (raw detection count + epsilon) in the Tile table.

Runs synchronously inside a FastAPI BackgroundTask so it does not block the
request thread.  For large jobs you can move this to Azure Functions / Celery.
"""
import json
import logging
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

        for image in images:
            log.debug("Job %d: processing image %d (%s)", job_id, image.id, image.original_filename)
            image_bytes = storage_service.get_file_bytes(image.blob_url)
            inference = _run_inference(yolo, image_bytes)

            g_raw = float(inference["count"])
            # epsilon is a minimum floor: g(s) = max(raw_count, epsilon)
            # This ensures every tile has a non-zero sampling probability even
            # when the detector finds nothing, without inflating tiles that do
            # have detections.
            g_with_eps = max(g_raw, epsilon)

            tile = Tile(
                job_id=job_id,
                image_id=image.id,
                g_count=g_with_eps,
                g_count_raw=g_raw,
                detections_json=json.dumps(inference["detections"]),
            )
            db.add(tile)

        job.status = "ready"
        await db.commit()
        log.info("Job %d finished processing (%d tiles)", job_id, len(images))

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
