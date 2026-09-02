"""Serve listing photos from MinIO or Autoplius via this host only.

Russian clients cannot rely on autoplius-img.dgn.lt. The VM fetches once,
optionally resizes for list cards, and caches on disk.
"""

from __future__ import annotations

import hashlib
import os
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

from botocore.exceptions import BotoCoreError, ClientError
from flask import Response, abort, send_file
from PIL import Image, ImageOps, UnidentifiedImageError

from scraper.config import Settings
from scraper.s3_storage import get_s3_client

ALLOWED_WIDTHS = frozenset({160, 240, 320, 480, 640})
LIST_THUMB_WIDTH = 320
CACHE_CONTROL = "public, max-age=604800, immutable"


def cache_dir() -> Path:
    raw = os.environ.get("MEDIA_CACHE_DIR", "").strip()
    if raw:
        path = Path(raw)
    else:
        data_dir = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
        path = data_dir.parent / "media-cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def parse_width(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        width = int(raw)
    except (TypeError, ValueError):
        return None
    if width in ALLOWED_WIDTHS:
        return width
    return None


def _cache_file(kind: str, ident: str, width: int | None) -> Path:
    digest = hashlib.sha1(f"{kind}:{ident}".encode("utf-8")).hexdigest()
    suffix = f"w{width}.webp" if width else "orig.bin"
    folder = cache_dir() / kind / digest[:2]
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{digest}.{suffix}"


def _image_response(data: bytes, content_type: str) -> Response:
    return Response(
        data,
        mimetype=content_type,
        headers={"Cache-Control": CACHE_CONTROL},
    )


def _resize_webp(data: bytes, width: int) -> bytes:
    image = Image.open(BytesIO(data))
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")
    if image.width > width:
        height = max(1, int(round(image.height * (width / image.width))))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    out = BytesIO()
    image.save(out, format="WEBP", quality=72, method=4)
    return out.getvalue()


def _load_s3(settings: Settings, key: str) -> tuple[bytes, str]:
    try:
        response = get_s3_client(settings).get_object(Bucket=settings.s3_bucket, Key=key)
    except (ClientError, BotoCoreError):
        abort(404, "Object not found")
    body = response.get("Body")
    if body is None:
        abort(404, "Object body missing")
    data = body.read()
    content_type = response.get("ContentType") or "application/octet-stream"
    if not data:
        abort(404, "Empty object")
    return data, content_type


def _load_remote(url: str, referer: str, timeout: int = 20) -> tuple[bytes, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AutopliusScraper/1.0)",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": f"{referer.rstrip('/')}/",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            data = response.read()
            content_type = (response.headers.get("Content-Type") or "image/jpeg").split(";")[0]
    except Exception:
        abort(502, "Failed to fetch image")
    if not data:
        abort(502, "Empty image response")
    return data, content_type


def _serve_cached_or_build(
    *,
    kind: str,
    ident: str,
    width: int | None,
    loader,
) -> Response:
    path = _cache_file(kind, ident, width)
    if width and path.is_file() and path.stat().st_size > 0:
        return send_file(
            path,
            mimetype="image/webp",
            max_age=604800,
            conditional=True,
        )

    data, content_type = loader()
    if width:
        try:
            data = _resize_webp(data, width)
            content_type = "image/webp"
        except (UnidentifiedImageError, OSError, ValueError):
            abort(502, "Invalid image")
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        return _image_response(data, content_type)

    return _image_response(data, content_type)


def serve_s3_object(settings: Settings, key: str, width: int | None) -> Response:
    ident = key
    return _serve_cached_or_build(
        kind="s3",
        ident=ident,
        width=width,
        loader=lambda: _load_s3(settings, key),
    )


def serve_s3_object_from_cache(key: str, width: int | None) -> Response:
    """Serve a previously cached S3 object when remote storage is unavailable."""
    if width:
        thumb_path = _cache_file("s3", key, width)
        if thumb_path.is_file() and thumb_path.stat().st_size > 0:
            return send_file(
                thumb_path,
                mimetype="image/webp",
                max_age=604800,
                conditional=True,
            )

    orig_path = _cache_file("s3", key, None)
    if orig_path.is_file() and orig_path.stat().st_size > 0:
        data = orig_path.read_bytes()
        content_type = "application/octet-stream"
        if width:
            try:
                data = _resize_webp(data, width)
                content_type = "image/webp"
            except (UnidentifiedImageError, OSError, ValueError):
                abort(502, "Invalid image")
        return _image_response(data, content_type)

    abort(404, "Object not found")


def serve_remote_photo(url: str, referer: str, width: int | None) -> Response:
    return _serve_cached_or_build(
        kind="cdn",
        ident=url,
        width=width,
        loader=lambda: _load_remote(url, referer),
    )
