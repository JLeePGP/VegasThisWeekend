"""Mirroring event images into Cloudflare R2.

The PRD's reason for R2 is that external venue URLs break — a card that pointed at a
venue's CDN goes blank the week they redesign. So the image is copied once, at the
moment the event is saved, and the card points at our own bucket forever after.

The image URL arrives from an untrusted page, which makes this a server-side fetch of
an attacker-influenced address: a textbook SSRF sink. Every hop is checked against
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
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
}

MAX_REDIRECTS = 3
REQUEST_TIMEOUT = 20.0


class ImageMirrorError(RuntimeError):
    """Raised when an image could not be mirrored. Never fatal to saving an event."""


def _resolves_to_public_address(host: str) -> bool:
    """Reject hosts that resolve to anything other than a public address.

    This is what stops a pasted image URL from reaching localhost, a Docker sidecar,
    or a cloud metadata endpoint. It resolves rather than pattern-matching, so
    `http://127.0.0.1.nip.io/` is caught too.

    A determined attacker could still race DNS between this check and the request
    (rebinding). Given the image URL comes off a page John is actively reviewing, that
    is an acceptable residual risk; an egress allowlist is the real fix if it matters.
    """
    try:
        resolved = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return False
    if not resolved:
        return False
    return all(ipaddress.ip_address(info[4][0]).is_global for info in resolved)


def _assert_fetchable(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ImageMirrorError("Only http and https image URLs can be mirrored.")
    if not parsed.hostname:
        raise ImageMirrorError("That image URL has no host.")
    if not _resolves_to_public_address(parsed.hostname):
        raise ImageMirrorError("That image host does not resolve to a public address.")


def download_image(source_url: str) -> tuple[bytes, str]:
    """Fetch an image, following redirects manually so every hop is re-validated.

    Returns (body, content_type). Letting httpx follow redirects itself would skip the
    address check on hops 2..n, which is precisely where an SSRF payload hides.
    """
    settings = get_settings()
    url = source_url

    with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _assert_fetchable(url)

            with client.stream("GET", url) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ImageMirrorError("Image redirect had no destination.")
                    url = urljoin(url, location)
                    continue

                if response.status_code >= 400:
                    raise ImageMirrorError(f"Image host returned HTTP {response.status_code}.")

                content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise ImageMirrorError(f"Unsupported image type: {content_type or 'unknown'}")

                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > settings.max_image_bytes:
                        raise ImageMirrorError("Image is larger than the size limit.")

                if not body:
                    raise ImageMirrorError("Image host returned an empty body.")
                return bytes(body), content_type

    raise ImageMirrorError("Too many redirects while fetching that image.")


def mirror_to_r2(source_url: str) -> str:
    """Copy an image into R2 and return its durable public URL."""
    settings = get_settings()
    if not settings.r2_enabled:
        raise ImageMirrorError("Cloudflare R2 is not configured on this deployment.")

    body, content_type = download_image(source_url)

    # Imported lazily: the API runs fine without boto3 when R2 is unconfigured.
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import BotoCoreError, ClientError

    key = f"events/{uuid4().hex}{ALLOWED_CONTENT_TYPES[content_type]}"

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
