"""Verifying that a request really came through Cloudflare.

The risk being covered is a guard that silently does nothing. Every check here has a
plausible mis-implementation that passes a naive test: a secret that is configured but
never compared, an enforcement flag that is read but never acted on, or a health check
that starts failing and takes the deployment with it.
"""

from __future__ import annotations

from app.config import get_settings
from app.proxy_guard import PROXY_SECRET_HEADER, came_through_proxy

SECRET = "s3cr3t-from-the-transform-rule"


class FakeRequest:
    """Only `headers` and `url.path` are touched, so a full Request is unnecessary."""

    def __init__(self, headers: dict[str, str] | None = None, path: str = "/events"):
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.url = type("Url", (), {"path": path})()
        self.client = type("Client", (), {"host": "203.0.113.9"})()


class TestUnconfigured:
    def test_no_secret_means_every_request_passes(self):
        """The default. Distrusting every header the moment this module was added would
        quietly put every visitor back into one shared rate-limit bucket."""
        assert came_through_proxy(FakeRequest()) is True

    def test_a_stray_header_is_ignored_when_no_secret_is_set(self):
        assert came_through_proxy(FakeRequest({PROXY_SECRET_HEADER: "anything"})) is True


class TestConfigured:
    def test_the_matching_secret_is_accepted(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "proxy_shared_secret", SECRET, raising=False)
        assert came_through_proxy(FakeRequest({PROXY_SECRET_HEADER: SECRET})) is True

    def test_a_missing_secret_is_refused(self, monkeypatch):
        """This is the raw *.up.railway.app request the whole thing exists to catch."""
        monkeypatch.setattr(get_settings(), "proxy_shared_secret", SECRET, raising=False)
        assert came_through_proxy(FakeRequest()) is False

    def test_a_wrong_secret_is_refused(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "proxy_shared_secret", SECRET, raising=False)
        assert came_through_proxy(FakeRequest({PROXY_SECRET_HEADER: "wrong"})) is False

    def test_a_prefix_of_the_secret_is_refused(self, monkeypatch):
        """Guards against a comparison that only checks the start of the value."""
        monkeypatch.setattr(get_settings(), "proxy_shared_secret", SECRET, raising=False)
        assert came_through_proxy(FakeRequest({PROXY_SECRET_HEADER: SECRET[:10]})) is False

    def test_an_empty_header_is_refused(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "proxy_shared_secret", SECRET, raising=False)
        assert came_through_proxy(FakeRequest({PROXY_SECRET_HEADER: ""})) is False


class TestRateLimitKey:
    """What the guard is actually protecting: whose bucket a request lands in."""

    def test_an_unverified_request_cannot_claim_someone_elses_address(self, monkeypatch):
        """The attack. Without the guard, forging CF-Connecting-IP lets someone exhaust
        another visitor's rate limit — a denial of service against one person at a time.
        With it, the forged header is ignored and they can only affect their own."""
        from app.client_ip import client_ip

        settings = get_settings()
        monkeypatch.setattr(settings, "proxy_shared_secret", SECRET, raising=False)
        forged = FakeRequest({"cf-connecting-ip": "198.51.100.7"})
        assert client_ip(forged) == "203.0.113.9"

    def test_a_verified_request_is_keyed_on_the_visitor(self, monkeypatch):
        from app.client_ip import client_ip

        settings = get_settings()
        monkeypatch.setattr(settings, "proxy_shared_secret", SECRET, raising=False)
        genuine = FakeRequest(
            {"cf-connecting-ip": "198.51.100.7", PROXY_SECRET_HEADER: SECRET}
        )
        assert client_ip(genuine) == "198.51.100.7"


class TestEnforcement:
    def test_setting_the_secret_alone_rejects_nothing(self, client, monkeypatch):
        """The first stage of the rollout. Deploying the secret before the Cloudflare
        rule exists must not take the API down, or there is no safe way to land it."""
        settings = get_settings()
        monkeypatch.setattr(settings, "proxy_shared_secret", SECRET, raising=False)
        monkeypatch.setattr(settings, "require_proxy_secret", False, raising=False)
        assert client.get("/events").status_code == 200

    def test_enforcement_rejects_a_request_without_the_secret(self, client, monkeypatch):
        from app import main

        settings = get_settings()
        monkeypatch.setattr(settings, "proxy_shared_secret", SECRET, raising=False)
        monkeypatch.setattr(main.settings, "require_proxy_secret", True, raising=False)
        assert client.get("/events").status_code == 403

    def test_enforcement_allows_a_request_with_the_secret(self, client, monkeypatch):
        from app import main

        settings = get_settings()
        monkeypatch.setattr(settings, "proxy_shared_secret", SECRET, raising=False)
        monkeypatch.setattr(main.settings, "require_proxy_secret", True, raising=False)
        response = client.get("/events", headers={PROXY_SECRET_HEADER: SECRET})
        assert response.status_code == 200

    def test_health_stays_reachable_under_enforcement(self, client, monkeypatch):
        """Railway's healthcheck hits the container directly, never through Cloudflare.
        If this 403s, every deploy fails its healthcheck and rolls back while the logs
        show a perfectly healthy application."""
        from app import main

        settings = get_settings()
        monkeypatch.setattr(settings, "proxy_shared_secret", SECRET, raising=False)
        monkeypatch.setattr(main.settings, "require_proxy_secret", True, raising=False)
        assert client.get("/health").status_code == 200
