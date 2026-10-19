from django.conf import settings
from django.db import models
from django.utils import timezone


class ShortURL(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="short_urls")
    original_url = models.URLField(max_length=2048)
    short_code = models.CharField(max_length=32, unique=True)  # unique => indexed
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    click_count = models.PositiveBigIntegerField(default=0)  # denormalised counter, updated by Celery
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.short_code} -> {self.original_url}"

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()


class ClickEvent(models.Model):
    short_url = models.ForeignKey(ShortURL, on_delete=models.CASCADE, related_name="clicks")
    clicked_at = models.DateTimeField(db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    referer = models.CharField(max_length=2048, blank=True)

    class Meta:
        ordering = ["-clicked_at"]
        indexes = [models.Index(fields=["short_url", "clicked_at"])]
