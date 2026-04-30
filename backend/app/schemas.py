"""
Pydantic schemas (request / response shapes).
Kept separate from SQLAlchemy models so the API contract is explicit.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        if len(v) > 32:
            raise ValueError("Username must be at most 32 characters")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username may only contain letters, numbers, hyphens, and underscores")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Uploaded Image ────────────────────────────────────────────────────────────

class ImageOut(BaseModel):
    id: int
    original_filename: str
    file_size: Optional[int]
    width: Optional[int]
    height: Optional[int]
    uploaded_at: datetime

    model_config = {"from_attributes": True}


# ── CV Model ──────────────────────────────────────────────────────────────────

class CVModelOut(BaseModel):
    id: int
    name: str
    model_kind: str = "yolo_v8"
    original_filename: str = ""
    filename: str
    file_size: Optional[int]
    uploaded_at: datetime

    model_config = {"from_attributes": True}


# ── Job ───────────────────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    name: str
    description: str = ""
    model_id: int
    image_ids: list[int]
    epsilon: float = 0.5
    num_tiles: int = 100  # target number of sub-tiles to split each image into


class JobOut(BaseModel):
    id: int
    name: str
    description: str
    model_id: int
    status: str
    epsilon: float
    created_at: datetime
    error_message: Optional[str]
    total_tiles: int = 0
    labeled_tiles: int = 0
    yolo_finetune_status: str = "idle"
    yolo_finetune_error: Optional[str] = None
    yolo_last_trained_bbox_count: int = 0
    yolo_latest_model_id: Optional[int] = None

    model_config = {"from_attributes": True}


# ── Tile ──────────────────────────────────────────────────────────────────────

class TileOut(BaseModel):
    id: int
    job_id: int
    image_id: int
    g_count: float
    g_count_raw: float
    detections_json: str
    is_labeled: bool
    image_url: str      # URL of the sub-tile crop (or full image when not tiled)
    tile_row: int = 0   # 0-based row index in the grid
    tile_col: int = 0   # 0-based column index in the grid
    grid_rows: int = 1  # total rows in the grid (1 = not tiled)
    grid_cols: int = 1  # total columns in the grid (1 = not tiled)

    model_config = {"from_attributes": True}


# ── Label ─────────────────────────────────────────────────────────────────────

class LabelCreate(BaseModel):
    tile_id: int
    f_count: int


class LabelOut(BaseModel):
    id: int
    tile_id: int
    job_id: int
    f_count: int
    labeled_at: datetime

    model_config = {"from_attributes": True}


class BBoxIn(BaseModel):
    class_id: int = 0
    x1: float
    y1: float
    x2: float
    y2: float

    @field_validator("x1", "y1", "x2", "y2")
    @classmethod
    def normalized_bounds(cls, v: float) -> float:
        if v < 0 or v > 1:
            raise ValueError("bbox coordinates must be normalized to [0, 1]")
        return v


class BBoxSubmitRequest(BaseModel):
    tile_id: int
    boxes: list[BBoxIn]


class BBoxOut(BaseModel):
    id: int
    job_id: int
    tile_id: int
    class_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    annotated_at: datetime

    model_config = {"from_attributes": True}


class FineTuneStatusOut(BaseModel):
    job_id: int
    model_kind: str
    status: str
    last_trained_bbox_count: int
    current_bbox_tile_count: int
    next_auto_train_at: int
    latest_model_id: Optional[int]
    error: Optional[str]


# ── Estimate ──────────────────────────────────────────────────────────────────

class EstimateOut(BaseModel):
    job_id: int
    n_labeled: int
    total_tiles: int
    estimate: float
    ci_lower: Optional[float]
    ci_upper: Optional[float]
    std_error: Optional[float]
    g_total: float  # G(Ω) — total detector count over all tiles


class EstimateHistoryPoint(BaseModel):
    n_labeled: int
    estimate: float
    ci_lower: Optional[float]
    ci_upper: Optional[float]
    std_error: Optional[float]
    computed_at: datetime

    model_config = {"from_attributes": True}
