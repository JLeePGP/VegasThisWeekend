"""Resolving the client address behind proxies.

The bug this covers was invisible: keying on the socket peer put every visitor behind
Cloudflare into one rate-limit bucket, which looks exactly like normal operation until
there is enough traffic for real people to start getting 429s.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.client_ip import client_ip, resolve
from app.config import get_settings


def make_request(headers: dict[str, str] | None = None, peer: str = "10.0.0.7"):
    """Enough of a Request for the resolver. slowapi reads `.client.host`."""
    lowered = {k.lower(): v for k, v in (headers or {}).items()}
    return SimpleNamespace(
        headers=SimpleNamespace(get=lambda name, default=None: lowered.get(name.lower(), default)),
        client=SimpleNamespace(host=peer),
    )


@pytest.fixture
def trusting(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    return settings


@pytest.fixture
def untrusting(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "trust_proxy_headers", False)
    return settings


class TestResolution:
    def test_prefers_cloudflares_header(self, trusting):
        request = make_request(
            {"CF-Connecting-IP": "203.0.113.5", "X-Forwarded-For": "198.51.100.9, 10.0.0.1"}
        )
        # Cloudflare overwrites its own header; X-Forwarded-For is a list a client can
        # prepend to, so it is the weaker of the two.
        assert client_ip(request) == "203.0.113.5"

    def test_falls_back_to_the_first_forwarded_entry(self, trusting):
        request = make_request({"X-Forwarded-For": "203.0.113.5, 10.0.0.1, 10.0.0.2"})
        assert client_ip(request) == "203.0.113.5"

    def test_ignores_the_proxy_hops_after_the_client(self, trusting):
        request = make_request({"X-Forwarded-For": "203.0.113.5, 172.16.0.4"})
        assert client_ip(request) != "172.16.0.4"

    def test_falls_back_to_the_socket_peer_with_no_headers(self, trusting):
        assert client_ip(make_request(peer="192.0.2.10")) == "192.0.2.10"

    def test_tolerates_whitespace(self, trusting):
        assert client_ip(make_request({"X-Forwarded-For": "  203.0.113.5 , 10.0.0.1"})) == "203.0.113.5"

    def test_never_returns_none(self, trusting):
        """slowapi uses the key to build a dict key; None would blow up on the first
        request from something without a peer address."""
        request = make_request(peer=None)
        request.client = None
        assert isinstance(client_ip(request), str)


class TestDistinctBuckets:
    def test_two_visitors_behind_one_proxy_get_different_keys(self, trusting):
        """The whole point. Both requests arrive from the same Railway address."""
        a = make_request({"CF-Connecting-IP": "203.0.113.5"}, peer="10.0.0.7")
        b = make_request({"CF-Connecting-IP": "198.51.100.9"}, peer="10.0.0.7")
        assert client_ip(a) != client_ip(b)

    def test_the_old_behaviour_would_have_collapsed_them(self, untrusting):
        """With trust switched off — which is what keying on the peer amounted to —
        the same two visitors share a bucket. This is the bug, pinned."""
        a = make_request({"CF-Connecting-IP": "203.0.113.5"}, peer="10.0.0.7")
        b = make_request({"CF-Connecting-IP": "198.51.100.9"}, peer="10.0.0.7")
        assert client_ip(a) == client_ip(b) == "10.0.0.7"


class TestSourceReport:
    def test_reports_every_candidate(self, trusting):
        request = make_request(
            {
                "CF-Connecting-IP": "203.0.113.5",
                "X-Forwarded-For": "203.0.113.5, 10.0.0.1",
                "CF-Ray": "abc123-LAS",
            }
        )
        sources = resolve(request)
        assert sources["cf_connecting_ip"] == "203.0.113.5"
        assert sources["x_forwarded_for_first"] == "203.0.113.5"
        assert sources["x_forwarded_for_raw"] == "203.0.113.5, 10.0.0.1"
        assert sources["socket_peer"] == "10.0.0.7"
        assert sources["cf_ray"] == "abc123-LAS"

    def test_missing_headers_are_null_not_absent(self, trusting):
        sources = resolve(make_request())
        assert set(sources) == {
            "cf_connecting_ip",
            "x_forwarded_for_first",
            "x_forwarded_for_raw",
            "socket_peer",
            "cf_ray",
        }
        assert sources["cf_connecting_ip"] is None


class TestDiagnosticsEndpoint:
    def test_requires_the_admin_token(self, client):
        assert client.get("/admin/diagnostics/client").status_code == 401

    def test_reports_what_the_server_sees(self, admin_client):
        body = admin_client.get(
            "/admin/diagnostics/client",
            headers={"CF-Connecting-IP": "203.0.113.5", "CF-Ray": "abc-LAS"},
        ).json()
        assert body["resolved_key"] == "203.0.113.5"
        assert body["behind_proxy"] is True
        assert body["sources"]["cf_ray"] == "abc-LAS"

    def test_says_when_it_is_not_behind_a_proxy(self, admin_client):
        body = admin_client.get("/admin/diagnostics/client").json()
        assert body["behind_proxy"] is False
