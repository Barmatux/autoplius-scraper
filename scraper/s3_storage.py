from __future__ import annotations

from urllib.parse import quote, unquote

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from scraper.config import Settings

_client = None
_client_key: tuple[str, str, str, str] | None = None


def get_s3_client(settings: Settings):
    global _client, _client_key
    key = (
        settings.s3_endpoint_url,
        settings.s3_access_key,
        settings.s3_secret_key,
        settings.s3_region,
    )
    if _client is None or _client_key != key:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4"),
        )
        _client_key = key
    return _client


def ensure_bucket_exists(settings: Settings) -> None:
    if not settings.s3_enabled:
        return
    client = get_s3_client(settings)
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
        return
    except ClientError:
        pass
    except BotoCoreError:
        return

    try:
        client.create_bucket(Bucket=settings.s3_bucket)
    except (ClientError, BotoCoreError):
        return


def object_exists(settings: Settings, storage_key: str) -> bool:
    client = get_s3_client(settings)
    try:
        client.head_object(Bucket=settings.s3_bucket, Key=storage_key)
        return True
    except (ClientError, BotoCoreError):
        return False


def put_object(
    settings: Settings,
    *,
    storage_key: str,
    body: bytes,
    content_type: str,
) -> None:
    client = get_s3_client(settings)
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=storage_key,
        Body=body,
        ContentType=content_type,
    )


def get_object(settings: Settings, storage_key: str):
    client = get_s3_client(settings)
    return client.get_object(Bucket=settings.s3_bucket, Key=storage_key)


def build_media_url(storage_key: str) -> str:
    return f"/media/object?key={quote(storage_key, safe='')}"


def is_media_url(url: str | None) -> bool:
    return bool(url and url.startswith("/media/object?key="))


def storage_key_from_media_url(url: str) -> str | None:
    prefix = "/media/object?key="
    if not url.startswith(prefix):
        return None
    return unquote(url[len(prefix) :])
