"""
SQLAlchemy ORM models.

Each uploaded image is one sample unit s ∈ Ω in the DISCOUNT framework.
The detector produces g(s) for each image; humans provide f(s) during labeling.
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """A registered user account."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class UploadedImage(Base):
    """A single image file uploaded by the user (= one sample unit s)."""

    __tablename__ = "uploaded_images"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    filename = Column(String, nullable=False)           # unique stored filename
    original_filename = Column(String, nullable=False)  # user's original name
    blob_url = Column(String, nullable=False)           # Azure path or local path
    file_size = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


class CVModel(Base):
    """A .pt YOLO / PyTorch model uploaded by the user."""

    __tablename__ = "cv_models"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name = Column(String, nullable=False)
    # "yolo_v8" | "csrnet"
    model_kind = Column(String, nullable=False, default="yolo_v8")
    filename = Column(String, nullable=False)
    blob_url = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


class JobImage(Base):
    """Many-to-many join: which images belong to a job."""

    __tablename__ = "job_images"
    __table_args__ = (UniqueConstraint("job_id", "image_id"),)

    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    image_id = Column(Integer, ForeignKey("uploaded_images.id"), primary_key=True)


class Job(Base):
    """
    A counting job that ties together a set of images and a detector model.

    Lifecycle: created → processing → ready (→ user labels tiles)
    """

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    model_id = Column(Integer, ForeignKey("cv_models.id"), nullable=False)
    # Job status values: "created" | "processing" | "ready" | "error"
    status = Column(String, default="created", nullable=False)
    epsilon = Column(Float, default=0.5)  # minimum floor for g(s): g(s) = max(raw_count, epsilon)
    num_tiles = Column(Integer, default=100)  # target number of sub-tiles to split each image into
    # YOLO fine-tuning metadata (bbox-driven)
    yolo_finetune_status = Column(String, default="idle", nullable=False)  # idle|queued|running|failed
    yolo_finetune_error = Column(Text, nullable=True)
    yolo_last_trained_bbox_count = Column(Integer, default=0, nullable=False)
    yolo_latest_model_id = Column(Integer, ForeignKey("cv_models.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    error_message = Column(Text, nullable=True)

    model = relationship("CVModel", foreign_keys=[model_id])
    yolo_latest_model = relationship("CVModel", foreign_keys=[yolo_latest_model_id])
    images = relationship("UploadedImage", secondary="job_images")
    tiles = relationship("Tile", back_populates="job", cascade="all, delete-orphan")
    labels = relationship("Label", back_populates="job", cascade="all, delete-orphan")
    estimate_history = relationship(
        "EstimateHistory", back_populates="job", cascade="all, delete-orphan"
    )
    bbox_annotations = relationship(
        "BBoxAnnotation", back_populates="job", cascade="all, delete-orphan"
    )


class Tile(Base):
    """
    Detector output for one image within a job.

    g_count      = detector prediction + epsilon (used in importance weights)
    g_count_raw  = raw detector prediction (number of detected objects)
    detections_json = JSON array of bounding-box objects for the overlay UI
    """

    __tablename__ = "tiles"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    image_id = Column(Integer, ForeignKey("uploaded_images.id"), nullable=False)
    g_count = Column(Float, nullable=False)       # g(s) + epsilon
    g_count_raw = Column(Float, nullable=False)   # raw detection count
    detections_json = Column(Text, default="[]")  # list of {x1,y1,x2,y2,confidence,class_id}
    # Tiling metadata (grid_rows=1, grid_cols=1 means no tiling — full image)
    crop_blob_url = Column(String, nullable=True)   # stored path/URL for the cropped sub-tile image
    tile_row = Column(Integer, default=0)           # 0-based row index in the grid
    tile_col = Column(Integer, default=0)           # 0-based column index in the grid
    grid_rows = Column(Integer, default=1)          # total rows in this job's grid
    grid_cols = Column(Integer, default=1)          # total columns in this job's grid

    job = relationship("Job", back_populates="tiles")
    image = relationship("UploadedImage")
    label = relationship("Label", uselist=False, back_populates="tile")


class Label(Base):
    """
    Human-provided true count f(s) for a tile.
    Each tile can be labeled at most once per job (unique constraint on tile_id).
    """

    __tablename__ = "labels"
    __table_args__ = (UniqueConstraint("tile_id"),)

    id = Column(Integer, primary_key=True, index=True)
    tile_id = Column(Integer, ForeignKey("tiles.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    f_count = Column(Integer, nullable=False)  # human-provided count
    labeled_at = Column(DateTime, default=datetime.utcnow)

    tile = relationship("Tile", back_populates="label")
    job = relationship("Job", back_populates="labels")


class BBoxAnnotation(Base):
    """Human-provided YOLO fine-tuning annotation for one tile."""

    __tablename__ = "bbox_annotations"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    tile_id = Column(Integer, ForeignKey("tiles.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(Integer, default=0, nullable=False)
    # Normalized XYXY coordinates in [0,1] relative to tile image dimensions.
    x1 = Column(Float, nullable=False)
    y1 = Column(Float, nullable=False)
    x2 = Column(Float, nullable=False)
    y2 = Column(Float, nullable=False)
    annotated_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="bbox_annotations")
    tile = relationship("Tile")


class EstimateHistory(Base):
    """
    Snapshot of the k-DISCOUNT estimate after each label is submitted.
    Used to draw the convergence and standard-error charts.
    """

    __tablename__ = "estimate_history"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    n_labeled = Column(Integer, nullable=False)
    estimate = Column(Float, nullable=False)
    ci_lower = Column(Float, nullable=True)
    ci_upper = Column(Float, nullable=True)
    std_error = Column(Float, nullable=True)
    computed_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="estimate_history")
