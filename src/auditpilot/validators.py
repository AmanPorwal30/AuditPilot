"""URL validation and SSRF protection module for AuditPilot.

Ensures requested URLs are valid HTTP/HTTPS endpoints and protects against
Server-Side Request Forgery (SSRF) by validating hostnames and resolved IP addresses.
"""

import ipaddress
import re
import socket
from urllib.parse import urlsplit, urlunsplit

BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "metadata.google.internal",
    "instance-data",
}

CLOUD_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),  # AWS/GCP/Azure IMDS
    ipaddress.ip_address("169.254.169.253"),  # DNS/NTP services
}


def normalize_url(url: str) -> str:
    """Normalize input URL (adds scheme if missing, strips fragments, cleans path).

    Args:
        url: The user-supplied URL.

    Returns:
        Clean, normalized URL string.

    Raises:
        ValueError: If the URL is syntactically invalid or non-HTTP/HTTPS.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")

    cleaned_url = url.strip()

    # If scheme is omitted, prepend https://
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", cleaned_url):
        cleaned_url = f"https://{cleaned_url}"

    parsed = urlsplit(cleaned_url)

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(
            f"Invalid URL scheme '{parsed.scheme}'. Only http and https are supported."
        )

    netloc = parsed.netloc.lower()
    if not netloc:
        raise ValueError("URL must include a valid host.")

    # Strip user credentials if present (user:pass@host -> host)
    if "@" in netloc:
        netloc = netloc.split("@")[-1]

    # Normalize path: collapse duplicate slashes and strip trailing slash on root
    path = parsed.path
    if path:
        path = re.sub(r"/{2,}", "/", path)
        if path == "/":
            path = ""
    else:
        path = ""

    # Clear fragment and reassemble
    normalized = urlunsplit((scheme, netloc, path, parsed.query, ""))
    return normalized


def is_safe_url(url: str) -> tuple[bool, str]:
    """Validate URL for SSRF vulnerabilities before any network request.

    Rejects:
      - Non-http/https schemes
      - Localhost, 127.0.0.1, ::1, 0.0.0.0
      - RFC 1918 private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
      - Link-local and cloud metadata IPs (169.254.0.0/16 including 169.254.169.254)
      - Broadcast/multicast/reserved addresses

    Args:
        url: The target URL to test.

    Returns:
        Tuple of (is_safe: bool, reason: str).
    """
    try:
        norm_url = normalize_url(url)
    except ValueError as e:
        return False, f"Invalid URL: {e}"

    parsed = urlsplit(norm_url)
    hostname = parsed.hostname

    if not hostname:
        return False, "URL contains no hostname."

    hostname_lower = hostname.lower()

    # Reject known literal localhost/metadata hostnames
    if hostname_lower in BLOCKED_HOSTNAMES:
        return False, f"Blocked target hostname: {hostname}"

    # Handle IP addresses or domain names
    try:
        # Check if hostname itself is an IP literal
        ip = ipaddress.ip_address(hostname_lower)
        ips_to_check = [ip]
    except ValueError:
        # Hostname is a domain name -> resolve via DNS
        try:
            addr_info = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
            ips_to_check = []
            for item in addr_info:
                ip_str = item[4][0]
                ips_to_check.append(ipaddress.ip_address(ip_str))
        except socket.gaierror as e:
            return False, f"DNS resolution failed for '{hostname}': {e}"
        except Exception as e:
            return False, f"Resolution error for '{hostname}': {e}"

    if not ips_to_check:
        return False, f"No IP addresses resolved for '{hostname}'."

    # Validate each resolved IP address against SSRF boundaries
    for ip in ips_to_check:
        if ip in CLOUD_METADATA_IPS:
            return False, f"SSRF blocked: Cloud metadata service IP ({ip})."
        if ip.is_loopback:
            return False, f"SSRF blocked: Loopback address ({ip})."
        if ip.is_private:
            return False, f"SSRF blocked: RFC 1918 private network IP ({ip})."
        if ip.is_link_local:
            return False, f"SSRF blocked: Link-local IP ({ip})."
        if ip.is_multicast:
            return False, f"SSRF blocked: Multicast address ({ip})."
        if ip.is_reserved:
            return False, f"SSRF blocked: Reserved IP ({ip})."
        if ip.is_unspecified:
            return False, f"SSRF blocked: Unspecified IP ({ip})."

    return True, "URL is safe for crawling."
