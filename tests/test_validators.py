"""Comprehensive unit tests for URL normalization and SSRF protection."""

import socket
from unittest.mock import patch

import pytest

from auditpilot.validators import is_safe_url, normalize_url


class TestNormalizeUrl:
    """Test suite for normalize_url."""

    def test_adds_https_when_scheme_missing(self) -> None:
        assert normalize_url("cynbit.in") == "https://cynbit.in"
        assert normalize_url("example.com/about") == "https://example.com/about"

    def test_normalizes_casing(self) -> None:
        assert normalize_url("HTTP://EXAMPLE.COM") == "http://example.com"
        assert normalize_url("HTTPS://CynBit.In/Path") == "https://cynbit.in/Path"

    def test_strips_trailing_slash_on_root_only(self) -> None:
        assert normalize_url("https://example.com/") == "https://example.com"
        assert normalize_url("https://example.com/services/") == "https://example.com/services/"

    def test_strips_fragments(self) -> None:
        assert normalize_url("https://example.com/page#overview") == "https://example.com/page"

    def test_strips_user_credentials(self) -> None:
        assert (
            normalize_url("https://admin:secret@example.com/dashboard")
            == "https://example.com/dashboard"
        )

    def test_collapses_consecutive_slashes(self) -> None:
        assert normalize_url("https://example.com//blog///post") == "https://example.com/blog/post"

    def test_rejects_empty_or_invalid_inputs(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            normalize_url("")
        with pytest.raises(ValueError, match="non-empty string"):
            normalize_url(None)  # type: ignore

    def test_rejects_unsupported_schemes(self) -> None:
        with pytest.raises(ValueError, match="Only http and https are supported"):
            normalize_url("ftp://ftp.example.com")
        with pytest.raises(ValueError, match="Only http and https are supported"):
            normalize_url("file:///etc/passwd")


class TestIsSafeUrl:
    """Test suite for SSRF protection in is_safe_url."""

    def test_rejects_literal_localhost(self) -> None:
        safe, reason = is_safe_url("http://localhost:8000")
        assert not safe
        assert "Blocked target hostname" in reason

        safe, reason = is_safe_url("http://127.0.0.1")
        assert not safe
        assert "Loopback" in reason or "Blocked target hostname" in reason

        safe, reason = is_safe_url("http://[::1]")
        assert not safe
        assert "Loopback" in reason or "Blocked target hostname" in reason

    def test_rejects_private_rf1918_ips(self) -> None:
        safe, reason = is_safe_url("http://10.0.0.1/admin")
        assert not safe
        assert "private network" in reason.lower()

        safe, reason = is_safe_url("https://192.168.1.100")
        assert not safe
        assert "private network" in reason.lower()

        safe, reason = is_safe_url("http://172.16.0.1")
        assert not safe
        assert "private network" in reason.lower()

    def test_rejects_cloud_metadata_ips(self) -> None:
        safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data")
        assert not safe
        assert "metadata" in reason.lower()

    def test_rejects_blocked_hostnames(self) -> None:
        safe, reason = is_safe_url("http://metadata.google.internal")
        assert not safe
        assert "Blocked target hostname" in reason

    def test_rejects_domain_resolving_to_private_ip(self) -> None:
        # Mock DNS resolution to simulate a DNS rebinding / malicious domain pointing to 127.0.0.1
        mock_addr = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 80))
        ]
        with patch("socket.getaddrinfo", return_value=mock_addr):
            safe, reason = is_safe_url("https://malicious-local-redirect.com")
            assert not safe
            assert "Loopback" in reason

    def test_accepts_domain_resolving_to_public_ip(self) -> None:
        mock_addr = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443))
        ]
        with patch("socket.getaddrinfo", return_value=mock_addr):
            safe, reason = is_safe_url("https://example.com")
            assert safe
            assert "safe" in reason.lower()

    def test_handles_dns_resolution_failure(self) -> None:
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("Name or service not known")):
            safe, reason = is_safe_url("https://non-existent-domain-123456789.com")
            assert not safe
            assert "DNS resolution failed" in reason
