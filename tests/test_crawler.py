"""Comprehensive unit tests for AsyncCrawler with mocked network responses."""

import socket
from unittest.mock import patch

import httpx
import pytest

from auditpilot.crawler import AsyncCrawler
from auditpilot.models import PageData


class TestAsyncCrawlerUnit:
    """Unit tests for crawler utility methods."""

    def test_same_domain_matching(self) -> None:
        crawler = AsyncCrawler("https://cynbit.in")
        assert crawler._is_same_domain("https://cynbit.in/about")
        assert crawler._is_same_domain("https://www.cynbit.in/services")
        assert crawler._is_same_domain("https://blog.cynbit.in/post-1")
        assert not crawler._is_same_domain("https://google.com")
        assert not crawler._is_same_domain("https://cynbit.org")

    def test_extract_links_filters_and_normalizes(self) -> None:
        crawler = AsyncCrawler("https://example.com")
        html = """
        <html>
            <body>
                <a href="/about">About Us</a>
                <a href="https://example.com/contact">Contact</a>
                <a href="#section">Fragment</a>
                <a href="mailto:test@example.com">Email</a>
                <a href="javascript:void(0)">JS</a>
                <a href="https://external.com/partner">External</a>
            </body>
        </html>
        """
        links = crawler._extract_links("https://example.com", html)
        assert "https://example.com/about" in links
        assert "https://example.com/contact" in links
        assert not any("external.com" in link for link in links)
        assert not any("#section" in link for link in links)
        assert not any("mailto:" in link for link in links)


@pytest.mark.asyncio
class TestAsyncCrawlerExecution:
    """Integration-style tests for crawler lifecycle with mocked transport."""

    async def test_crawler_full_lifecycle_with_mocks(self) -> None:
        base_url = "https://example.com"
        mock_public_ip = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443))
        ]

        robots_content = """User-agent: *
Disallow: /admin
Sitemap: https://example.com/sitemap.xml
"""
        sitemap_content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://example.com/sitemap-page</loc></url>
</urlset>
"""
        home_html = """<html><body>
            <h1>Home</h1>
            <a href="/page-1">Page 1</a>
            <a href="/admin/secret">Admin (Disallowed)</a>
        </body></html>"""

        page1_html = """<html><body><h1>Page 1</h1></body></html>"""
        sitemap_page_html = """<html><body><h1>Sitemap Page</h1></body></html>"""

        async def mock_get_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if url_str == "https://example.com/robots.txt":
                return httpx.Response(200, text=robots_content, request=request)
            elif url_str == "https://example.com/sitemap.xml":
                return httpx.Response(200, text=sitemap_content, request=request)
            elif url_str == "https://example.com":
                return httpx.Response(
                    200,
                    text=home_html,
                    headers={"content-type": "text/html; charset=utf-8"},
                    request=request,
                )
            elif url_str == "https://example.com/page-1":
                return httpx.Response(
                    200,
                    text=page1_html,
                    headers={"content-type": "text/html; charset=utf-8"},
                    request=request,
                )
            elif url_str == "https://example.com/sitemap-page":
                return httpx.Response(
                    200,
                    text=sitemap_page_html,
                    headers={"content-type": "text/html; charset=utf-8"},
                    request=request,
                )
            elif "/admin" in url_str:
                return httpx.Response(200, text="Secret Admin", request=request)
            return httpx.Response(404, text="Not Found", request=request)

        mock_transport = httpx.MockTransport(mock_get_handler)

        with patch("socket.getaddrinfo", return_value=mock_public_ip):
            async with httpx.AsyncClient(transport=mock_transport) as mock_client:
                crawler = AsyncCrawler(base_url, max_pages=10, delay_seconds=0.0)
                pages: list[PageData] = []
                async for page in crawler.crawl(client=mock_client):
                    pages.append(page)

                crawled_urls = [p.url for p in pages]

                # Verify homepage, page-1, and sitemap-page were crawled
                assert "https://example.com" in crawled_urls
                assert "https://example.com/page-1" in crawled_urls
                assert "https://example.com/sitemap-page" in crawled_urls

                # Verify robots.txt disallowed path was NOT crawled
                assert not any("/admin" in u for u in crawled_urls)

                # Verify PageData attributes
                for p in pages:
                    assert p.status_code == 200
                    assert p.response_time_ms >= 0.0
                    assert p.raw_html is not None

    async def test_crawler_handles_retry_on_network_error(self) -> None:
        base_url = "https://example.com"
        mock_public_ip = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443))
        ]

        call_count = 0

        async def failing_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if str(request.url) == "https://example.com/robots.txt":
                return httpx.Response(404, request=request)
            if call_count == 2:  # First attempt at homepage fails
                raise httpx.ConnectError("Simulated socket timeout", request=request)
            # Second attempt succeeds
            return httpx.Response(
                200,
                text="<html>Success</html>",
                headers={"content-type": "text/html"},
                request=request,
            )

        mock_transport = httpx.MockTransport(failing_handler)

        with patch("socket.getaddrinfo", return_value=mock_public_ip):
            async with httpx.AsyncClient(transport=mock_transport) as mock_client:
                crawler = AsyncCrawler(base_url, max_pages=1, delay_seconds=0.0)
                pages: list[PageData] = []
                async for page in crawler.crawl(client=mock_client):
                    pages.append(page)

                assert len(pages) == 1
                assert pages[0].status_code == 200
                assert pages[0].raw_html == "<html>Success</html>"
