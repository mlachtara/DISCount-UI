"""
Storage service abstraction.

When USE_AZURE_STORAGE=false (default for local dev) files are saved under
LOCAL_STORAGE_PATH on disk and served via a static-file mount on the backend.

When USE_AZURE_STORAGE=true files go to Azure Blob Storage and the returned
URLs are Azure SAS-less public URLs (or you can add SAS generation here).
"""
import os
import uuid
from pathlib import Path

from app.config import get_settings

settings = get_settings()


def _local_storage_path() -> Path:
    path = Path(settings.local_storage_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _make_unique_filename(original: str) -> str:
    """Prepend a UUID so filenames never collide."""
    ext = Path(original).suffix
    return f"{uuid.uuid4().hex}{ext}"


# ── Public API ────────────────────────────────────────────────────────────────

def save_upload(file_data: bytes, original_filename: str, folder: str) -> tuple[str, str]:
    """
    Persist uploaded bytes and return (stored_filename, blob_url_or_path).

    `folder` is a sub-path like "images" or "models".
    `blob_url_or_path` is what gets stored in the DB blob_url column.
    """
    stored_filename = _make_unique_filename(original_filename)

    if settings.use_azure_storage:
        return _save_azure(file_data, stored_filename, folder)
    else:
        return _save_local(file_data, stored_filename, folder)


def get_file_bytes(blob_url: str) -> bytes:
    """
    Retrieve raw file bytes from storage.
    `blob_url` is exactly what was returned by save_upload.
    """
    if settings.use_azure_storage:
        return _get_azure(blob_url)
    else:
        return _get_local(blob_url)


def get_serving_url(blob_url: str) -> str:
    """
    Return the URL the frontend should use to load the file.

    Local: relative URL served by the /static FastAPI mount.
    Azure: the blob_url is already a public HTTPS URL.
    """
    if settings.use_azure_storage:
        return blob_url  # already a public URL
    else:
        # blob_url is an absolute local path; convert to a /static/... URL
        local_root = str(_local_storage_path().resolve())
        rel = blob_url.replace(local_root, "").replace("\\", "/").lstrip("/")
        return f"/static/{rel}"


# ── Local backend ─────────────────────────────────────────────────────────────

def _save_local(file_data: bytes, stored_filename: str, folder: str) -> tuple[str, str]:
    dest_dir = _local_storage_path() / folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / stored_filename
    dest_path.write_bytes(file_data)
    return stored_filename, str(dest_path.resolve())


def _get_local(blob_url: str) -> bytes:
    return Path(blob_url).read_bytes()


# ── Azure backend ─────────────────────────────────────────────────────────────

def _save_azure(file_data: bytes, stored_filename: str, folder: str) -> tuple[str, str]:
    from azure.storage.blob import BlobServiceClient

    client = BlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    )
    container = client.get_container_client(settings.azure_storage_container_name)

    blob_name = f"{folder}/{stored_filename}"
    container.upload_blob(blob_name, file_data, overwrite=True)

    # Build public URL (works if the container has public read access)
    account_name = client.account_name
    url = (
        f"https://{account_name}.blob.core.windows.net"
        f"/{settings.azure_storage_container_name}/{blob_name}"
    )
    return stored_filename, url


def _get_azure(blob_url: str) -> bytes:
    from azure.storage.blob import BlobClient

    client = BlobClient.from_blob_url(
        blob_url,
        connection_string=settings.azure_storage_connection_string,
    )
    return client.download_blob().readall()
