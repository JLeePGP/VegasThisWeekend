"""Mirroring media into R2.

The reason these tests exist is privacy, not durability. Every media URL left pointing at
a third party is a request the visitor's browser makes to a host we do not control, which
hands that host their IP address and the page they were looking at. So what is asserted
here is mostly what the mirror *refuses* — because a refusal that silently succeeds is
how an unvetted URL ends up on a card.
"""

from __future__ import annotations

import httpx
import pytest

from app.images import (
    IMAGE_CONTENT_TYPES,
    VIDEO_CONTENT_TYPES,
    ImageMirrorError,
    download_media,
)


def transport(handler):
    """Swap httpx's network layer for a handler, so nothing here touches the internet."""
    return httpx.MockTransport(handler)


@pytest.fixture
def served(monkeypatch):
    """Serve a canned response for any URL, bypassing DNS and the network.

    The public-address check is monkeypatched to pass because it is tested directly
    elsewhere; leaving it live would make these tests depend on DNS.
    """

    def install(*, content_type: str, body: bytes, status_code: int = 200):
        monkeypatch.setattr("app.images._resolves_to_public_address", lambda host: True)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code, headers={"content-type": content_type}, content=body
            )

        real_client = httpx.Client

        def patched(*args, **kwargs):
            kwargs["transport"] = transport(handler)
            return real_client(*args, **kwargs)

        monkeypatch.setattr("app.images.httpx.Client", patched)

    return install


class TestVideoTypes:
    def test_mp4_is_accepted(self, served):
        served(content_type="video/mp4", body=b"\x00\x00\x00\x18ftypmp42")
        body, content_type = download_media("https://cdn.example.com/clip", kind="video")
        assert content_type == "video/mp4"
        assert body.startswith(b"\x00\x00\x00\x18")

    def test_webm_and_mov_are_accepted(self):
        assert set(VIDEO_CONTENT_TYPES) == {"video/mp4", "video/webm", "video/quicktime"}

    def test_a_streaming_manifest_is_refused(self, served):
        """An HLS playlist is a list of URLs, not a file. Mirroring it would copy the
        text and leave the actual segments loading from the venue's CDN — the exact
        third-party leak this is meant to close, but looking like a success."""
        served(content_type="application/vnd.apple.mpegurl", body=b"#EXTM3U")
        with pytest.raises(ImageMirrorError, match="Unsupported video type"):
            download_media("https://cdn.example.com/playlist.m3u8", kind="video")

    def test_an_image_is_refused_as_video(self, served):
        """The allowlists do not overlap, so a mis-set kind fails loudly."""
        served(content_type="image/jpeg", body=b"\xff\xd8\xff")
        with pytest.raises(ImageMirrorError, match="Unsupported video type"):
            download_media("https://cdn.example.com/poster.jpg", kind="video")

    def test_a_video_is_refused_as_image(self, served):
        served(content_type="video/mp4", body=b"\x00\x00\x00\x18ftypmp42")
        with pytest.raises(ImageMirrorError, match="Unsupported image type"):
            download_media("https://cdn.example.com/clip.mp4", kind="image")

    def test_html_is_refused(self, served):
        """A page that 200s with HTML is the usual shape of a dead media URL — a login
        wall or an error page. Saving it would put a card's image or video one byte
        away from being a web page."""
        served(content_type="text/html", body=b"<!doctype html><title>Sign in</title>")
        with pytest.raises(ImageMirrorError, match="Unsupported video type"):
            download_media("https://cdn.example.com/gated", kind="video")


class TestSizeCaps:
    def test_video_is_capped(self, served, monkeypatch):
        from app.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "max_video_bytes", 32, raising=False)
        served(content_type="video/mp4", body=b"x" * 500)
        with pytest.raises(ImageMirrorError, match="larger than the size limit"):
            download_media("https://cdn.example.com/big.mp4", kind="video")

    def test_video_gets_a_larger_cap_than_images(self):
        """A clip is legitimately bigger than a poster; sharing one cap would mean either
        rejecting every real video or accepting an absurd image."""
        from app.config import get_settings

        settings = get_settings()
        assert settings.max_video_bytes > settings.max_image_bytes


class TestFailureModes:
    def test_an_empty_body_is_refused(self, served):
        served(content_type="video/mp4", body=b"")
        with pytest.raises(ImageMirrorError, match="empty body"):
            download_media("https://cdn.example.com/clip.mp4", kind="video")

    def test_an_error_status_is_refused(self, served):
        served(content_type="video/mp4", body=b"nope", status_code=503)
        with pytest.raises(ImageMirrorError, match="HTTP 503"):
            download_media("https://cdn.example.com/clip.mp4", kind="video")

    def test_an_unknown_kind_is_refused(self):
        """Guards against a typo silently selecting the image allowlist."""
        with pytest.raises(ImageMirrorError, match="Unknown media kind"):
            download_media("https://cdn.example.com/x", kind="audio")

    def test_the_two_allowlists_do_not_overlap(self):
        assert not set(IMAGE_CONTENT_TYPES) & set(VIDEO_CONTENT_TYPES)
