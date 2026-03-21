"""Tests for tools/gates/deployment_gate.py.

Covers:
- run_deployment_gate(url, phase_id="3") returns GateResult with gate_type="deployment"
- HTTP 200 response -> passed=True
- Non-200 response -> passed=False with issue
- httpx.RequestError -> passed=False with descriptive issue
- timeout defaults to 30 seconds
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tools.gates.gate_result import GateResult


class TestRunDeploymentGatePass:
    """Tests for successful HTTP 200 case."""

    def test_returns_gate_result_instance(self):
        """run_deployment_gate must return a GateResult."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=200)

        with patch("httpx.get", return_value=mock_response):
            result = run_deployment_gate("https://example.vercel.app")

        assert isinstance(result, GateResult)

    def test_passed_true_on_200(self):
        """HTTP 200 response -> passed=True."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=200)

        with patch("httpx.get", return_value=mock_response):
            result = run_deployment_gate("https://example.vercel.app")

        assert result.passed is True

    def test_status_pass_on_200(self):
        """HTTP 200 -> status='PASS'."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=200)

        with patch("httpx.get", return_value=mock_response):
            result = run_deployment_gate("https://example.vercel.app")

        assert result.status == "PASS"

    def test_severity_info_on_200(self):
        """HTTP 200 -> severity='INFO'."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=200)

        with patch("httpx.get", return_value=mock_response):
            result = run_deployment_gate("https://example.vercel.app")

        assert result.severity == "INFO"

    def test_confidence_1_on_200(self):
        """HTTP 200 -> confidence=1.0."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=200)

        with patch("httpx.get", return_value=mock_response):
            result = run_deployment_gate("https://example.vercel.app")

        assert result.confidence == 1.0

    def test_no_issues_on_200(self):
        """HTTP 200 -> issues is empty list."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=200)

        with patch("httpx.get", return_value=mock_response):
            result = run_deployment_gate("https://example.vercel.app")

        assert result.issues == []

    def test_gate_type_is_deployment(self):
        """gate_type must be 'deployment'."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=200)

        with patch("httpx.get", return_value=mock_response):
            result = run_deployment_gate("https://example.vercel.app")

        assert result.gate_type == "deployment"

    def test_default_phase_id_is_3(self):
        """Default phase_id should be '3'."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=200)

        with patch("httpx.get", return_value=mock_response):
            result = run_deployment_gate("https://example.vercel.app")

        assert result.phase_id == "3"

    def test_custom_phase_id_preserved(self):
        """Custom phase_id is reflected in result."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=200)

        with patch("httpx.get", return_value=mock_response):
            result = run_deployment_gate("https://example.vercel.app", phase_id="3+")

        assert result.phase_id == "3+"

    def test_checked_at_is_populated(self):
        """checked_at must be a non-empty string."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=200)

        with patch("httpx.get", return_value=mock_response):
            result = run_deployment_gate("https://example.vercel.app")

        assert isinstance(result.checked_at, str) and len(result.checked_at) > 0


class TestRunDeploymentGateNon200:
    """Tests for non-200 HTTP status codes."""

    def test_passed_false_on_500(self):
        """HTTP 500 -> passed=False."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=500)

        with patch("httpx.get", return_value=mock_response):
            result = run_deployment_gate("https://example.vercel.app")

        assert result.passed is False

    def test_issue_contains_status_code_on_non_200(self):
        """Non-200 response should include status code in issues."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=404)

        with patch("httpx.get", return_value=mock_response):
            result = run_deployment_gate("https://example.vercel.app")

        assert any("404" in issue for issue in result.issues)

    def test_passed_false_on_302(self):
        """Redirect (non-200) -> passed=False (follow_redirects=True means 302 resolved)."""
        from tools.gates.deployment_gate import run_deployment_gate

        # After following redirects, result is a non-200 error
        mock_response = MagicMock(status_code=503)

        with patch("httpx.get", return_value=mock_response):
            result = run_deployment_gate("https://example.vercel.app")

        assert result.passed is False

    def test_gate_type_is_deployment_on_failure(self):
        """gate_type remains 'deployment' on failure."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=500)

        with patch("httpx.get", return_value=mock_response):
            result = run_deployment_gate("https://example.vercel.app")

        assert result.gate_type == "deployment"


class TestRunDeploymentGateRequestError:
    """Tests for httpx.RequestError handling."""

    def test_passed_false_on_request_error(self):
        """httpx.RequestError -> passed=False."""
        import httpx
        from tools.gates.deployment_gate import run_deployment_gate

        with patch("httpx.get", side_effect=httpx.RequestError("Connection refused")):
            result = run_deployment_gate("https://example.vercel.app")

        assert result.passed is False

    def test_issue_contains_error_description(self):
        """httpx.RequestError -> descriptive message in issues."""
        import httpx
        from tools.gates.deployment_gate import run_deployment_gate

        with patch("httpx.get", side_effect=httpx.RequestError("Connection refused")):
            result = run_deployment_gate("https://example.vercel.app")

        assert len(result.issues) > 0
        # Issue should mention connection/request/error context
        issue_text = " ".join(result.issues).lower()
        assert any(term in issue_text for term in ["error", "connection", "request", "reach"])

    def test_gate_type_is_deployment_on_request_error(self):
        """gate_type remains 'deployment' on RequestError."""
        import httpx
        from tools.gates.deployment_gate import run_deployment_gate

        with patch("httpx.get", side_effect=httpx.RequestError("timeout")):
            result = run_deployment_gate("https://example.vercel.app")

        assert result.gate_type == "deployment"


class TestRunDeploymentGateHttpxCallArgs:
    """Tests that httpx.get is called with correct arguments."""

    def test_follow_redirects_true(self):
        """httpx.get must be called with follow_redirects=True."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=200)

        with patch("httpx.get", return_value=mock_response) as mock_get:
            run_deployment_gate("https://example.vercel.app")

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs.get("follow_redirects") is True

    def test_timeout_defaults_to_30(self):
        """httpx.get must be called with timeout=30 by default."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=200)

        with patch("httpx.get", return_value=mock_response) as mock_get:
            run_deployment_gate("https://example.vercel.app")

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs.get("timeout") == 30

    def test_url_passed_correctly(self):
        """httpx.get is called with the URL as first positional arg."""
        from tools.gates.deployment_gate import run_deployment_gate

        mock_response = MagicMock(status_code=200)

        with patch("httpx.get", return_value=mock_response) as mock_get:
            run_deployment_gate("https://my-app.vercel.app")

        call_args = mock_get.call_args[0]
        assert call_args[0] == "https://my-app.vercel.app"
