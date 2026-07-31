"""Fetching the video behind a TikTok post URL.

Nothing here touches the network: yt-dlp is replaced with a fake module in `sys.modules`,
which is also what lets these run on a machine that has not installed it.

Most of what is asserted is refusal. A reader that returns *something* plausible for a
post it did not really understand is worse than one that fails, because the something
gets copied into R2 and put on a card.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from app.video_sources import (
    FORMAT_PREFERENCE,
    RESOLVABLE_HOSTS,
    VideoResolveError,
    download_video_page,
    is_resolvable_video_page,
)

TIKTOK_URL = "https://www.tiktok.com/@lvlightsfc/video/7665394552613735711"
MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"payload"


class FakeDownloadError(Exception):
    """Stands in for `yt_dlp.utils.DownloadError`, which the reader catches by name."""


@pytest.fixture
def fake_ytdlp(monkeypatch):
    """Install a fake `yt_dlp` that writes a canned file, or raises.

    `written` is the filename it drops into yt-dlp's output directory; passing None makes
    it write nothing, which is how a real oversize abort or a photo post behaves.
    """

    captured = {}

    def install(*, written="video.mp4", body=MP4_BYTES, error=None):
        module = types.ModuleType("yt_dlp")
        utils = types.ModuleType("yt_dlp.utils")
        utils.DownloadError = FakeDownloadError

        class FakeYoutubeDL:
            def __init__(self, options):
                captured["options"] = options

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def download(self, urls):
                captured["urls"] = urls
                if error is not None:
                    raise error
                if written is not None:
                    target = Path(captured["options"]["outtmpl"]).parent / written
                    target.write_bytes(body)
                return 0

        module.YoutubeDL = FakeYoutubeDL
        module.utils = utils
        monkeypatch.setitem(sys.modules, "yt_dlp", module)
        monkeypatch.setitem(sys.modules, "yt_dlp.utils", utils)
        return captured

    return install


class TestWhichHostsAreRead:
    """The allowlist is the security boundary. This path runs outside the per-hop SSRF
    checks in images.py, and yt-dlp ships ~2000 extractors — some of which read local
    files — so what is *not* handed to it matters more than what is."""

    @pytest.mark.parametrize("host", sorted(RESOLVABLE_HOSTS))
    def test_every_allowlisted_host_is_recognised(self, host):
        assert is_resolvable_video_page(f"https://{host}/@venue/video/123")

    def test_instagram_is_not_read(self):
        """Deliberately excluded: its posts need a logged-in session, so supporting it
        would mean a credential living on the server."""
        assert not is_resolvable_video_page("https://www.instagram.com/p/DbCOzEPGNhR/")

    def test_a_direct_cdn_url_is_left_alone(self):
        assert not is_resolvable_video_page("https://cdn.example.com/clip.mp4")

    def test_a_lookalike_path_does_not_qualify(self):
        """Host-based, not substring-based — otherwise this URL would be handed to yt-dlp."""
        assert not is_resolvable_video_page("https://evil.example.com/www.tiktok.com/video/1")

    def test_a_lookalike_subdomain_does_not_qualify(self):
        assert not is_resolvable_video_page("https://tiktok.com.evil.example.com/video/1")

    def test_a_malformed_url_is_not_read(self):
        assert not is_resolvable_video_page("not-a-url")

    def test_a_non_allowlisted_url_is_refused_outright(self):
        """Belt and braces: the caller checks first, but this must never be the thing
        that lets an arbitrary URL reach yt-dlp."""
        with pytest.raises(VideoResolveError, match="not a video page"):
            download_video_page("https://cdn.example.com/clip.mp4")


class TestDownloading:
    def test_a_post_yields_mp4_bytes(self, fake_ytdlp):
        fake_ytdlp()
        body, content_type = download_video_page(TIKTOK_URL)
        assert content_type == "video/mp4"
        assert body == MP4_BYTES

    def test_the_post_url_is_what_gets_fetched(self, fake_ytdlp):
        captured = fake_ytdlp()
        download_video_page(TIKTOK_URL)
        assert captured["urls"] == [TIKTOK_URL]

    def test_a_webm_is_accepted(self, fake_ytdlp):
        fake_ytdlp(written="video.webm")
        _, content_type = download_video_page(TIKTOK_URL)
        assert content_type == "video/webm"

    def test_the_size_cap_is_passed_to_yt_dlp(self, fake_ytdlp):
        """So an oversized clip costs one aborted request rather than a full download."""
        from app.config import get_settings

        captured = fake_ytdlp()
        download_video_page(TIKTOK_URL)
        assert captured["options"]["max_filesize"] == get_settings().max_video_bytes

    def test_merging_formats_is_never_requested(self, fake_ytdlp):
        """ffmpeg is not installed on the API host, so a merge would fail at the last
        step of an otherwise successful download."""
        assert "+" not in FORMAT_PREFERENCE
        captured = fake_ytdlp()
        download_video_page(TIKTOK_URL)
        assert captured["options"]["format"] == FORMAT_PREFERENCE

    def test_the_temporary_file_does_not_outlive_the_call(self, fake_ytdlp):
        captured = fake_ytdlp()
        download_video_page(TIKTOK_URL)
        assert not Path(captured["options"]["outtmpl"]).parent.exists()


class TestRefusals:
    def test_a_photo_post_writes_nothing_and_is_refused(self, fake_ytdlp):
        fake_ytdlp(written=None)
        with pytest.raises(VideoResolveError, match="photo post"):
            download_video_page(TIKTOK_URL)

    def test_an_unstorable_extension_is_refused(self, fake_ytdlp):
        """A format outside the allowlist must not be renamed into the bucket."""
        fake_ytdlp(written="video.mkv")
        with pytest.raises(VideoResolveError, match="not a video format"):
            download_video_page(TIKTOK_URL)

    def test_an_empty_file_is_refused(self, fake_ytdlp):
        fake_ytdlp(body=b"")
        with pytest.raises(VideoResolveError, match="empty"):
            download_video_page(TIKTOK_URL)

    def test_an_oversized_body_is_refused_even_undeclared(self, fake_ytdlp, monkeypatch):
        """max_filesize only acts on a size the platform declared up front, and TikTok
        does not always declare one — so the bytes are measured after the fact too."""
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "max_video_bytes", 4, raising=False)
        fake_ytdlp(body=b"x" * 100)
        with pytest.raises(VideoResolveError, match="larger than the size limit"):
            download_video_page(TIKTOK_URL)

    def test_tiktoks_own_message_is_passed_through(self, fake_ytdlp):
        """"Video is private" is the useful half of the warning John reads in the panel;
        replacing it with a generic string would cost him the diagnosis."""
        fake_ytdlp(error=FakeDownloadError("Video is private"))
        with pytest.raises(VideoResolveError, match="Video is private"):
            download_video_page(TIKTOK_URL)

    def test_an_unexpected_extractor_crash_is_still_a_resolve_error(self, fake_ytdlp):
        """Extractors raise a wide variety of exceptions; none of them may reach the
        request handler, because saving the event must survive a reader failure."""
        fake_ytdlp(error=KeyError("aweme_detail"))
        with pytest.raises(VideoResolveError, match="failed"):
            download_video_page(TIKTOK_URL)

    def test_a_missing_yt_dlp_is_reported_not_crashed(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "yt_dlp", None)
        with pytest.raises(VideoResolveError, match="not installed"):
            download_video_page(TIKTOK_URL)
