from django.contrib import admin

from .models import ClickEvent, ShortURL


@admin.register(ShortURL)
class ShortURLAdmin(admin.ModelAdmin):
    list_display = ("short_code", "original_url", "owner", "click_count", "is_active", "expires_at", "created_at")
    search_fields = ("short_code", "original_url")
    list_filter = ("is_active",)


@admin.register(ClickEvent)
class ClickEventAdmin(admin.ModelAdmin):
    list_display = ("short_url", "clicked_at", "ip_address", "referer")
    list_select_related = ("short_url",)
