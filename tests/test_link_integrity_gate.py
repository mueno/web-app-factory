"""Tests for tools/gates/link_integrity_gate.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest
import httpx

from tools.gates.gate_result import GateResult


def _make_mock_response(status_code: int, body: str = "", url: str = "https://example.com") -> MagicMock:
    """Build a minimal mock httpx Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = body
    mock_resp.url = httpx.URL(url)
    return mock_resp


# HTML with two internal links and one external link
_BASE_HTML = """
<html>
<body>
  <a href="/about">About</a>
  <a href="/contact">Contact</a>
  <a href="https://external.com/page">External</a>
</body>
</html>
"""

_ABOUT_HTML = "<html><body><h1>About</h1></body></html>"
_CONTACT_HTML = "<html><body><h1>Contact</h1></body></html>"


class TestLinkIntegrityGatePass:
    """Tests where all internal links are valid."""

    def test_all_links_200_pass(self):
        """All internal links return 200 -> passed=True."""
        from tools.gates.link_integrity_gate import run_link_integrity_gate

        responses = {
            "https://example.com/": _make_mock_response(200, _BASE_HTML, "https://example.com/"),
            "https://example.com/about": _make_mock_response(200, _ABOUT_HTML, "https://example.com/about"),
            "https://example.com/contact": _make_mock_response(200, _CONTACT_HTML, "https://example.com/contact"),
        }

        def mock_get(url, **kwargs):
            return responses.get(str(url), _make_mock_response(200, "", str(url)))

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = mock_get
            mock_client_cls.return_value = mock_client

            result = run_link_integrity_gate("https://example.com")

        assert isinstance(result, GateResult)
        assert result.passed is True

    def test_all_links_200_no_issues(self):
        """All internal links 200 -> no issues."""
        from tools.gates.link_integrity_gate import run_link_integrity_gate

        responses = {
            "https://example.com/": _make_mock_response(200, _BASE_HTML, "https://example.com/"),
            "https://example.com/about": _make_mock_response(200, _ABOUT_HTML),
            "https://example.com/contact": _make_mock_response(200, _CONTACT_HTML),
        }

        def mock_get(url, **kwargs):
            return responses.get(str(url), _make_mock_response(200))

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = mock_get
            mock_client_cls.return_value = mock_client

            result = run_link_integrity_gate("https://example.com")

        assert result.issues == []

    def test_gate_type_is_link_integrity(self):
        """gate_type field is 'link_integrity'."""
        from tools.gates.link_integrity_gate import run_link_integrity_gate

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(200, "<html></html>")
            mock_client_cls.return_value = mock_client

            result = run_link_integrity_gate("https://example.com")

        assert result.gate_type == "link_integrity"

    def test_phase_id_preserved(self):
        """phase_id passed to function appears in result."""
        from tools.gates.link_integrity_gate import run_link_integrity_gate

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(200, "<html></html>")
            mock_client_cls.return_value = mock_client

            result = run_link_integrity_gate("https://example.com", phase_id="3")

        assert result.phase_id == "3"

    def test_redirect_responses_are_ok(self):
        """301 redirect response -> not an issue."""
        from tools.gates.link_integrity_gate import run_link_integrity_gate

        base_html = '<html><body><a href="/redirected">Redirected</a></body></html>'

        def mock_get(url, **kwargs):
            if str(url) == "https://example.com/" or str(url) == "https://example.com":
                return _make_mock_response(200, base_html, "https://example.com/")
            elif "/redirected" in str(url):
                return _make_mock_response(301, "", str(url))
            return _make_mock_response(200, "")

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = mock_get
            mock_client_cls.return_value = mock_client

            result = run_link_integrity_gate("https://example.com")

        assert result.passed is True
        assert result.issues == []


class TestLinkIntegrityGateFail:
    """Tests where 404 links are found."""

    def test_one_404_fail(self):
        """One link returns 404 -> passed=False."""
        from tools.gates.link_integrity_gate import run_link_integrity_gate

        base_html = '<html><body><a href="/missing">Missing</a></body></html>'

        def mock_get(url, **kwargs):
            if "/missing" in str(url):
                return _make_mock_response(404, "", str(url))
            return _make_mock_response(200, base_html, str(url))

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = mock_get
            mock_client_cls.return_value = mock_client

            result = run_link_integrity_gate("https://example.com")

        assert result.passed is False

    def test_one_404_produces_issue(self):
        """One 404 link -> one issue in result."""
        from tools.gates.link_integrity_gate import run_link_integrity_gate

        base_html = '<html><body><a href="/missing">Missing</a></body></html>'

        def mock_get(url, **kwargs):
            if "/missing" in str(url):
                return _make_mock_response(404, "", str(url))
            return _make_mock_response(200, base_html, str(url))

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = mock_get
            mock_client_cls.return_value = mock_client

            result = run_link_integrity_gate("https://example.com")

        assert len(result.issues) == 1
        assert any("404" in issue for issue in result.issues)

    def test_fail_result_status_is_blocked(self):
        """404 found -> status='BLOCKED'."""
        from tools.gates.link_integrity_gate import run_link_integrity_gate

        base_html = '<html><body><a href="/missing">Missing</a></body></html>'

        def mock_get(url, **kwargs):
            if "/missing" in str(url):
                return _make_mock_response(404, "", str(url))
            return _make_mock_response(200, base_html, str(url))

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = mock_get
            mock_client_cls.return_value = mock_client

            result = run_link_integrity_gate("https://example.com")

        assert result.status == "BLOCKED"


class TestLinkIntegrityGateExternalLinks:
    """Tests that external links are ignored."""

    def test_external_links_not_checked(self):
        """Links to a different hostname are not checked."""
        from tools.gates.link_integrity_gate import run_link_integrity_gate

        base_html = """
        <html><body>
        <a href="https://external.com/resource">External</a>
        <a href="https://another.net/page">Another external</a>
        </body></html>
        """

        checked_urls = []

        def mock_get(url, **kwargs):
            checked_urls.append(str(url))
            return _make_mock_response(200, "", str(url))

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = mock_get
            mock_client_cls.return_value = mock_client

            result = run_link_integrity_gate("https://example.com")

        # Only the base URL itself is checked, no external links
        assert all("external.com" not in url and "another.net" not in url for url in checked_urls)


class TestLinkIntegrityGateCrawlLimits:
    """Tests for crawl depth and URL count limits."""

    def test_max_depth_respected(self):
        """Crawl stops at depth 3 (no links beyond depth 3 are followed)."""
        from tools.gates.link_integrity_gate import run_link_integrity_gate

        # Build a chain: / -> /level1 -> /level2 -> /level3 -> /level4 (should NOT be followed)
        pages = {
            "https://example.com/": '<html><a href="/level1">L1</a></html>',
            "https://example.com/level1": '<html><a href="/level2">L2</a></html>',
            "https://example.com/level2": '<html><a href="/level3">L3</a></html>',
            "https://example.com/level3": '<html><a href="/level4">L4</a></html>',
            "https://example.com/level4": '<html><h1>Deep</h1></html>',
        }

        checked_urls = []

        def mock_get(url, **kwargs):
            url_str = str(url)
            checked_urls.append(url_str)
            # Normalize trailing slash
            body = pages.get(url_str, pages.get(url_str.rstrip("/") + "/", "<html></html>"))
            return _make_mock_response(200, body, url_str)

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = mock_get
            mock_client_cls.return_value = mock_client

            result = run_link_integrity_gate("https://example.com")

        # /level4 should NOT be checked (depth 4 exceeds limit of 3)
        assert not any("level4" in url for url in checked_urls)

    def test_max_urls_respected(self):
        """Crawl stops after 50 URLs checked."""
        from tools.gates.link_integrity_gate import run_link_integrity_gate

        # Build page that contains many links
        many_links = "\n".join(f'<a href="/page{i}">Page {i}</a>' for i in range(100))
        base_html = f"<html><body>{many_links}</body></html>"

        call_count = [0]

        def mock_get(url, **kwargs):
            call_count[0] += 1
            if str(url).endswith("/") or str(url) == "https://example.com":
                return _make_mock_response(200, base_html, str(url))
            return _make_mock_response(200, "<html></html>", str(url))

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = mock_get
            mock_client_cls.return_value = mock_client

            result = run_link_integrity_gate("https://example.com")

        # Should not have checked more than 50 URLs
        assert call_count[0] <= 50


class TestLinkIntegrityGateExtra:
    """Tests for extra data in GateResult."""

    def test_extra_contains_urls_checked(self):
        """extra dict has 'urls_checked' key."""
        from tools.gates.link_integrity_gate import run_link_integrity_gate

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(200, "<html></html>")
            mock_client_cls.return_value = mock_client

            result = run_link_integrity_gate("https://example.com")

        assert "urls_checked" in result.extra

    def test_extra_contains_broken_links(self):
        """extra dict has 'broken_links' key."""
        from tools.gates.link_integrity_gate import run_link_integrity_gate

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(200, "<html></html>")
            mock_client_cls.return_value = mock_client

            result = run_link_integrity_gate("https://example.com")

        assert "broken_links" in result.extra


class TestLinkIntegrityGateRequestErrors:
    """Tests for request error handling."""

    def test_request_error_per_url_is_issue(self):
        """Individual URL timeout produces an issue for that URL, others continue."""
        from tools.gates.link_integrity_gate import run_link_integrity_gate

        base_html = '<html><body><a href="/ok">OK</a><a href="/broken">Broken</a></body></html>'

        def mock_get(url, **kwargs):
            if "/broken" in str(url):
                raise httpx.RequestError("Connection timeout", request=MagicMock())
            if "/ok" in str(url):
                return _make_mock_response(200, "<html>OK</html>", str(url))
            return _make_mock_response(200, base_html, str(url))

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.side_effect = mock_get
            mock_client_cls.return_value = mock_client

            result = run_link_integrity_gate("https://example.com")

        # /ok was still checked despite /broken failing
        assert result.extra["urls_checked"] >= 2
