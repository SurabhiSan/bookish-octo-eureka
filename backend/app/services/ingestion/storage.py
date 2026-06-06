"""Local disk storage — replaces R2 for MVP."""
from pathlib import Path
from app.core.config import get_settings


def _upload_dir() -> Path:
    settings = get_settings()
    d = Path(settings.upload_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def upload_to_r2(key: str, content: bytes) -> None:
    path = _upload_dir() / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def download_from_r2(key: str) -> bytes:
    path = _upload_dir() / key
    return path.read_bytes()


def delete_from_r2(key: str) -> None:
    path = _upload_dir() / key
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
