from datetime import datetime

from celery import shared_task
from django.db import transaction
from django.db.models import F

from .models import ClickEvent, ShortURL


@shared_task(ignore_result=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def record_click(code, ip, user_agent, referer, clicked_at_iso):
    """Runs in the Celery worker so the redirect itself never waits on analytics writes."""
    short_url = ShortURL.objects.filter(short_code=code).only("id").first()
    if short_url is None:
        return
    with transaction.atomic():
        ClickEvent.objects.create(
            short_url=short_url,
            clicked_at=datetime.fromisoformat(clicked_at_iso),
            ip_address=ip,
            user_agent=(user_agent or "")[:512],
            referer=(referer or "")[:2048],
        )
        # Atomic increment in SQL, safe under concurrent workers
        ShortURL.objects.filter(pk=short_url.pk).update(click_count=F("click_count") + 1)
