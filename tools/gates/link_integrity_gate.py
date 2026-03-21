"""Link integrity gate executor.

Crawls the deployed application starting from the root URL using BFS
(breadth-first search), following internal links only (same hostname).
Reports any internal links that return HTTP 404 as issues.

Limits: max crawl depth 3, max 50 URLs checked.

Exported function: run_link_integrity_gate
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from tools.gates.gate_result import GateResult


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_MAX_DEPTH = 3
_MAX_URLS = 50
_REQUEST_TIMEOUT = 10


class _LinkExtractor(HTMLParser):
    """Minimal HTML parser that collects href attributes from <a> tags."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "a":
            for attr_name, attr_value in attrs:
                if attr_name == "href" and attr_value:
                    self.links.append(attr_value)


def _extract_links(html: str) -> list:
    """Extract all href values from <a> tags in the HTML."""
    parser = _LinkExtractor()
    parser.feed(html)
    return parser.links


def _is_same_host(base_url: str, link_url: str) -> bool:
    """Return True if link_url has the same hostname as base_url."""
    base_parsed = urlparse(base_url)
    link_parsed = urlparse(link_url)
    return base_parsed.netloc == link_parsed.netloc


def _normalize_url(base: str, href: str) -> str:
    """Resolve a potentially-relative href against a base URL."""
    return urljoin(base, href)


def _strip_fragment(url: str) -> str:
    """Remove URL fragments (#section) to avoid duplicate checks."""
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()


def run_link_integrity_gate(url: str, phase_id: str = "3") -> GateResult:
    """Crawl deployed app and report internal 404 links.

    Uses BFS from the starting URL. Only internal links (same hostname)
    are followed and checked. External links are ignored. Redirects
    (301, 302, 308) are treated as OK. Only 404 responses are reported.

    Args:
        url: Full URL of the deployed application root.
        phase_id: Pipeline phase identifier (default "3").

    Returns:
        GateResult with gate_type="link_integrity". passed=True when
        no internal 404 links are found.
        extra["urls_checked"] is the total count of URLs checked.
        extra["broken_links"] is the list of 404 URLs.
    """
    checked_at = _now_iso()

    base_hostname = urlparse(url).netloc
    visited: set = set()
    broken_links: list = []
    issues: list = []
    urls_checked = 0

    # BFS queue: (url, depth)
    queue: deque = deque()
    start_url = _strip_fragment(url)
    queue.append((start_url, 0))
    visited.add(start_url)

    _OK_STATUSES = {200, 301, 302, 308}

    with httpx.Client(follow_redirects=False, timeout=_REQUEST_TIMEOUT) as client:
        while queue and urls_checked < _MAX_URLS:
            current_url, depth = queue.popleft()
            urls_checked += 1

            try:
                response = client.get(current_url)
                status = response.status_code
            except httpx.RequestError as exc:
                issues.append(f"Request error on {current_url}: {exc}")
                broken_links.append(current_url)
                continue

            if status == 404:
                issues.append(f"404 Not Found: {current_url}")
                broken_links.append(current_url)
                # Don't follow links from 404 pages
                continue

            # Follow internal links if within depth limit
            if depth < _MAX_DEPTH and status in _OK_STATUSES:
                # Only parse HTML responses from same-hostname pages
                page_host = urlparse(str(response.url)).netloc
                if page_host == base_hostname:
                    try:
                        page_html = response.text
                    except Exception:
                        page_html = ""

                    for href in _extract_links(page_html):
                        # Skip anchor-only, javascript, mailto links
                        if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
                            continue

                        absolute = _normalize_url(current_url, href)
                        absolute = _strip_fragment(absolute)

                        # Only follow same-hostname links
                        if not _is_same_host(url, absolute):
                            continue

                        # Skip already-visited URLs
                        if absolute in visited:
                            continue

                        if urls_checked + len(queue) < _MAX_URLS:
                            visited.add(absolute)
                            queue.append((absolute, depth + 1))

    passed = len(broken_links) == 0

    return GateResult(
        gate_type="link_integrity",
        phase_id=phase_id,
        passed=passed,
        status="PASS" if passed else "BLOCKED",
        severity="INFO" if passed else "BLOCK",
        confidence=1.0 if passed else 0.0,
        checked_at=checked_at,
        issues=issues,
        extra={
            "urls_checked": urls_checked,
            "broken_links": broken_links,
        },
    )
