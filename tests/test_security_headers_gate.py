"""Tests for tools/gates/security_headers_gate.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import httpx

from tools.gates.gate_result import GateResult


def _make_mock_response(headers: dict) -> MagicMock:
    """Build a mock httpx Response with the given headers."""
    mock_resp = MagicMock()
    mock_resp.headers = httpx.Headers(headers)
    mock_resp.status_code = 200
    return mock_resp


ALL_REQUIRED_HEADERS = {
    "Content-Security-Policy": "default-src 'self'",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000",
}


class TestSecurityHeadersGatePass:
    """Tests where all required headers are present."""

    def test_all_headers_present_pass(self):
        """All 4 required headers present -> passed=True."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        mock_resp = _make_mock_response(ALL_REQUIRED_HEADERS)
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert isinstance(result, GateResult)
        assert result.passed is True

    def test_pass_result_status_is_pass(self):
        """Passing gate returns status='PASS'."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        mock_resp = _make_mock_response(ALL_REQUIRED_HEADERS)
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert result.status == "PASS"

    def test_pass_result_has_no_issues(self):
        """No issues when all required headers present."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        mock_resp = _make_mock_response(ALL_REQUIRED_HEADERS)
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert result.issues == []

    def test_gate_type_is_security_headers(self):
        """gate_type field is 'security_headers'."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        mock_resp = _make_mock_response(ALL_REQUIRED_HEADERS)
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert result.gate_type == "security_headers"

    def test_phase_id_preserved(self):
        """phase_id passed to function appears in result."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        mock_resp = _make_mock_response(ALL_REQUIRED_HEADERS)
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com", phase_id="3")

        assert result.phase_id == "3"

    def test_checked_at_is_populated(self):
        """checked_at field is non-empty on success."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        mock_resp = _make_mock_response(ALL_REQUIRED_HEADERS)
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert isinstance(result.checked_at, str)
        assert len(result.checked_at) > 0


class TestSecurityHeadersGateFail:
    """Tests where required headers are missing."""

    def test_missing_csp_fail(self):
        """CSP header missing -> passed=False."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        headers = {k: v for k, v in ALL_REQUIRED_HEADERS.items() if "Content-Security-Policy" not in k}
        mock_resp = _make_mock_response(headers)
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert result.passed is False

    def test_missing_csp_has_issue_mentioning_csp(self):
        """CSP missing -> issue mentioning Content-Security-Policy."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        headers = {k: v for k, v in ALL_REQUIRED_HEADERS.items() if "Content-Security-Policy" not in k}
        mock_resp = _make_mock_response(headers)
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert any("content-security-policy" in issue.lower() for issue in result.issues)

    def test_missing_multiple_headers_fail(self):
        """2 required headers missing -> 2 issues."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        headers = {
            "Strict-Transport-Security": "max-age=31536000",
        }
        mock_resp = _make_mock_response(headers)
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert result.passed is False
        assert len(result.issues) == 4  # all 4 required headers missing

    def test_fail_result_status_is_blocked(self):
        """Failing gate returns status='BLOCKED'."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        mock_resp = _make_mock_response({})
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert result.status == "BLOCKED"

    def test_fail_result_severity_is_block(self):
        """Failing gate returns severity='BLOCK'."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        mock_resp = _make_mock_response({})
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert result.severity == "BLOCK"


class TestSecurityHeadersGateCaseInsensitive:
    """Tests for case-insensitive header name matching."""

    def test_headers_with_different_casing_pass(self):
        """Headers with different casing are matched case-insensitively."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        headers = {
            "content-security-policy": "default-src 'self'",
            "x-frame-options": "DENY",
            "x-content-type-options": "nosniff",
            "referrer-policy": "strict-origin-when-cross-origin",
        }
        mock_resp = _make_mock_response(headers)
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert result.passed is True

    def test_mixed_case_headers_pass(self):
        """Mixed case header names are still recognized."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        headers = {
            "CONTENT-SECURITY-POLICY": "default-src 'self'",
            "X-Frame-Options": "DENY",
            "x-content-type-options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }
        mock_resp = _make_mock_response(headers)
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert result.passed is True


class TestSecurityHeadersGateHSTS:
    """Tests for HSTS advisory handling."""

    def test_hsts_missing_but_required_present_pass(self):
        """HSTS missing but all 4 required headers present -> pass (advisory only)."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        headers_without_hsts = {
            "Content-Security-Policy": "default-src 'self'",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }
        mock_resp = _make_mock_response(headers_without_hsts)
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert result.passed is True

    def test_hsts_missing_generates_advisory(self):
        """HSTS missing -> advisory (not an issue) is generated."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        headers_without_hsts = {
            "Content-Security-Policy": "default-src 'self'",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }
        mock_resp = _make_mock_response(headers_without_hsts)
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert any("strict-transport-security" in adv.lower() or "hsts" in adv.lower() for adv in result.advisories)

    def test_hsts_present_no_advisory(self):
        """HSTS present -> no advisory for HSTS."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        mock_resp = _make_mock_response(ALL_REQUIRED_HEADERS)
        with patch("httpx.get", return_value=mock_resp):
            result = run_security_headers_gate("https://example.com")

        assert result.advisories == []


class TestSecurityHeadersGateRequestError:
    """Tests for httpx request error handling."""

    def test_request_error_returns_passed_false(self):
        """httpx.RequestError -> passed=False."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        with patch("httpx.get", side_effect=httpx.RequestError("Connection refused")):
            result = run_security_headers_gate("https://example.com")

        assert result.passed is False

    def test_request_error_has_issue(self):
        """httpx.RequestError -> issues list is non-empty."""
        from tools.gates.security_headers_gate import run_security_headers_gate

        with patch("httpx.get", side_effect=httpx.RequestError("Connection refused")):
            result = run_security_headers_gate("https://example.com")

        assert len(result.issues) > 0
