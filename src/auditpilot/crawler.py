"""Asynchronous website crawler for AuditPilot.

Performs polite, breadth-first crawling bounded by domain and page limit.
Respects robots.txt directives, discovers XML sitemaps, and enforces SSRF guards.
"""

import asyncio
import logging
import re
import time
import xml.etree.ElementTree as ET
from collections import deque
from collections.abc import AsyncGenerator
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from auditpilot.config import settings
from auditpilot.models import PageData, SiteSignals
from auditpilot.validators import is_safe_url, normalize_url

logger = logging.getLogger(__name__)


def _get_root_domain(host: str) -> str:
    """Extract root domain without external network lookups."""
    host = host.split(":")[0].lower()
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    second_level_tlds = {
        "co.uk",
        "org.uk",
        "gov.uk",
        "co.in",
        "net.in",
        "org.in",
        "gen.in",
        "firm.in",
        "ind.in",
        "com.au",
        "net.au",
        "org.au",
    }
    last_two = ".".join(parts[-2:])
    if last_two in second_level_tlds and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


class AsyncCrawler:
    """Async crawler with concurrency throttling and robots.txt support."""

    def __init__(
        self,
        base_url: str,
        max_pages: int = 25,
        concurrency: int = 5,
        delay_seconds: float = 0.4,
        timeout_seconds: float = 10.0,
        user_agent: str | None = None,
    ) -> None:
        """Initialize crawler parameters."""
        self.base_url = normalize_url(base_url)
        self.max_pages = min(max_pages, settings.MAX_PAGES_CAP)
        self.concurrency = concurrency
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent or settings.USER_AGENT

        parsed = urlsplit(self.base_url)
        self.base_netloc = parsed.netloc.lower()
        self.base_scheme = parsed.scheme.lower()
        self.registered_domain = _get_root_domain(self.base_netloc)

        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._robot_parser: RobotFileParser | None = None
        self._sitemap_urls: list[str] = []
        self._visited: set[str] = set()
        self.site_signals = SiteSignals()

    def _is_same_domain(self, url: str) -> bool:
        """Check if target URL belongs to the same domain as base_url."""
        try:
            parsed = urlsplit(url)
            netloc = parsed.netloc.lower()
            if not netloc:
                return False
            if netloc == self.base_netloc:
                return True
            return _get_root_domain(netloc) == self.registered_domain
        except Exception:
            return False

    async def _init_robots(self, client: httpx.AsyncClient) -> None:
        """Fetch and parse robots.txt for the domain."""
        robots_url = f"{self.base_scheme}://{self.base_netloc}/robots.txt"
        self._robot_parser = RobotFileParser()
        self._robot_parser.set_url(robots_url)

        is_safe, _ = is_safe_url(robots_url)
        if not is_safe:
            return

        try:
            response = await client.get(robots_url, timeout=self.timeout_seconds)
            if response.status_code == 200:
                lines = response.text.splitlines()
                self._robot_parser.parse(lines)
                directive_re = re.compile(r"^[A-Za-z-]+\s*:")
                directives = 0
                malformed = 0
                has_user_agent = False
                for line in lines:
                    line_clean = line.split("#", 1)[0].strip()
                    if not line_clean:
                        continue
                    if directive_re.match(line_clean):
                        directives += 1
                        if line_clean.lower().startswith("user-agent"):
                            has_user_agent = True
                    else:
                        malformed += 1
                    if line_clean.lower().startswith("sitemap:"):
                        sitemap_candidate = line_clean[8:].strip()
                        if sitemap_candidate:
                            self._sitemap_urls.append(sitemap_candidate)
                self.site_signals.robots_found = True
                self.site_signals.robots_directive_count = directives
                self.site_signals.robots_valid = has_user_agent and malformed == 0
                self.site_signals.robots_blocks_all = not self._robot_parser.can_fetch(
                    "*", f"{self.base_scheme}://{self.base_netloc}/"
                )
            else:
                self.site_signals.robots_found = (
                    False if response.status_code in (404, 410) else None
                )
                self._robot_parser.allow_all = True
        except Exception as e:
            logger.warning(f"Could not fetch robots.txt for {self.base_netloc}: {e}")
            self._robot_parser.allow_all = True

    async def _fetch_sitemap_urls(self, client: httpx.AsyncClient) -> list[str]:
        """Fetch and parse XML sitemaps (including sitemap index)."""
        candidate_sitemaps = list(self._sitemap_urls)
        default_sitemap = f"{self.base_scheme}://{self.base_netloc}/sitemap.xml"
        if default_sitemap not in candidate_sitemaps:
            candidate_sitemaps.append(default_sitemap)

        extracted_urls: list[str] = []
        sig = self.site_signals
        any_response = False

        for sitemap_url in candidate_sitemaps:
            is_safe, _ = is_safe_url(sitemap_url)
            if not is_safe:
                continue

            try:
                resp = await client.get(sitemap_url, timeout=self.timeout_seconds)
                any_response = True
                if resp.status_code != 200:
                    continue

                xml_content = resp.text
                if sig.sitemap_url is None:
                    sig.sitemap_url = sitemap_url
                    sig.sitemap_found = True
                    sig.sitemap_valid = False
                # Reject entity declarations (XML entity-expansion DoS) before parsing.
                if "<!DOCTYPE" in xml_content or "<!ENTITY" in xml_content:
                    continue
                root = ET.fromstring(xml_content)
                if sitemap_url == sig.sitemap_url:
                    sig.sitemap_valid = root.tag.endswith(("urlset", "sitemapindex"))

                for loc in root.findall(".//{*}loc"):
                    loc_text = loc.text.strip() if loc.text else ""
                    if not loc_text:
                        continue
                    if loc_text.endswith(".xml") and loc_text not in candidate_sitemaps:
                        candidate_sitemaps.append(loc_text)
                    elif self._is_same_domain(loc_text):
                        try:
                            norm = normalize_url(loc_text)
                            extracted_urls.append(norm)
                        except ValueError:
                            pass
            except Exception as e:
                logger.debug(f"Failed to parse sitemap {sitemap_url}: {e}")

        unique = list(dict.fromkeys(extracted_urls))
        sig.sitemap_url_count = len(unique)
        if sig.sitemap_found is None and any_response:
            sig.sitemap_found = False
        return unique

    async def _probe_https_redirect(self, client: httpx.AsyncClient) -> None:
        """Check whether the plain-HTTP origin redirects to HTTPS."""
        if self.base_scheme != "https":
            return
        http_url = f"http://{self.base_netloc}/"
        is_safe, _ = is_safe_url(http_url)
        if not is_safe:
            return
        try:
            resp = await client.get(http_url, timeout=self.timeout_seconds, follow_redirects=False)
            location = resp.headers.get("location", "")
            self.site_signals.http_redirects_to_https = resp.status_code in (
                301,
                302,
                307,
                308,
            ) and location.lower().startswith("https://")
        except Exception as e:
            logger.debug(f"HTTP->HTTPS probe failed for {self.base_netloc}: {e}")

    def _can_fetch(self, url: str) -> bool:
        """Check if robots.txt allows fetching this URL."""
        if self._robot_parser is None:
            return True
        try:
            return self._robot_parser.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def _extract_links(self, current_url: str, html: str) -> list[str]:
        """Extract same-domain hyperlinks from HTML payload."""
        links: list[str] = []
        try:
            soup = BeautifulSoup(html, "lxml")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                joined = urljoin(current_url, href)
                try:
                    norm = normalize_url(joined)
                    if self._is_same_domain(norm):
                        links.append(norm)
                except ValueError:
                    continue
        except Exception as e:
            logger.debug(f"Link extraction error on {current_url}: {e}")
        return links

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> PageData | None:
        """Fetch a single page with retries, timeout, and timing metrics."""
        is_safe, reason = is_safe_url(url)
        if not is_safe:
            logger.warning(f"Skipping unsafe URL {url}: {reason}")
            return None

        if not self._can_fetch(url):
            logger.info(f"URL {url} blocked by robots.txt")
            self.site_signals.urls_blocked_by_robots.append(url)
            return None

        async with self._semaphore:
            if self.delay_seconds > 0:
                await asyncio.sleep(self.delay_seconds)

            start_time = time.perf_counter()
            response: httpx.Response | None = None

            # Retry once on transport error
            for attempt in range(2):
                try:
                    response = await client.get(
                        url,
                        timeout=self.timeout_seconds,
                        follow_redirects=True,
                    )
                    break
                except (httpx.TransportError, httpx.TimeoutException) as e:
                    if attempt == 1:
                        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                        logger.warning(f"Request failed for {url} after retry: {e}")
                        return PageData(
                            url=url,
                            status_code=0,
                            final_url=url,
                            response_time_ms=elapsed_ms,
                            html_size_bytes=0,
                        )
                    await asyncio.sleep(0.5)

            if response is None:
                return None

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            content_type = response.headers.get("content-type", "").lower()
            is_html = "text/html" in content_type or "application/xhtml+xml" in content_type

            redirect_chain = [str(r.url) for r in response.history]
            final_url = str(response.url)
            raw_html = response.text if is_html else None
            html_size = len(response.content)

            from auditpilot.parsers import parse_page_html

            return parse_page_html(
                url=url,
                html=raw_html,
                status_code=response.status_code,
                final_url=final_url,
                redirect_chain=redirect_chain,
                response_time_ms=elapsed_ms,
                html_size_bytes=html_size,
                headers=dict(response.headers),
            )

    async def crawl(
        self, client: httpx.AsyncClient | None = None
    ) -> AsyncGenerator[PageData, None]:
        """Perform breadth-first crawl yielding PageData objects.

        Args:
            client: Optional httpx.AsyncClient for dependency injection / mock testing.

        Yields:
            PageData object for each visited page.
        """
        queue: deque[str] = deque([self.base_url])
        self._visited = {self.base_url}

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        # If a client is passed in (e.g. from tests or caller), reuse it; otherwise create one
        if client is not None:
            async for page in self._crawl_with_client(client, queue):
                yield page
        else:
            async with httpx.AsyncClient(headers=headers, verify=True) as new_client:
                async for page in self._crawl_with_client(new_client, queue):
                    yield page

    async def _crawl_with_client(
        self, client: httpx.AsyncClient, queue: deque[str]
    ) -> AsyncGenerator[PageData, None]:
        """Internal crawl execution with given active client."""
        # 1. Fetch and initialize robots.txt
        await self._init_robots(client)

        # 2. Discover sitemap URLs and queue valid pages
        sitemap_discovered = await self._fetch_sitemap_urls(client)
        await self._probe_https_redirect(client)
        for sm_url in sitemap_discovered:
            if sm_url not in self._visited and len(self._visited) < self.max_pages * 2:
                queue.append(sm_url)

        # 3. BFS crawl loop
        crawled_count = 0
        while queue and crawled_count < self.max_pages:
            current_url = queue.popleft()

            page_data = await self._fetch_page(client, current_url)
            if page_data is None:
                continue

            crawled_count += 1
            yield page_data

            # Discover outbound same-domain links if page is HTML and returned 200
            if page_data.raw_html and page_data.status_code == 200:
                found_links = self._extract_links(page_data.final_url, page_data.raw_html)
                for link in found_links:
                    if link not in self._visited and len(self._visited) < self.max_pages * 3:
                        self._visited.add(link)
                        queue.append(link)
