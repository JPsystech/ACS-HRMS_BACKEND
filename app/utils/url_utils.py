from urllib.parse import urlparse, urlunparse
from typing import Optional
from app.core.config import settings

def _base() -> str:
    return settings.PUBLIC_BASE_URL.rstrip("/")

def build_api_image_url(kind: str, key: str) -> str:
    return f"{_base()}/api/v1/{kind}/image/{key}"

def is_private_host(host: str) -> bool:
    h = host.lower()
    return (
        h.startswith("localhost")
        or h.startswith("127.0.0.1")
        or h.startswith("192.168.")
        or h.startswith("10.")
    )

def normalize_public_url(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("/"):
        return f"{_base()}{s}"
    if s.startswith("http://") or s.startswith("https://"):
        try:
            p = urlparse(s)
            if is_private_host(p.hostname or ""):
                return f"{_base()}{p.path}"
            if _base().startswith("https://") and p.scheme == "http" and (p.hostname or "").endswith("onrender.com"):
                return urlunparse(p._replace(scheme="https"))
        except Exception:
            return s
        return s
    return f"{_base()}/{s.lstrip('/')}"
