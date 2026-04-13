"""
/api/models — upload and list computer-vision (.pt) models.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import CVModel, User
from app.schemas import CVModelOut
from app.services import storage as storage_service

router = APIRouter(prefix="/api/models", tags=["models"])

MAX_MODEL_SIZE_MB = 500


@router.post("/upload", response_model=CVModelOut)
async def upload_model(
    name: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a YOLO .pt model file."""
    filename = file.filename or "model.pt"
    if not filename.endswith(".pt"):
        raise HTTPException(status_code=422, detail="Only .pt model files are supported.")

    data = await file.read()
    if len(data) > MAX_MODEL_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail=f"Model file exceeds {MAX_MODEL_SIZE_MB} MB limit."
        )

    stored_name, blob_url = storage_service.save_upload(data, filename, "models")

    model = CVModel(
        user_id=current_user.id,
        name=name,
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
    """List models uploaded by the current user."""
    result = await db.execute(
        select(CVModel)
        .where(CVModel.user_id == current_user.id)
        .order_by(CVModel.uploaded_at.desc())
    )
    return [CVModelOut.model_validate(m) for m in result.scalars()]


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
    return CVModelOut.model_validate(model)
