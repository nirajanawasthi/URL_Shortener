import ipaddress
import secrets
import string

from django.conf import settings
from django.utils import timezone

ALPHABET = string.ascii_letters + string.digits  # base62
CODE_LENGTH = 7  # 62^7 ~ 3.5 trillion combinations
RESERVED_CODES = {"api", "admin", "healthz", "static"}


def generate_code(length=CODE_LENGTH):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def cache_key(code):
    return f"short:{code}"


def cache_ttl(short_url):
    """Cache TTL that never outlives the link's own expiry."""
    if short_url.expires_at is None:
        return settings.REDIRECT_CACHE_TTL
    remaining = int((short_url.expires_at - timezone.now()).total_seconds())
    return max(1, min(remaining, settings.REDIRECT_CACHE_TTL))


def get_client_ip(request):
    """Best-effort client IP. Only trust X-Forwarded-For behind your own reverse proxy."""
    raw = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR")
    try:
        return str(ipaddress.ip_address(raw))
    except (ValueError, TypeError):
        return None
