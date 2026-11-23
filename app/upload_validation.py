"""Small, bounded uploads and validated image magic bytes.
Never trust a browser-provided MIME type alone.
"""
from __future__ import annotations

from fastapi import HTTPException, UploadFile

MAX_WAV_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 6 * 1024 * 1024


async def limited_upload(upload: UploadFile, limit: int, label: str) -> bytes:
    # Read only limit+1 bytes: the client cannot force unbounded RAM consumption.
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"{label} vượt quá dung lượng cho phép.")
    if not data:
        raise HTTPException(status_code=400, detail=f"{label} trống. Vui lòng chọn tệp hợp lệ.")
    return data


def image_mime(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise HTTPException(status_code=400, detail="Hình ảnh phải là tệp JPEG, PNG hoặc WebP hợp lệ.")
