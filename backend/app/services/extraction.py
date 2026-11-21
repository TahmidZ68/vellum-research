import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.core.security_url import UnsafeURLError, safe_fetch_url

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
INJECTION_TAG_RE = re.compile(r"</?untrusted_source_content[^>]*>", re.IGNORECASE)


@dataclass
class ExtractedDocument:
    url: str
    final_url: str
    title: str
    publisher: str
    author: str | None
    published_at: str | None
    content_text: str
    raw_excerpt: str
    content_hash: str
    extraction_status: str
    limitations: str
    error_detail: str | None = None


def sanitize_untrusted_text(text: str, max_chars: int = 16000) -> str:
    """
    Sanitize untrusted webpage text before storing or passing to an LLM.
    Strips control characters, collapses excessive whitespace, and neutralizes
    delimiter breakout attempts.
    """
    cleaned = CONTROL_CHARS_RE.sub("", text or "")
    cleaned = INJECTION_TAG_RE.sub("[filtered-tag]", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()[:max_chars]


def wrap_untrusted_source(
    source_ref: int,
    *,
    title: str,
    publisher: str,
    url: str,
    published_at: str | None,
    source_type: str,
    content: str,
) -> str:
    """Wrap extracted source content inside explicit data-only delimiters."""
    safe_content = sanitize_untrusted_text(content, max_chars=8000)
    safe_title = sanitize_untrusted_text(title, max_chars=300)
    return (
        f'<untrusted_source_content ref="{source_ref}" publisher="{publisher}" '
        f'source_type="{source_type}" published_at="{published_at or "unknown"}" '
        f'url="{url}">\n'
        f"Title: {safe_title}\n"
        f"Body:\n{safe_content}\n"
        f"</untrusted_source_content>"
    )


def infer_source_type(url: str, title: str = "", content: str = "") -> str:
    """Provide a transparent initial classification based on domain and page metadata."""
    host = (urlparse(url).hostname or "").lower()
    combined = f"{title} {content[:600]}".lower()

    if host.endswith(".gov") or ".gov." in host or host.endswith(".mil") or "europa.eu" in host:
        return "government"
    if (
        host.endswith(".edu")
        or ".ac." in host
        or any(d in host for d in ("arxiv.org", "pubmed", "scholar.google", "nature.com", "ieee.org", "acm.org", "sciencedirect"))
    ):
        return "academic"
    if any(d in host for d in ("docs.", "github.com", "developer.", "rfc-editor.org", "w3.org")):
        return "primary"
    if any(d in host for d in ("reuters.com", "apnews.com", "bbc.", "ft.com", "nytimes.com", "economist.com", "techcrunch.com", "thedailystar.net")):
        return "journalism"
    if any(k in combined for k in ("pricing", "book a demo", "free trial", "case study", "request a quote")):
        return "promotional"
    if any(k in combined for k in ("opinion", "editorial", "commentary", "my view", "substack")):
        return "opinion"
    return "company"


def extract_readable_content(
    raw_html_or_text: str,
    *,
    url: str,
    content_type: str = "text/html",
    fallback_title: str = "",
) -> tuple[str, str, str | None, str | None, str]:
    """
    Extract clean readable text and metadata from HTML or plain text.
    Returns (title, publisher, author, published_at, clean_text).
    """
    hostname = (urlparse(url).hostname or "unknown").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    if "text/plain" in content_type:
        cleaned = sanitize_untrusted_text(raw_html_or_text)
        return fallback_title or hostname, hostname, None, None, cleaned

    soup = BeautifulSoup(raw_html_or_text, "lxml")

    # Remove active/hidden/non-content elements before fallback parsing
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "template"]):
        tag.decompose()
    for hidden in soup.select('[style*="display:none"], [style*="display: none"], [hidden], [aria-hidden="true"]'):
        hidden.decompose()

    title = fallback_title or hostname
    if soup.title and soup.title.string:
        candidate_title = sanitize_untrusted_text(soup.title.string, max_chars=300)
        if candidate_title:
            title = candidate_title

    publisher = hostname
    og_site = soup.find("meta", attrs={"property": "og:site_name"})
    if og_site and og_site.get("content"):
        publisher = sanitize_untrusted_text(str(og_site["content"]), max_chars=120) or hostname

    author: str | None = None
    author_meta = soup.find("meta", attrs={"name": re.compile(r"^author$", re.I)})
    if author_meta and author_meta.get("content"):
        author = sanitize_untrusted_text(str(author_meta["content"]), max_chars=120) or None

    published_at: str | None = None
    for attr_key, attr_val in (
        ("property", "article:published_time"),
        ("name", "pubdate"),
        ("name", "publish-date"),
        ("name", "date"),
        ("property", "og:updated_time"),
    ):
        meta_date = soup.find("meta", attrs={attr_key: attr_val})
        if meta_date and meta_date.get("content"):
            published_at = sanitize_untrusted_text(str(meta_date["content"]), max_chars=64) or None
            break

    # Primary extractor: Trafilatura on sanitized HTML
    cleaned_html = str(soup)
    extracted_text = trafilatura.extract(
        cleaned_html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
        favor_precision=True,
    )

    if not extracted_text or len(extracted_text.strip()) < 120:
        # Fallback: BeautifulSoup visible paragraph/heading extraction
        blocks = [
            el.get_text(" ", strip=True)
            for el in soup.find_all(["h1", "h2", "h3", "p", "li", "td", "th"])
        ]
        extracted_text = "\n".join(b for b in blocks if len(b) > 20)

    clean_text = sanitize_untrusted_text(extracted_text or "")
    return title, publisher, author, published_at, clean_text


async def fetch_and_extract_source(
    url: str,
    *,
    fallback_title: str = "",
    fallback_snippet: str = "",
    fallback_published_at: str | None = None,
    prefetched_raw_content: str | None = None,
    resolve_dns: bool = True,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ExtractedDocument:
    """
    Safely fetch a URL (with SSRF checks) and extract readable text + provenance metadata.
    Falls back gracefully to snippet if extraction fails or content is blocked.
    """
    settings = get_settings()
    hostname = (urlparse(url).hostname or "unknown").lower().removeprefix("www.")

    if prefetched_raw_content and len(prefetched_raw_content.strip()) >= 200:
        clean = sanitize_untrusted_text(prefetched_raw_content)
        content_hash = hashlib.sha256(clean.encode("utf-8")).hexdigest()
        return ExtractedDocument(
            url=url,
            final_url=url,
            title=fallback_title or hostname,
            publisher=hostname,
            author=None,
            published_at=fallback_published_at,
            content_text=clean,
            raw_excerpt=clean[:600],
            content_hash=content_hash,
            extraction_status="extracted",
            limitations="Extracted from search provider payload.",
        )

    try:
        final_url, status_code, content_type, body = await safe_fetch_url(
            url,
            timeout_seconds=settings.EXTRACTION_TIMEOUT_SECONDS,
            max_bytes=settings.MAX_EXTRACTION_BYTES,
            max_redirects=settings.MAX_REDIRECTS,
            resolve_dns=resolve_dns,
            transport=transport,
        )
        if status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {status_code}",
                request=httpx.Request("GET", final_url),
                response=httpx.Response(status_code),
            )

        title, publisher, author, published_at, clean_text = extract_readable_content(
            body,
            url=final_url,
            content_type=content_type,
            fallback_title=fallback_title,
        )
        if len(clean_text) < 80 and fallback_snippet:
            clean_text = sanitize_untrusted_text(fallback_snippet)
            limitations = "Full page body yielded minimal text; fell back to search snippet."
            status_label = "extracted"
        elif not clean_text:
            limitations = "Page contained no extractable readable text."
            status_label = "failed"
        else:
            limitations = "No full-page extraction errors observed."
            status_label = "extracted"

        content_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest() if clean_text else ""
        return ExtractedDocument(
            url=url,
            final_url=final_url,
            title=title or fallback_title or hostname,
            publisher=publisher or hostname,
            author=author,
            published_at=published_at or fallback_published_at,
            content_text=clean_text,
            raw_excerpt=clean_text[:600] if clean_text else sanitize_untrusted_text(fallback_snippet, 600),
            content_hash=content_hash,
            extraction_status=status_label,
            limitations=limitations,
        )
    except UnsafeURLError as exc:
        return ExtractedDocument(
            url=url,
            final_url=url,
            title=fallback_title or hostname,
            publisher=hostname,
            author=None,
            published_at=fallback_published_at,
            content_text="",
            raw_excerpt=sanitize_untrusted_text(fallback_snippet, 600),
            content_hash="",
            extraction_status="failed",
            limitations=f"Blocked by URL safety policy: {exc}",
            error_detail=str(exc),
        )
    except Exception as exc:
        safe_snippet = sanitize_untrusted_text(fallback_snippet)
        return ExtractedDocument(
            url=url,
            final_url=url,
            title=fallback_title or hostname,
            publisher=hostname,
            author=None,
            published_at=fallback_published_at,
            content_text=safe_snippet,
            raw_excerpt=safe_snippet[:600],
            content_hash=hashlib.sha256(safe_snippet.encode("utf-8")).hexdigest() if safe_snippet else "",
            extraction_status="failed" if not safe_snippet else "extracted",
            limitations=f"Direct page fetch failed ({type(exc).__name__}); snippet used only if available.",
            error_detail=str(exc),
        )
