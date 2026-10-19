from django.contrib import admin
from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from links.frontend import home
from links.views import RegisterView, ShortURLViewSet, health, redirect_view

router = DefaultRouter()
router.register("urls", ShortURLViewSet, basename="shorturl")

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("healthz/", health),
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/", include(router.urls)),
    # Must stay LAST: catches /<short_code>/
    re_path(r"^(?P<code>[0-9A-Za-z_-]{3,32})/$", redirect_view, name="redirect"),
]