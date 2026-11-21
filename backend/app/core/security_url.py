import asyncio
import ipaddress
import socket
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx

BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.goog",
    "169.254.169.254",
    "0.0.0.0",
    "::",
    "::1",
}

BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".arpa")

TRACKING_QUERY_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
    "ref",
}


class UnsafeURLError(Exception):
    """Raised when a URL fails SSRF validation or safety checks."""


def canonicalize_url(raw_url: str) -> str:
    """Normalize a URL for deduplication while preserving meaningful path/query."""
    parsed = urlparse(raw_url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    filtered_query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in TRACKING_QUERY_PARAMS
    ]
    filtered_query.sort()
    query = urlencode(filtered_query)

    return urlunparse((scheme, netloc, path, "", query, ""))


def _is_public_ip(ip_str: str) -> bool:
    """Return True only if ip_str is a globally routable public IP address."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return False
    # Explicitly ensure IPv4-mapped IPv6 addresses are also checked
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_public_ip(str(ip.ipv4_mapped))
    return ip.is_global


def _resolve_hostname_sync(hostname: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    ips: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr and isinstance(sockaddr[0], str):
            # Strip IPv6 scope ID if present
            ips.append(sockaddr[0].split("%")[0])
    return ips


async def validate_public_url(url: str, resolve_dns: bool = True) -> str:
    """Validate that a URL points strictly to a public HTTP(S) destination (SSRF defense)."""
    if not url or len(url) > 2048:
        raise UnsafeURLError("URL is empty or exceeds maximum allowed length.")

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeURLError(f"Disallowed URL scheme: {parsed.scheme!r}")

    if parsed.username or parsed.password:
        raise UnsafeURLError("Embedded credentials in URLs are not permitted.")

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        raise UnsafeURLError("URL must contain a valid hostname.")

    if hostname in BLOCKED_HOSTNAMES or any(
        hostname.endswith(suffix) for suffix in BLOCKED_SUFFIXES
    ):
        raise UnsafeURLError(f"Blocked internal/reserved hostname: {hostname}")

    # Direct IP literal check
    parsed_ip = None
    try:
        parsed_ip = ipaddress.ip_address(hostname)
    except ValueError:
        parsed_ip = None

    if parsed_ip is not None:
        if not _is_public_ip(hostname):
            raise UnsafeURLError(f"Blocked non-public IP address: {hostname}")
        return url.strip()

    if resolve_dns:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        try:
            resolved_ips = await asyncio.to_thread(_resolve_hostname_sync, hostname, port)
        except OSError as exc:
            raise UnsafeURLError(f"Failed to resolve hostname {hostname}: {exc}") from exc

        if not resolved_ips:
            raise UnsafeURLError(f"Hostname {hostname} resolved to no addresses.")

        for ip_addr in resolved_ips:
            if not _is_public_ip(ip_addr):
                raise UnsafeURLError(
                    f"Hostname {hostname} resolved to blocked non-public IP {ip_addr}"
                )

    return url.strip()


async def safe_fetch_url(
    url: str,
    *,
    timeout_seconds: int = 12,
    max_bytes: int = 1_500_000,
    max_redirects: int = 3,
    resolve_dns: bool = True,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[str, int, str, str]:
    """
    Fetch a public HTTP(S) URL safely with SSRF checks on the initial URL and every redirect hop,
    strict byte-size limits, and timeout enforcement.

    Returns (final_url, status_code, content_type, decoded_text).
    """
    current_url = await validate_public_url(url, resolve_dns=resolve_dns)
    headers = {
        "User-Agent": "VellumResearch/0.1 (+https://github.com/TahmidZ68/vellum-research)",
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_seconds),
        follow_redirects=False,
        transport=transport,
    ) as client:
        for _ in range(max_redirects + 1):
            async with client.stream("GET", current_url, headers=headers) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise UnsafeURLError("Redirect response missing Location header.")
                    next_url = urljoin(current_url, location)
                    current_url = await validate_public_url(next_url, resolve_dns=resolve_dns)
                    continue

                content_type = response.headers.get("content-type", "").lower()
                if content_type and not any(
                    allowed in content_type
                    for allowed in ("text/html", "application/xhtml+xml", "text/plain", "application/xml")
                ):
                    raise UnsafeURLError(f"Unsupported content type: {content_type}")

                chunks: list[bytes] = []
                total_bytes = 0
                async for chunk in response.aiter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        chunks.append(chunk[: max_bytes - (total_bytes - len(chunk))])
                        break
                    chunks.append(chunk)

                raw_bytes = b"".join(chunks)
                encoding = response.encoding or "utf-8"
                text = raw_bytes.decode(encoding, errors="replace")
                return current_url, response.status_code, content_type, text

    raise UnsafeURLError(f"Exceeded maximum redirects ({max_redirects}).")
