from datetime import timedelta

from unittest import mock

from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import ShortURL
from .utils import cache_key


class ShortenerTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client.post("/api/auth/register/", {"username": "ram", "password": "S3cure-pass-9"})
        token = self.client.post("/api/auth/token/", {"username": "ram", "password": "S3cure-pass-9"}).data["access"]
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def create(self, **extra):
        payload = {"original_url": "https://example.com/some/long/path", **extra}
        return self.client.post("/api/urls/", payload, format="json", **self.auth)

    def test_create_requires_auth(self):
        r = self.client.post("/api/urls/", {"original_url": "https://example.com"}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_create_and_redirect_and_click_tracking(self):
        r = self.create()
        self.assertEqual(r.status_code, 201)
        code = r.data["short_code"]
        self.assertEqual(len(code), 7)

        resp = self.client.get(f"/{code}/", HTTP_REFERER="https://news.site/", HTTP_USER_AGENT="pytest")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], "https://example.com/some/long/path")

        obj = ShortURL.objects.get(short_code=code)  # Celery runs eagerly in tests
        self.assertEqual(obj.click_count, 1)
        self.assertEqual(obj.clicks.first().referer, "https://news.site/")

    def test_redirect_is_served_from_cache(self):
        code = self.create().data["short_code"]
        self.client.get(f"/{code}/")  # warms cache
        self.assertEqual(cache.get(cache_key(code)), "https://example.com/some/long/path")
        # With the task mocked out, a cached redirect must hit the DB zero times
        with mock.patch("links.views.record_click.delay") as delay, self.assertNumQueries(0):
            resp = self.client.get(f"/{code}/")
        self.assertEqual(resp.status_code, 302)
        delay.assert_called_once()

    def test_redirect_survives_broker_failure(self):
        code = self.create().data["short_code"]
        with mock.patch("links.views.record_click.delay", side_effect=ConnectionError("broker down")):
            self.assertEqual(self.client.get(f"/{code}/").status_code, 302)

    def test_custom_alias_and_conflict(self):
        self.assertEqual(self.create(custom_alias="my-link").data["short_code"], "my-link")
        self.assertEqual(self.create(custom_alias="my-link").status_code, 400)
        self.assertEqual(self.create(custom_alias="admin").status_code, 400)

    def test_rejects_bad_scheme(self):
        self.assertEqual(self.create(original_url="javascript:alert(1)").status_code, 400)
        self.assertEqual(self.create(original_url="ftp://example.com/x").status_code, 400)

    def test_expired_link_is_404(self):
        code = self.create().data["short_code"]
        ShortURL.objects.filter(short_code=code).update(expires_at=timezone.now() - timedelta(seconds=1))
        cache.clear()
        self.assertEqual(self.client.get(f"/{code}/").status_code, 404)

    def test_delete_invalidates_cache(self):
        code = self.create().data["short_code"]
        self.client.get(f"/{code}/")
        r = self.client.delete(f"/api/urls/{code}/", **self.auth)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.client.get(f"/{code}/").status_code, 404)

    def test_deactivate_invalidates_cache(self):
        code = self.create().data["short_code"]
        self.client.get(f"/{code}/")
        self.client.patch(f"/api/urls/{code}/", {"is_active": False}, format="json", **self.auth)
        self.assertEqual(self.client.get(f"/{code}/").status_code, 404)

    def test_users_cannot_see_each_others_links(self):
        code = self.create().data["short_code"]
        self.client.post("/api/auth/register/", {"username": "sita", "password": "An0ther-pass-7"})
        tok = self.client.post("/api/auth/token/", {"username": "sita", "password": "An0ther-pass-7"}).data["access"]
        other = {"HTTP_AUTHORIZATION": f"Bearer {tok}"}
        self.assertEqual(self.client.get(f"/api/urls/{code}/", **other).status_code, 404)
        self.assertEqual(self.client.get("/api/urls/", **other).data["count"], 0)

    def test_stats(self):
        code = self.create().data["short_code"]
        for _ in range(3):
            self.client.get(f"/{code}/", HTTP_REFERER="https://a.com/")
        r = self.client.get(f"/api/urls/{code}/stats/", **self.auth)
        self.assertEqual(r.data["total_clicks"], 3)
        self.assertEqual(r.data["top_referers"][0], {"referer": "https://a.com/", "clicks": 3})
