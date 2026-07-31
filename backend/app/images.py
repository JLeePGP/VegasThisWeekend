"""Mirroring event media — images and video — into Cloudflare R2.

The PRD's reason for R2 is that external venue URLs break: a card that pointed at a
venue's CDN goes blank the week they redesign. So the file is copied once, at the moment
the event is saved, and the card points at our own bucket forever after.

There is a second reason, and it is the stronger one. Every third-party URL left on a
card is a request the visitor's browser makes to a host we do not control, which hands
that host the visitor's IP address, user agent, and the referring page — enough to know
that someone in a particular city looked at a particular event. This app sets no cookies
and stores nothing that identifies a person, and a single off-origin image quietly undoes
a good part of that. Mirroring means the browser talks to our bucket and nobody else.

The source URL arrives from an untrusted page, which makes this a server-side fetch of an
attacker-influenced address: a textbook SSRF sink. Every hop is checked against
public-address rules, redirects are followed by hand rather than by the client, the
content type is allowlisted, and the body is capped mid-stream.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import httpx

from .config import get_settings

# Extension is chosen from the response's own content type, never from the URL — a
# path ending in .jpg proves nothing about what the server actually returns.
IMAGE_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
}

# Deliberately short. These are what a phone records and what every browser the app
# targets plays without arguing about codecs; anything else is a transcoding job rather
# than a copy, and this function only copies.
VIDEO_CONTENT_TYPES = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}

MAX_REDIRECTS = 3
REQUEST_TIMEOUT = 20.0
# Video is larger and venue CDNs are slower than image hosts. This runs inside an admin
# request John is watching, never a visitor's, so a long wait costs nobody else anything.
VIDEO_REQUEST_TIMEOUT = 120.0


class ImageMirrorError(RuntimeError):
    """Raised when media could not be mirrored. Never fatal to saving an event.

    Still named for images because it is raised and caught by name across the admin
    router and the tests; the failure it represents is the same for video.
    """


def _resolves_to_public_address(host: str) -> bool:
    """Reject hosts that resolve to anything other than a public address.

    This is what stops a pasted URL from reaching localhost, a Docker sidecar, or a cloud
    metadata endpoint. It resolves rather than pattern-matching, so `http://127.0.0.1.nip.io/`
    is caught too.

    A determined attacker could still race DNS between this check and the request
    (rebinding). Given the URL comes off a page John is actively reviewing, that is an
    acceptable residual risk; an egress allowlist is the real fix if it ever matters.
    """
    try:
        resolved = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return False
    if not resolved:
        return False
    return all(ipaddress.ip_address(info[4][0]).is_global for info in resolved)


def _assert_fetchable(url: str, *, kind: str = "image") -> None:
    """`kind` only shapes the message; the checks it performs are identical either way."""
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ImageMirrorError(f"Only http and https {kind} URLs can be mirrored.")
    if not parsed.hostname:
        raise ImageMirrorError(f"That {kind} URL has no host.")
    if not _resolves_to_public_address(parsed.hostname):
        raise ImageMirrorError(f"That {kind} host does not resolve to a public address.")


def _rules_for(kind: str) -> tuple[dict[str, str], int, float]:
    settings = get_settings()
    if kind == "video":
        return VIDEO_CONTENT_TYPES, settings.max_video_bytes, VIDEO_REQUEST_TIMEOUT
    if kind == "image":
        return IMAGE_CONTENT_TYPES, settings.max_image_bytes, REQUEST_TIMEOUT
    raise ImageMirrorError(f"Unknown media kind {kind!r}.")


def download_media(source_url: str, *, kind: str = "image") -> tuple[bytes, str]:
    """Fetch media, following redirects manually so every hop is re-validated.

    Returns (body, content_type). Letting httpx follow redirects itself would skip the
    address check on hops 2..n, which is precisely where an SSRF payload hides.

    `kind` selects the allowlist, the size cap and the timeout. Everything else about
    fetching an image and fetching a video is identical, and a separate video function
    would mean a second copy of the SSRF handling — the one part that must never drift.
    """
    allowed, max_bytes, timeout = _rules_for(kind)
    url = source_url

    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _assert_fetchable(url, kind=kind)

            with client.stream("GET", url) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ImageMirrorError(f"That {kind} redirect had no destination.")
                    url = urljoin(url, location)
                    continue

                if response.status_code >= 400:
                    raise ImageMirrorError(
                        f"The {kind} host returned HTTP {response.status_code}."
                    )

                content_type = (
                    response.headers.get("content-type", "").split(";")[0].strip().lower()
                )
                if content_type not in allowed:
                    raise ImageMirrorError(
                        f"Unsupported {kind} type: {content_type or 'unknown'}"
                    )

                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    # Checked mid-stream, so a host that advertises a small file and then
                    # sends a huge one is cut off rather than filling memory first.
                    if len(body) > max_bytes:
                        raise ImageMirrorError(f"That {kind} is larger than the size limit.")

                if not body:
                    raise ImageMirrorError(f"The {kind} host returned an empty body.")
                return bytes(body), content_type

    raise ImageMirrorError(f"Too many redirects while fetching that {kind}.")


def download_image(source_url: str) -> tuple[bytes, str]:
    """Back-compatible alias; prefer download_media."""
    return download_media(source_url, kind="image")


def mirror_to_r2(source_url: str, *, kind: str = "image") -> str:
    """Copy media into R2 and return its durable public URL."""
    settings = get_settings()
    if not settings.r2_enabled:
        raise ImageMirrorError("Cloudflare R2 is not configured on this deployment.")

    body, content_type = download_media(source_url, kind=kind)

    # Imported lazily: the API runs fine without boto3 when R2 is unconfigured.
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import BotoCoreError, ClientError

    extensions = {**IMAGE_CONTENT_TYPES, **VIDEO_CONTENT_TYPES}
    # Separate prefixes so a bucket lifecycle rule or a cost breakdown can tell the two
    # apart; video is the expensive one to store and serve.
    folder = "video" if kind == "video" else "events"
    key = f"{folder}/{uuid4().hex}{extensions[content_type]}"

    client = boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=BotoConfig(signature_version="s3v4", retries={"max_attempts": 3}),
    )

    try:
        client.put_object(
            Bucket=settings.r2_bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            # Immutable: the key contains a fresh uuid, so the object never changes.
            CacheControl="public, max-age=31536000, immutable",
        )
    except (BotoCoreError, ClientError) as error:
        raise ImageMirrorError(f"Upload to R2 failed: {error}") from error

    return f"{settings.r2_public_base_url.rstrip('/')}/{key}"
