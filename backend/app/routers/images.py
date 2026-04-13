"""
/api/images — upload and list source images.
"""
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import UploadedImage, User
from app.schemas import ImageOut
from app.services import storage as storage_service

router = APIRouter(prefix="/api/images", tags=["images"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
MAX_FILE_SIZE_MB = 50


@router.post("/upload", response_model=list[ImageOut])
async def upload_images(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload one or more image files (JPEG / PNG / TIFF)."""
    saved: list[ImageOut] = []

    for file in files:
        ext = "." + (file.filename or "").rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}",
            )

        data = await file.read()
        if len(data) > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"File '{file.filename}' exceeds {MAX_FILE_SIZE_MB} MB limit.",
            )

        # Get image dimensions if possible
        width, height = _get_dimensions(data)

        stored_name, blob_url = storage_service.save_upload(data, file.filename or "image", "images")

        img = UploadedImage(
            user_id=current_user.id,
            filename=stored_name,
            original_filename=file.filename or stored_name,
            blob_url=blob_url,
            file_size=len(data),
            width=width,
            height=height,
        )
        db.add(img)
        await db.flush()  # get id without full commit
        saved.append(ImageOut.model_validate(img))

    await db.commit()
    return saved


@router.get("", response_model=list[ImageOut])
async def list_images(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List images uploaded by the current user."""
    result = await db.execute(
        select(UploadedImage)
        .where(UploadedImage.user_id == current_user.id)
        .order_by(UploadedImage.uploaded_at.desc())
    )
    return [ImageOut.model_validate(r) for r in result.scalars()]


@router.get("/{image_id}/file")
async def serve_image(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve the raw image bytes (used when local storage is active)."""
    from fastapi.responses import Response

    result = await db.execute(
        select(UploadedImage).where(
            UploadedImage.id == image_id,
            UploadedImage.user_id == current_user.id,
        )
    )
    img = result.scalar_one_or_none()
    if img is None:
        raise HTTPException(status_code=404, detail="Image not found")

    data = storage_service.get_file_bytes(img.blob_url)
    ext = img.filename.rsplit(".", 1)[-1].lower()
    media_types = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                   "tif": "image/tiff", "tiff": "image/tiff", "bmp": "image/bmp"}
    return Response(content=data, media_type=media_types.get(ext, "application/octet-stream"))


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_dimensions(data: bytes) -> tuple[int | None, int | None]:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        return img.width, img.height
    except Exception:
        return None, None
