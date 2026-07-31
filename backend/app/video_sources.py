"""Fetching the video behind a social post URL.

A TikTok link is an HTML page, not a video. Pasting one into the video field stored a URL
that `<video src>` could never play, and that `images.py` correctly refused to mirror
because it serves `text/html`. This module is the missing step: given a TikTok post URL,
it produces the actual MP4 bytes, which then go into R2 through the ordinary upload path.

**Why this downloads rather than just resolving a URL.** The obvious design — ask yt-dlp
for the direct CDN URL and hand it to `download_media` — was built first and does not
work. TikTok's CDN answers those signed URLs with 403 for any client that is not the
session which produced them; supplying the Referer and User-Agent yt-dlp reports is not
enough. Reproducing whatever else that session carries would mean reimplementing a moving
target, so yt-dlp does the fetch itself. Measured against a live post: resolve-then-fetch
returned HTTP 403, yt-dlp's own downloader returned 2.7 MB of MP4.

That trade is worth being explicit about, because it moves this path outside the SSRF
handling in `images.py`. What replaces it is `RESOLVABLE_HOSTS`: yt-dlp is only ever
invoked for URLs whose host is on that list, so the address it fetches is TikTok's, not
one an arbitrary pasted string chose. The size cap and the content-type allowlist still
apply — they are re-checked in `mirror_bytes_to_r2` on the way into the bucket.

The bytes are also a copy of somebody's video, which is a judgement about the source, not
a technical property. That call is John's, per post.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

from .config import get_settings
from .images import VIDEO_CONTENT_TYPES

# Only these are handed to yt-dlp, and this is the security boundary that replaces the
# per-hop address checks in images.py. yt-dlp ships ~2000 extractors, several of which
# read local files or reach internal services, so an arbitrary admin-supplied string must
# never reach it.
#
# Instagram is deliberately absent: its posts need a logged-in session, so supporting it
# would mean storing John's credentials on the server and re-pasting them whenever they
# expire. Those stay a manual job.
RESOLVABLE_HOSTS = frozenset(
    {
        "tiktok.com",
        "www.tiktok.com",
        "m.tiktok.com",
        # Share-sheet shorteners. They 301 to the canonical post, which yt-dlp follows.
        "vm.tiktok.com",
        "vt.tiktok.com",
    }
)

# Single-file formats only, in preference order. Never `bestvideo+bestaudio`: merging
# needs ffmpeg, which is not installed on the API host, and this pipeline copies rather
# than transcodes. A muxed MP4 is also the format every browser the app targets plays
# without argument.
FORMAT_PREFERENCE = "best[ext=mp4][vcodec!=none][acodec!=none]/best[ext=mp4]/best"

# yt-dlp does its own network I/O, outside the httpx timeouts in images.py. Without this
# a slow extractor would hang the admin request until the platform's proxy gives up.
SOCKET_TIMEOUT = 30.0

# Content type is decided by the extension yt-dlp wrote, inverted from the one allowlist
# so the two can never drift apart.
EXTENSION_CONTENT_TYPES = {ext: ctype for ctype, ext in VIDEO_CONTENT_TYPES.items()}


class VideoResolveError(RuntimeError):
    """Raised when a social post could not be turned into video bytes.

    Never fatal to saving an event — the caller catches it, keeps the original URL and
    surfaces the message as the same media warning every other mirror failure uses.
    """


def is_resolvable_video_page(url: str) -> bool:
    """True when `url` is a post we know how to unwrap.

    Host-based rather than pattern-based: it is the host that decides whether yt-dlp is
    involved at all, and a check that guessed from the path could be walked past with a
    URL whose path merely looked like TikTok's.
    """
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host in RESOLVABLE_HOSTS


def download_video_page(url: str) -> tuple[bytes, str]:
    """Return `(body, content_type)` for the video behind a social post URL.

    Mirrors `images.download_media`'s contract so the two are interchangeable at the call
    site. Raises `VideoResolveError` on any failure; callers warn, keep the original URL,
    and save the event anyway.
    """
    if not is_resolvable_video_page(url):
        raise VideoResolveError(f"{url} is not a video page this app knows how to read.")

    # Imported lazily, matching boto3 and anthropic: yt-dlp is a large import and the API
    # must boot fine on a deployment that never touches a social URL.
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError as error:  # pragma: no cover - depends on the deployment
        raise VideoResolveError(
            "yt-dlp is not installed on this deployment, so TikTok links cannot be read."
        ) from error

    max_bytes = get_settings().max_video_bytes

    with TemporaryDirectory(prefix="vtw-video-") as workspace:
        options = {
            "quiet": True,
            "no_warnings": True,
            # `quiet` does not cover the progress bar, which writes a line per chunk
            # straight to stdout and would fill the deployment's logs with each save.
            "noprogress": True,
            "noplaylist": True,
            "format": FORMAT_PREFERENCE,
            "socket_timeout": SOCKET_TIMEOUT,
            # Aborts before the body arrives when the platform declares the size, so an
            # oversized clip costs a request rather than a full download.
            "max_filesize": max_bytes,
            "outtmpl": str(Path(workspace) / "video.%(ext)s"),
            # yt-dlp otherwise calls sys.exit on some failures, which inside a web worker
            # would take down the request in a way FastAPI cannot report.
            "ignoreerrors": False,
        }

        try:
            with YoutubeDL(options) as ydl:
                ydl.download([url])
        except DownloadError as error:
            # TikTok's own message is usually the useful one ("video is private", "region
            # locked"), so it is passed through rather than replaced with a generic string.
            raise VideoResolveError(f"Could not read that TikTok post: {error}") from error
        except Exception as error:  # noqa: BLE001 - extractors raise a wide variety
            raise VideoResolveError(f"Reading that TikTok post failed: {error}") from error

        written = sorted(Path(workspace).glob("video.*"))
        if not written:
            # `max_filesize` aborts by writing nothing, so this is also the oversize path.
            raise VideoResolveError(
                "That TikTok post produced no video file — it may be a photo post, a "
                "slideshow, or larger than the size limit."
            )

        downloaded = written[0]
        content_type = EXTENSION_CONTENT_TYPES.get(downloaded.suffix.lower())
        if content_type is None:
            raise VideoResolveError(
                f"That TikTok post downloaded as {downloaded.suffix or 'an unknown type'}, "
                "which is not a video format this app stores."
            )

        body = downloaded.read_bytes()

    if not body:
        raise VideoResolveError("That TikTok post downloaded as an empty file.")
    # Re-checked here as well as in mirror_bytes_to_r2: max_filesize only acts on a size
    # the platform declared up front, and TikTok does not always declare one.
    if len(body) > max_bytes:
        raise VideoResolveError("That TikTok video is larger than the size limit.")
    return body, content_type
