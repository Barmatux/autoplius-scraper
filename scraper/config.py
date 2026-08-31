from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


@dataclass(frozen=True)
class Settings:
    test_mode: bool
    pages: int
    page_delay_sec: float
    enrich_details: bool
    enrich_limit: int
    detail_delay_sec: float
    interval_hours: int
    data_dir: Path
    profile_dir: Path
    logs_dir: Path
    db_path: Path
    auto_captcha: bool
    headless: bool
    timeout_sec: float
    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    s3_region: str
    sync_photos_after_scrape: bool
    sync_photos_timeout_sec: int
    autoplius_base_url: str
    translate_descriptions: bool
    translate_delay_sec: float

    @property
    def s3_enabled(self) -> bool:
        return bool(self.s3_endpoint_url and self.s3_access_key and self.s3_secret_key)

    @classmethod
    def from_env(cls, *, root: Path | None = None) -> Settings:
        root = root or Path(__file__).resolve().parents[1]
        load_dotenv(root / ".env")
        data_dir = Path(os.environ.get("DATA_DIR", root / "data"))
        db_path = Path(os.environ.get("DB_PATH", data_dir / "autoplius.db"))
        return cls(
            test_mode=_env_bool("TEST_MODE", True),
            pages=_env_int("SCRAPE_PAGES", 10),
            page_delay_sec=_env_float("PAGE_DELAY_SEC", 3.0),
            enrich_details=_env_bool("ENRICH_DETAILS", True),
            # 0 = enrich all listings from search pages
            enrich_limit=_env_int("ENRICH_LIMIT", 0),
            detail_delay_sec=_env_float("DETAIL_DELAY_SEC", 2.0),
            interval_hours=_env_int("SCRAPE_INTERVAL_HOURS", 1),
            data_dir=data_dir,
            profile_dir=Path(os.environ.get("PROFILE_DIR", root / ".browser-profile")),
            logs_dir=Path(os.environ.get("LOGS_DIR", root / "logs")),
            db_path=db_path,
            auto_captcha=_env_bool("AUTO_CAPTCHA", True),
            headless=_env_bool("HEADLESS", True),
            timeout_sec=_env_float("SCRAPE_TIMEOUT_SEC", 180.0),
            s3_endpoint_url=os.environ.get("S3_ENDPOINT_URL", "").strip(),
            s3_access_key=os.environ.get("S3_ACCESS_KEY", "").strip(),
            s3_secret_key=os.environ.get("S3_SECRET_KEY", "").strip(),
            s3_bucket=os.environ.get("S3_BUCKET", "autoplius-media").strip(),
            s3_region=os.environ.get("S3_REGION", "us-east-1").strip(),
            sync_photos_after_scrape=_env_bool("SYNC_PHOTOS_AFTER_SCRAPE", True),
            sync_photos_timeout_sec=_env_int("SYNC_PHOTOS_TIMEOUT_SEC", 25),
            autoplius_base_url=os.environ.get("AUTOPLIUS_BASE_URL", "https://ru.autoplius.lt").strip().rstrip("/"),
            translate_descriptions=_env_bool("TRANSLATE_DESCRIPTIONS", True),
            translate_delay_sec=_env_float("TRANSLATE_DELAY_SEC", 0.15),
        )
