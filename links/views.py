import logging
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.utils import timezone
from rest_framework import generics, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import ShortURL
from .serializers import RegisterSerializer, ShortURLSerializer
from .tasks import record_click
from .utils import cache_key, cache_ttl, get_client_ip

logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []


class ShortURLViewSet(viewsets.ModelViewSet):
    """CRUD for the logged-in user's links (+ /stats/). Users only ever see their own rows."""

    serializer_class = ShortURLSerializer
    lookup_field = "short_code"
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return ShortURL.objects.filter(owner=self.request.user)

    def perform_update(self, serializer):
        obj = serializer.save()
        cache.delete(cache_key(obj.short_code))  # never serve a stale target

    def perform_destroy(self, instance):
        cache.delete(cache_key(instance.short_code))
        instance.delete()

    @action(detail=True, methods=["get"])
    def stats(self, request, short_code=None):
        obj = self.get_object()
        since = timezone.now() - timedelta(days=30)
        daily = (
            obj.clicks.filter(clicked_at__gte=since)
            .annotate(day=TruncDate("clicked_at"))
            .values("day").annotate(clicks=Count("id")).order_by("day")
        )
        top_referers = (
            obj.clicks.exclude(referer="")
            .values("referer").annotate(clicks=Count("id")).order_by("-clicks")[:5]
        )
        return Response({
            "short_code": obj.short_code,
            "total_clicks": obj.click_count,
            "last_30_days": list(daily),
            "top_referers": list(top_referers),
        })


def redirect_view(request, code):
    """Hot path: Redis lookup -> (DB on miss) -> 302. Analytics are fire-and-forget."""
    key = cache_key(code)
    target = None
    try:
        target = cache.get(key)
    except Exception:  # Redis down must not take redirects down
        logger.warning("cache read failed", exc_info=True)

    if target is None:
        obj = ShortURL.objects.filter(short_code=code).first()
        if obj is None or not obj.is_active or obj.is_expired:
            raise Http404("Short link not found")
        target = obj.original_url
        try:
            cache.set(key, target, cache_ttl(obj))
        except Exception:
            logger.warning("cache write failed", exc_info=True)

    try:
        record_click.delay(
            code,
            get_client_ip(request),
            request.META.get("HTTP_USER_AGENT", ""),
            request.META.get("HTTP_REFERER", ""),
            timezone.now().isoformat(),
        )
    except Exception:  # broker down: lose one analytics event, never the redirect
        logger.warning("could not enqueue click event", exc_info=True)

    # 302 (not 301) so browsers don't cache it and every click is counted
    return HttpResponseRedirect(target)


def health(request):
    return JsonResponse({"status": "ok"})
