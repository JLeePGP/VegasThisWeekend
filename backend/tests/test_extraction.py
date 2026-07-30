"""The parts of extraction and image mirroring that handle untrusted input.

These are the security-relevant units: what a hostile page can put in a URL field, and
what a hostile URL can make the server connect to. All offline — no test here touches
the network or the Claude API.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.enums import Neighborhood, PriceTier, Vibe
from app.extraction import ExtractedEvent, ExtractionError, _clean_url, parse_local
from app.images import ImageMirrorError, _assert_fetchable, _resolves_to_public_address


class TestCleanUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/tickets",
            "http://example.com/tickets",
            "https://example.com/a?b=c#d",
        ],
    )
    def test_keeps_plain_http_urls(self, url):
        assert _clean_url(url) == url

    @pytest.mark.parametrize(
        "url",
        [
            "javascript:alert(1)",
            "data:text/html;base64,PHNjcmlwdD4=",
            "file:///etc/passwd",
            "vbscript:msgbox(1)",
        ],
    )
    def test_drops_dangerous_schemes(self, url):
        assert _clean_url(url) is None

    def test_drops_a_url_with_no_host(self):
        assert _clean_url("https:///nowhere") is None

    def test_handles_empty_and_none(self):
        assert _clean_url(None) is None
        assert _clean_url("") is None
        assert _clean_url("   ") is None


class TestExtractedEventValidation:
    def _event(self, **overrides) -> ExtractedEvent:
        payload = {
            "name": "Midnight Mass",
            "venue": "Neon Cathedral",
            "neighborhood": Neighborhood.STRIP,
            "address": None,
            "starts_at_local": "2026-08-07T22:00",
            "ends_at_local": None,
            "vibe": Vibe.NIGHTLIFE,
            "tags": [],
            "alcohol_free": False,
            "price_tier": PriceTier.PREMIUM,
            "price_note": None,
            "hook": "The big room",
            "description": "A night.",
            "ticket_url": None,
            "image_url": None,
        }
        payload.update(overrides)
        return ExtractedEvent(**payload)

    def test_a_poisoned_ticket_url_is_stripped(self):
        """A page that tries to inject a javascript: link gets nothing through."""
        assert self._event(ticket_url="javascript:alert(1)").ticket_url is None

    def test_a_poisoned_image_url_is_stripped(self):
        assert self._event(image_url="data:image/png;base64,AAAA").image_url is None

    def test_a_legitimate_url_survives(self):
        event = self._event(ticket_url="https://example.com/buy")
        assert event.ticket_url == "https://example.com/buy"

    def test_an_unknown_vibe_is_rejected(self):
        with pytest.raises(Exception):
            self._event(vibe="karaoke")


class TestParseLocal:
    def test_parses_the_expected_format(self):
        assert parse_local("2026-08-07T22:00", field="starts_at_local") == datetime(2026, 8, 7, 22, 0)

    def test_rejects_a_timezone_aware_value(self):
        """The model is told never to send an offset; this is the enforcement."""
        with pytest.raises(ExtractionError, match="naive local"):
            parse_local("2026-08-07T22:00+00:00", field="starts_at_local")

    def test_rejects_a_trailing_z(self):
        with pytest.raises(ExtractionError):
            parse_local("2026-08-07T22:00Z", field="starts_at_local")

    def test_rejects_unparseable_text(self):
        with pytest.raises(ExtractionError, match="readable"):
            parse_local("next friday", field="starts_at_local")


class TestServerSideRequestForgery:
    """The image URL comes off an untrusted page, so this is an attacker-influenced
    server-side fetch. These are the checks that keep it off the internal network."""

    @pytest.mark.parametrize(
        "host",
        [
            "127.0.0.1",
            "0.0.0.0",
            "10.0.0.1",
            "192.168.1.1",
            "172.16.0.1",
            # AWS/GCP instance metadata — the classic SSRF target.
            "169.254.169.254",
            "localhost",
        ],
    )
    def test_private_and_loopback_hosts_are_refused(self, host):
        assert _resolves_to_public_address(host) is False

    def test_a_public_address_is_allowed(self):
        assert _resolves_to_public_address("8.8.8.8") is True

    def test_an_unresolvable_host_is_refused(self):
        assert _resolves_to_public_address("this-host-does-not-exist.invalid") is False

    @pytest.mark.parametrize("url", ["file:///etc/passwd", "gopher://x/", "ftp://example.com/x"])
    def test_non_http_schemes_are_refused(self, url):
        with pytest.raises(ImageMirrorError, match="http"):
            _assert_fetchable(url)

    def test_a_loopback_url_is_refused(self):
        with pytest.raises(ImageMirrorError, match="public address"):
            _assert_fetchable("http://127.0.0.1:8000/admin")

    def test_metadata_endpoint_is_refused(self):
        with pytest.raises(ImageMirrorError, match="public address"):
            _assert_fetchable("http://169.254.169.254/latest/meta-data/")
