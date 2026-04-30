"""
/api/models — list detector choices and upload custom detector weights.
"""
import tempfile
from pathlib import Path

import torch
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import CVModel, User
from app.schemas import CVModelOut
from app.services import storage as storage_service

router = APIRouter(prefix="/api/models", tags=["models"])
settings = get_settings()
_BACKEND_DIR = Path(__file__).resolve().parents[2]

MAX_MODEL_SIZE_MB = 500
MODEL_KIND_YOLO = "yolo_v8"
MODEL_KIND_CSRNET = "csrnet"
MODEL_KIND_FASTER_RCNN = "faster_rcnn"
MODEL_KIND_AUTO = "auto"
YOLOV8N_FALLBACK_SIZE_BYTES = 6_549_796
FASTER_RCNN_FALLBACK_SIZE_BYTES = 167_104_063
BUILTIN_DETECTORS = [
    {
        "name": "YOLO-v8 (built-in)",
        "kind": MODEL_KIND_YOLO,
        "filename": "__builtin_yolov8__.pt",
        "blob_url": "builtin://yolo_v8",
    },
    {
        "name": "CSRNet (built-in)",
        "kind": MODEL_KIND_CSRNET,
        "filename": "__builtin_csrnet__.pth",
        "blob_url": "builtin://csrnet",
    },
    {
        "name": "Faster R-CNN (built-in)",
        "kind": MODEL_KIND_FASTER_RCNN,
        "filename": "__builtin_faster_rcnn__.pt",
        "blob_url": "builtin://faster_rcnn",
    },
]


async def _ensure_builtin_models(db: AsyncSession, user_id: int) -> None:
    for detector in BUILTIN_DETECTORS:
        existing = await db.execute(
            select(CVModel).where(
                CVModel.user_id == user_id,
                CVModel.filename == detector["filename"],
                CVModel.blob_url == detector["blob_url"],
            )
        )
        if existing.scalar_one_or_none() is None:
            db.add(
                CVModel(
                    user_id=user_id,
                    name=detector["name"],
                    model_kind=detector["kind"],
                    filename=detector["filename"],
                    blob_url=detector["blob_url"],
                    file_size=None,
                )
            )
    await db.commit()


def _resolve_csrnet_weights_path() -> Path | None:
    raw = (settings.csrnet_default_weights_path or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (_BACKEND_DIR / path).resolve()
    return path


def _builtin_file_size_bytes(model: CVModel) -> int | None:
    if model.blob_url == "builtin://csrnet":
        csr_path = _resolve_csrnet_weights_path()
        if csr_path and csr_path.exists():
            return csr_path.stat().st_size
        return None
    if model.blob_url == "builtin://yolo_v8":
        candidates = [
            Path("yolov8n.pt"),  # common local cache location when launched from repo root
            _BACKEND_DIR / "yolov8n.pt",
            Path.home() / ".cache" / "ultralytics" / "yolov8n.pt",
        ]
        for candidate in candidates:
            try:
                if candidate.exists():
                    return candidate.stat().st_size
            except OSError:
                pass
        return YOLOV8N_FALLBACK_SIZE_BYTES
    if model.blob_url == "builtin://faster_rcnn":
        candidates = [
            Path("fasterrcnn_resnet50_fpn_coco-258fb6c6.pth"),
            _BACKEND_DIR / "fasterrcnn_resnet50_fpn_coco-258fb6c6.pth",
            Path.home() / ".cache" / "torch" / "hub" / "checkpoints" / "fasterrcnn_resnet50_fpn_coco-258fb6c6.pth",
        ]
        for candidate in candidates:
            try:
                if candidate.exists():
                    return candidate.stat().st_size
            except OSError:
                pass
        return FASTER_RCNN_FALLBACK_SIZE_BYTES
    return model.file_size


def _looks_like_csrnet_state_dict(payload: dict) -> bool:
    # CSRNet checkpoints usually expose state_dict keys like:
    # frontend.*, backend.*, output_layer.* (optionally prefixed with module.)
    keys = payload.keys()
    return any(
        k.startswith("frontend.")
        or k.startswith("backend.")
        or k.startswith("output_layer.")
        or k.startswith("module.frontend.")
        or k.startswith("module.backend.")
        or k.startswith("module.output_layer.")
        for k in keys
    )


def _infer_model_kind(filename: str, data: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pth") or lower.endswith(".pth.tar") or lower.endswith(".tar"):
        return MODEL_KIND_CSRNET

    if lower.endswith(".pt"):
        # .pt can be either YOLO or generic torch checkpoint; inspect payload.
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            payload = torch.load(tmp_path, map_location="cpu", weights_only=False)
        except Exception:
            # If inspection fails, default to YOLO for .pt (most common case).
            return MODEL_KIND_YOLO
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

        if isinstance(payload, dict):
            state_dict = payload.get("state_dict") if isinstance(payload.get("state_dict"), dict) else payload
            if isinstance(state_dict, dict) and _looks_like_csrnet_state_dict(state_dict):
                return MODEL_KIND_CSRNET
            if "model" in payload or "ema" in payload or "train_args" in payload:
                return MODEL_KIND_YOLO
        return MODEL_KIND_YOLO

    raise HTTPException(status_code=422, detail="Unsupported model file extension. Use .pt, .pth, .pth.tar, or .tar.")


@router.post("/upload", response_model=CVModelOut)
async def upload_model(
    name: str = Form(...),
    model_kind: str = Form(MODEL_KIND_AUTO),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a detector weights file with auto-detection or manual override."""
    if model_kind not in {MODEL_KIND_AUTO, MODEL_KIND_YOLO, MODEL_KIND_CSRNET, MODEL_KIND_FASTER_RCNN}:
        raise HTTPException(
            status_code=422,
            detail="model_kind must be 'auto', 'yolo_v8', 'csrnet', or 'faster_rcnn'.",
        )

    filename = file.filename or "model.pt"
    lower = filename.lower()
    if not (lower.endswith(".pt") or lower.endswith(".pth") or lower.endswith(".pth.tar") or lower.endswith(".tar")):
        raise HTTPException(
            status_code=422,
            detail="Only .pt, .pth, .pth.tar, or .tar model files are supported.",
        )

    data = await file.read()
    if len(data) > MAX_MODEL_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail=f"Model file exceeds {MAX_MODEL_SIZE_MB} MB limit."
        )

    resolved_kind = _infer_model_kind(filename, data) if model_kind == MODEL_KIND_AUTO else model_kind
    if resolved_kind in {MODEL_KIND_YOLO, MODEL_KIND_FASTER_RCNN} and not lower.endswith(".pt"):
        raise HTTPException(status_code=422, detail="YOLOv8 and Faster R-CNN uploads must use a .pt file.")

    stored_name, blob_url = storage_service.save_upload(data, filename, "models")

    model = CVModel(
        user_id=current_user.id,
        name=name,
        model_kind=resolved_kind,
        filename=stored_name,
        blob_url=blob_url,
        file_size=len(data),
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)

    out = CVModelOut.model_validate(model)
    out.original_filename = filename
    return out


@router.get("", response_model=list[CVModelOut])
async def list_models(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List detector options for the current user (built-ins + uploaded)."""
    await _ensure_builtin_models(db, current_user.id)
    result = await db.execute(
        select(CVModel)
        .where(CVModel.user_id == current_user.id)
        .order_by(CVModel.uploaded_at.desc())
    )
    out = []
    for model in result.scalars():
        row = CVModelOut.model_validate(model)
        row.file_size = _builtin_file_size_bytes(model)
        out.append(row)
    return out


@router.get("/{model_id}", response_model=CVModelOut)
async def get_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CVModel).where(CVModel.id == model_id, CVModel.user_id == current_user.id)
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    out = CVModelOut.model_validate(model)
    out.file_size = _builtin_file_size_bytes(model)
    return out
