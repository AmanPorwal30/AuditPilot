"""Evidence-based scoring engine for AuditPilot.

100-point, 8-category model. Every check either measures something observed in the
crawl or is reported as ``not_tested`` / ``not_applicable``. Those two statuses are
excluded from the score and lower coverage/confidence, so a check that cannot be
verified never adds or removes points. Critical issue caps are applied last.
"""

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import combinations
from statistics import fmean
from typing import Any
from urllib.parse import urlsplit

import textstat

from auditpilot.config import AUDIT_THRESHOLDS
from auditpilot.models import AuditScore, CategoryScore, Finding, PageData, SiteSignals
from auditpilot.parsers import STOPWORDS

CATEGORY_WEIGHTS: dict[str, dict[str, Any]] = {
    "availability": {"name": "Availability & Reliability", "weight": 10.0},
    "seo": {"name": "SEO", "weight": 15.0},
    "performance": {"name": "Performance", "weight": 15.0},
    "ui_ux": {"name": "UI/UX & Navigation", "weight": 15.0},
    "content": {"name": "Content Quality", "weight": 15.0},
    "functionality": {"name": "Functionality", "weight": 15.0},
    "security": {"name": "Security", "weight": 5.0},
    "accessibility": {"name": "Accessibility", "weight": 10.0},
}

LEGACY_CATEGORIES: dict[str, dict[str, Any]] = {
    "technical": {"name": "Technical SEO", "weight": 0.35},
    "onpage": {"name": "On-Page SEO", "weight": 0.30},
    "content": {"name": "Content Quality", "weight": 0.20},
    "performance": {"name": "Performance", "weight": 0.15},
}

SKIPPED_STATUSES = ("not_tested", "not_applicable")


def _get_rating_band(score: float, is_assessable: bool = True) -> str:
    """Map numeric 0-100 score to quality rating band."""
    if not is_assessable:
        return "Not assessable"
    if score >= 90.0:
        return "Excellent"
    if score >= 80.0:
        return "Very Good"
    if score >= 70.0:
        return "Good"
    if score >= 60.0:
        return "Average"
    if score >= 40.0:
        return "Needs Improvement"
    if score >= 20.0:
        return "Poor"
    return "Critical"


def _get_letter_grade(score: float, is_assessable: bool = True) -> str:
    """Map numeric score to traditional letter grade."""
    if not is_assessable:
        return "N/A"
    if score > 90.0:
        return "A"
    if score >= 80.0:
        return "B"
    if score >= 70.0:
        return "C"
    if score >= 60.0:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Check plumbing
# ---------------------------------------------------------------------------


def _norm(url: str) -> str:
    return url.split("#", 1)[0].rstrip("/").lower()


def _host(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


@dataclass
class _Ctx:
    pages: list[PageData]
    target_url: str
    keywords: list[str]
    site: SiteSignals | None
    cfg: dict[str, Any]
    home: PageData = field(init=False)
    ok: list[PageData] = field(init=False)
    linked: set[str] = field(init=False)

    def __post_init__(self) -> None:
        self.home = self.pages[0]
        self.ok = [p for p in self.pages if p.status_code == 200 and p.raw_html]
        self.linked = {_norm(link) for p in self.pages for link in p.internal_links}

    @property
    def home_ok(self) -> bool:
        return any(p is self.home for p in self.ok)

    @property
    def is_single_page(self) -> bool:
        return len(self.ok) < 2


@dataclass(frozen=True)
class _Spec:
    check_id: str
    category: str
    max_points: float

    def score(
        self,
        earned: float,
        message: str,
        *,
        severity: str = "medium",
        impact: str = "medium",
        urls: list[str] | None = None,
        evidence: dict[str, Any] | None = None,
        recommendation: str = "",
    ) -> Finding:
        earned = max(0.0, min(self.max_points, earned))
        ratio = earned / self.max_points
        status = "pass" if ratio >= 0.999 else ("fail" if ratio <= 0.001 else "partial")
        return Finding(
            check_id=self.check_id,
            category=self.category,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            points_earned=round(earned, 2),
            max_points=self.max_points,
            severity=severity,  # type: ignore[arg-type]
            impact=impact,  # type: ignore[arg-type]
            passed=status == "pass",
            message=message,
            affected_urls=(urls or [])[:10],
            evidence=evidence or {},
            recommendation=recommendation,
        )

    def skip(
        self,
        status: str,
        message: str,
        *,
        evidence: dict[str, Any] | None = None,
        recommendation: str = "",
    ) -> Finding:
        return Finding(
            check_id=self.check_id,
            category=self.category,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            points_earned=0.0,
            max_points=self.max_points,
            severity="info",
            impact="low",
            passed=True,
            message=message,
            evidence=evidence or {},
            recommendation=recommendation,
        )


_CheckFn = Callable[[_Ctx, _Spec], Finding]
_REGISTRY: list[tuple[_Spec, bool, _CheckFn]] = []


def _check(
    check_id: str, category: str, max_points: float, needs_pages: bool = True
) -> Callable[[_CheckFn], _CheckFn]:
    def register(fn: _CheckFn) -> _CheckFn:
        _REGISTRY.append((_Spec(check_id, category, max_points), needs_pages, fn))
        return fn

    return register


def _len_quality(text: str | None, lo: int, hi: int) -> float:
    n = len((text or "").strip())
    if n == 0:
        return 0.0
    return 1.0 if lo <= n <= hi else 0.5


def _jaccard(a: set[Any], b: set[Any]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def _shingles(text: str, k: int = 5) -> set[int]:
    words = text.lower().split()[:3000]
    return {hash(" ".join(words[i : i + k])) for i in range(max(0, len(words) - k + 1))}


# ---------------------------------------------------------------------------
# 1. AVAILABILITY & RELIABILITY (10)
# ---------------------------------------------------------------------------


@_check("AV01", "availability", 2.0, needs_pages=False)
def _av01(c: _Ctx, s: _Spec) -> Finding:
    reachable = c.home.status_code != 0
    return s.score(
        2.0 if reachable else 0.0,
        "The server accepted a connection and returned a response."
        if reachable
        else "No response: DNS, TLS, connection refusal or timeout.",
        severity="critical",
        impact="high",
        urls=[] if reachable else [c.home.url],
        evidence={"status_code": c.home.status_code, "final_url": c.home.final_url},
        recommendation="Verify DNS records, TLS certificate and that the origin is deployed.",
    )


@_check("AV02", "availability", 3.0, needs_pages=False)
def _av02(c: _Ctx, s: _Spec) -> Finding:
    code = c.home.status_code
    good = 200 <= code < 300
    return s.score(
        3.0 if good else 0.0,
        f"Homepage returned HTTP {code}.",
        severity="critical",
        impact="high",
        urls=[] if good else [c.home.url],
        evidence={"status_code": code},
        recommendation="Make the primary URL return HTTP 200 without errors.",
    )


@_check("AV03", "availability", 2.0, needs_pages=False)
def _av03(c: _Ctx, s: _Spec) -> Finding:
    https = c.home.final_url.lower().startswith("https://") and c.home.status_code != 0
    return s.score(
        2.0 if https else 0.0,
        "Homepage is served over HTTPS with a certificate that validated."
        if https
        else "Homepage is not served over HTTPS.",
        severity="critical",
        impact="high",
        urls=[] if https else [c.home.url],
        evidence={"final_url": c.home.final_url},
        recommendation="Install a valid TLS certificate and serve all pages over HTTPS.",
    )


@_check("AV04", "availability", 2.0, needs_pages=False)
def _av04(c: _Ctx, s: _Spec) -> Finding:
    errors = [p.url for p in c.pages if p.status_code >= 500]
    ratio = 1 - len(errors) / len(c.pages)
    return s.score(
        2.0 * ratio,
        f"{len(errors)} of {len(c.pages)} crawled pages returned a 5xx server error.",
        severity="critical" if errors else "medium",
        impact="high",
        urls=errors,
        evidence={"server_error_count": len(errors), "pages": len(c.pages)},
        recommendation="Inspect server logs and fix the failing handlers.",
    )


@_check("AV05", "availability", 1.0, needs_pages=False)
def _av05(c: _Ctx, s: _Spec) -> Finding:
    cfg = c.cfg["availability"]
    ms = c.home.response_time_ms
    pts = 1.0 if ms <= cfg["response_time_ok_ms"] else 0.5 if ms <= cfg["response_time_slow_ms"] else 0.0
    return s.score(
        pts,
        f"Homepage fetch completed in {ms:.0f} ms.",
        urls=[] if pts == 1.0 else [c.home.url],
        evidence={"response_time_ms": round(ms)},
        recommendation="Reduce server processing time and enable caching/CDN.",
    )


# ---------------------------------------------------------------------------
# 2. SEO (15)
# ---------------------------------------------------------------------------


@_check("SE01", "seo", 2.0)
def _se01(c: _Ctx, s: _Spec) -> Finding:
    cfg = c.cfg["seo"]
    quality = [_len_quality(p.title, cfg["title_min_chars"], cfg["title_max_chars"]) for p in c.ok]
    titles = [(p.title or "").strip().lower() for p in c.ok if p.title]
    unique_ratio = len(set(titles)) / len(titles) if titles else 1.0
    dups = [t for t, n in Counter(titles).items() if n > 1]
    in_range = sum(1 for q in quality if q == 1.0)
    return s.score(
        2.0 * fmean(quality) * unique_ratio,
        f"{in_range}/{len(c.ok)} pages have a title of {cfg['title_min_chars']}-"
        f"{cfg['title_max_chars']} chars; {len(dups)} duplicated title(s).",
        severity="high",
        impact="high",
        urls=[p.url for p, q in zip(c.ok, quality, strict=True) if q < 1.0],
        evidence={"in_range": in_range, "pages": len(c.ok), "duplicate_titles": dups[:5]},
        recommendation="Give every page a unique, descriptive title within the recommended length.",
    )


@_check("SE02", "seo", 2.0)
def _se02(c: _Ctx, s: _Spec) -> Finding:
    cfg = c.cfg["seo"]
    quality = [
        _len_quality(p.meta_description, cfg["meta_desc_min_chars"], cfg["meta_desc_max_chars"])
        for p in c.ok
    ]
    in_range = sum(1 for q in quality if q == 1.0)
    return s.score(
        2.0 * fmean(quality),
        f"{in_range}/{len(c.ok)} pages have a meta description of "
        f"{cfg['meta_desc_min_chars']}-{cfg['meta_desc_max_chars']} chars.",
        urls=[p.url for p, q in zip(c.ok, quality, strict=True) if q < 1.0],
        evidence={"in_range": in_range, "pages": len(c.ok)},
        recommendation="Write a unique meta description summarising each page.",
    )


def _heading_quality(p: PageData) -> float:
    h1 = len(p.h1s)
    q = 1.0 if h1 == 1 else 0.5 if h1 > 1 else 0.0
    levels = [lvl for lvl, _ in p.headings]
    if any(b - a > 1 for a, b in zip(levels, levels[1:], strict=False)):
        q *= 0.75
    return q


@_check("SE03", "seo", 2.0)
def _se03(c: _Ctx, s: _Spec) -> Finding:
    quality = [_heading_quality(p) for p in c.ok]
    good = sum(1 for q in quality if q == 1.0)
    return s.score(
        2.0 * fmean(quality),
        f"{good}/{len(c.ok)} pages have exactly one H1 and no skipped heading levels.",
        urls=[p.url for p, q in zip(c.ok, quality, strict=True) if q < 1.0],
        evidence={"clean_pages": good, "pages": len(c.ok)},
        recommendation="Use one H1 per page and nest headings without skipping levels.",
    )


@_check("SE04", "seo", 2.0)
def _se04(c: _Ctx, s: _Spec) -> Finding:
    home_types = c.home.json_ld_types if c.home_ok else []
    other_types = sorted({t for p in c.ok for t in p.json_ld_types})
    pts = 2.0 if home_types else 1.0 if other_types else 0.0
    return s.score(
        pts,
        f"Structured data found on homepage: {', '.join(home_types)}."
        if home_types
        else "Structured data found only on inner pages."
        if other_types
        else "No JSON-LD structured data found.",
        severity="low",
        impact="low",
        evidence={"homepage_types": home_types, "site_types": other_types[:8]},
        recommendation="Add JSON-LD (Organization/WebSite on the homepage, plus page-type schemas).",
    )


@_check("SE05", "seo", 2.0, needs_pages=False)
def _se05(c: _Ctx, s: _Spec) -> Finding:
    sig = c.site
    if sig is None or sig.sitemap_found is None:
        return s.skip(
            "not_tested", "Sitemap could not be checked (no site-level crawl data or no response)."
        )
    evidence = {"sitemap_url": sig.sitemap_url, "url_count": sig.sitemap_url_count}
    rec = "Publish a valid XML sitemap and reference it from robots.txt."
    if not sig.sitemap_found:
        return s.score(0.0, "No sitemap.xml found.", evidence=evidence, recommendation=rec)
    if not sig.sitemap_valid:
        return s.score(
            0.5, "A sitemap exists but is not valid XML.", evidence=evidence, recommendation=rec
        )
    if sig.sitemap_url_count == 0:
        return s.score(1.0, "Sitemap is valid but lists no URLs.", evidence=evidence, recommendation=rec)
    return s.score(
        2.0, f"Valid sitemap listing {sig.sitemap_url_count} URL(s).", evidence=evidence, recommendation=rec
    )


@_check("SE06", "seo", 1.0, needs_pages=False)
def _se06(c: _Ctx, s: _Spec) -> Finding:
    sig = c.site
    if sig is None or (sig.robots_found is None):
        return s.skip(
            "not_tested", "robots.txt could not be checked (no site-level crawl data or no response)."
        )
    evidence = {"directives": sig.robots_directive_count, "blocks_all": sig.robots_blocks_all}
    rec = "Serve a valid robots.txt that allows crawling of public pages and lists the sitemap."
    if not sig.robots_found:
        return s.score(0.5, "No robots.txt found (crawlers default to allow-all).", evidence=evidence, recommendation=rec)
    if sig.robots_blocks_all:
        return s.score(
            0.0,
            "robots.txt blocks all crawlers from the site root.",
            severity="critical",
            impact="high",
            evidence=evidence,
            recommendation=rec,
        )
    if not sig.robots_valid:
        return s.score(0.5, "robots.txt is present but malformed.", evidence=evidence, recommendation=rec)
    return s.score(1.0, "robots.txt is valid and allows crawling.", evidence=evidence, recommendation=rec)


@_check("SE07", "seo", 1.0)
def _se07(c: _Ctx, s: _Spec) -> Finding:
    scores: list[float] = []
    for p in c.ok:
        if not p.canonical:
            scores.append(0.0)
        else:
            scores.append(1.0 if _host(p.canonical) == _host(p.final_url) else 0.5)
    with_canon = sum(1 for p in c.ok if p.canonical)
    return s.score(
        fmean(scores),
        f"{with_canon}/{len(c.ok)} pages declare a canonical URL.",
        urls=[p.url for p, sc in zip(c.ok, scores, strict=True) if sc < 1.0],
        evidence={"with_canonical": with_canon, "pages": len(c.ok)},
        recommendation="Add a self-referencing <link rel='canonical'> to every indexable page.",
    )


@_check("SE08", "seo", 1.0)
def _se08(c: _Ctx, s: _Spec) -> Finding:
    required = c.cfg["seo"]["og_required_tags"]
    present = [t for t in required if t in c.home.open_graph_tags]
    return s.score(
        len(present) / len(required),
        f"Homepage declares {len(present)}/{len(required)} Open Graph tags.",
        severity="low",
        impact="low",
        evidence={"present": present, "missing": [t for t in required if t not in present]},
        recommendation="Add og:title, og:description and og:image for rich social previews.",
    )


@_check("SE09", "seo", 2.0)
def _se09(c: _Ctx, s: _Spec) -> Finding:
    if c.is_single_page:
        return s.skip("not_applicable", "Single crawled page: orphan analysis does not apply.")
    others = [p for p in c.ok if p is not c.home]
    orphans = [
        p.url for p in others if _norm(p.url) not in c.linked and _norm(p.final_url) not in c.linked
    ]
    return s.score(
        2.0 * (1 - len(orphans) / len(others)),
        f"{len(orphans)} of {len(others)} crawled pages have no internal link pointing to them.",
        urls=orphans,
        evidence={"orphans": len(orphans), "pages": len(others)},
        recommendation="Link every important page from navigation or related content.",
    )


# ---------------------------------------------------------------------------
# 3. PERFORMANCE (15)
# ---------------------------------------------------------------------------


@_check("PF01", "performance", 4.0)
def _pf01(c: _Ctx, s: _Spec) -> Finding:
    cfg = c.cfg["performance"]
    avg = fmean(p.response_time_ms for p in c.ok)
    pts = (
        4.0
        if avg < cfg["response_excellent_ms"]
        else 2.5
        if avg < cfg["response_good_ms"]
        else 1.0
        if avg < cfg["response_poor_ms"]
        else 0.0
    )
    return s.score(
        pts,
        f"Average server response time is {avg:.0f} ms across {len(c.ok)} pages.",
        severity="high",
        impact="high",
        urls=[p.url for p in c.ok if p.response_time_ms >= cfg["response_good_ms"]],
        evidence={"avg_response_ms": round(avg)},
        recommendation="Use caching/CDN and optimise backend queries to keep responses under 800 ms.",
    )


@_check("PF02", "performance", 3.0)
def _pf02(c: _Ctx, s: _Spec) -> Finding:
    return s.skip(
        "not_tested",
        "Interaction latency (INP) needs a real browser; not measured by the HTML crawler.",
        recommendation="Run Lighthouse or the PageSpeed API for field/lab INP data.",
    )


@_check("PF03", "performance", 2.0)
def _pf03(c: _Ctx, s: _Spec) -> Finding:
    total = sum(p.images_total for p in c.ok)
    if total == 0:
        return s.skip("not_applicable", "No images found.")
    missing = sum(p.images_missing_dimensions for p in c.ok)
    ratio = 1 - missing / total
    target = c.cfg["performance"]["image_dimension_ratio_ok"]
    return s.score(
        2.0 * min(1.0, ratio / target),
        f"{total - missing}/{total} images declare width and height (layout-shift risk proxy).",
        urls=[p.url for p in c.ok if p.images_missing_dimensions],
        evidence={"images": total, "missing_dimensions": missing},
        recommendation="Set explicit width and height (or aspect-ratio) on every image.",
    )


@_check("PF04", "performance", 2.0)
def _pf04(c: _Ctx, s: _Spec) -> Finding:
    encodings = c.cfg["performance"]["compression_encodings"]
    compressed = [p for p in c.ok if any(e in p.headers.get("content-encoding", "").lower() for e in encodings)]
    return s.score(
        2.0 * len(compressed) / len(c.ok),
        f"{len(compressed)}/{len(c.ok)} HTML responses are compressed.",
        urls=[p.url for p in c.ok if p not in compressed],
        evidence={"compressed": len(compressed), "pages": len(c.ok)},
        recommendation="Enable Brotli or gzip compression for HTML, CSS and JS.",
    )


@_check("PF05", "performance", 1.0)
def _pf05(c: _Ctx, s: _Spec) -> Finding:
    total = sum(p.images_total for p in c.ok)
    if total == 0:
        return s.skip("not_applicable", "No images found.")
    good = sum(p.images_modern_or_lazy for p in c.ok)
    target = c.cfg["performance"]["image_modern_ratio_ok"]
    return s.score(
        min(1.0, (good / total) / target),
        f"{good}/{total} images are lazy-loaded or use WebP/AVIF/SVG.",
        severity="low",
        impact="low",
        evidence={"images": total, "modern_or_lazy": good},
        recommendation="Serve WebP/AVIF and add loading='lazy' to below-the-fold images.",
    )


@_check("PF06", "performance", 1.0)
def _pf06(c: _Ctx, s: _Spec) -> Finding:
    cfg = c.cfg["performance"]
    avg = fmean(p.render_blocking_scripts for p in c.ok)
    pts = 1.0 if avg <= cfg["render_blocking_ok"] else 0.5 if avg <= cfg["render_blocking_partial"] else 0.0
    return s.score(
        pts,
        f"Pages average {avg:.1f} render-blocking <script> tags in <head>.",
        severity="low",
        impact="low",
        urls=[p.url for p in c.ok if p.render_blocking_scripts > cfg["render_blocking_partial"]],
        evidence={"avg_blocking_scripts": round(avg, 1)},
        recommendation="Add defer/async to head scripts or move them to the end of <body>.",
    )


@_check("PF07", "performance", 2.0)
def _pf07(c: _Ctx, s: _Spec) -> Finding:
    cfg = c.cfg["performance"]
    avg_kb = fmean(p.html_size_bytes for p in c.ok) / 1024.0
    pts = 2.0 if avg_kb <= cfg["html_weight_good_kb"] else 1.0 if avg_kb <= cfg["html_weight_max_kb"] else 0.0
    return s.score(
        pts,
        f"Average HTML document size is {avg_kb:.0f} KB.",
        urls=[p.url for p in c.ok if p.html_size_bytes / 1024.0 > cfg["html_weight_max_kb"]],
        evidence={"avg_html_kb": round(avg_kb)},
        recommendation="Trim inline scripts/styles and large server-rendered payloads.",
    )


# ---------------------------------------------------------------------------
# 4. UI/UX & NAVIGATION (15)
# ---------------------------------------------------------------------------


@_check("UX01", "ui_ux", 3.0)
def _ux01(c: _Ctx, s: _Spec) -> Finding:
    cfg = c.cfg["ui_ux"]
    home = c.home
    links = home.anchors_total if c.is_single_page else len(home.internal_links)
    has_nav = "nav" in home.semantic_landmarks
    link_pts = 1.5 if links >= cfg["min_navigation_links"] else 0.75 if links >= 1 else 0.0
    return s.score(
        (1.5 if has_nav else 0.0) + link_pts,
        f"Homepage has a <nav> landmark: {has_nav}; {links} navigation link(s).",
        severity="high",
        impact="high",
        evidence={"nav_landmark": has_nav, "links": links, "single_page": c.is_single_page},
        recommendation="Provide a clear <nav> with links to the main sections.",
    )


@_check("UX02", "ui_ux", 2.0)
def _ux02(c: _Ctx, s: _Spec) -> Finding:
    return s.skip("not_tested", "Visual consistency needs rendered screenshots; not measured.")


@_check("UX03", "ui_ux", 3.0)
def _ux03(c: _Ctx, s: _Spec) -> Finding:
    vc = c.home.viewport_content
    if vc is None:
        return s.score(
            0.0,
            "Homepage has no <meta name='viewport'>; it will not render responsively on phones.",
            severity="critical",
            impact="high",
            urls=[c.home.url],
            recommendation="Add <meta name='viewport' content='width=device-width, initial-scale=1'>.",
        )
    responsive = "width=device-width" in vc.replace(" ", "")
    return s.score(
        3.0 if responsive else 1.5,
        f"Viewport declared: '{vc}'.",
        severity="critical" if not responsive else "medium",
        impact="high",
        evidence={"viewport": vc},
        recommendation="Use width=device-width in the viewport meta tag.",
    )


@_check("UX04", "ui_ux", 2.0)
def _ux04(c: _Ctx, s: _Spec) -> Finding:
    targets = [p for p in c.pages if _norm(p.url) in c.linked]
    broken = [p.url for p in targets if p.status_code >= 400 or p.status_code == 0]
    ratio = len(broken) / len(targets) if targets else 0.0
    pts = 2.0 if not broken else 1.0 if ratio <= c.cfg["ui_ux"]["broken_link_ratio_ok"] else 0.0
    return s.score(
        pts,
        f"{len(broken)} of {len(targets)} crawled link targets are broken (4xx/5xx/unreachable).",
        severity="high",
        impact="high",
        urls=broken,
        evidence={"broken": len(broken), "linked_targets_crawled": len(targets)},
        recommendation="Fix or redirect broken internal links.",
    )


@_check("UX05", "ui_ux", 2.0)
def _ux05(c: _Ctx, s: _Spec) -> Finding:
    n = c.home.cta_count
    full = c.cfg["ui_ux"]["min_ctas_full"]
    return s.score(
        2.0 if n >= full else 1.0 if n >= 1 else 0.0,
        f"Homepage has {n} action-oriented link(s)/button(s) (e.g. 'Get started', 'Contact').",
        evidence={"cta_count": n},
        recommendation="Add clear, verb-led calls to action above the fold.",
    )


@_check("UX06", "ui_ux", 2.0)
def _ux06(c: _Ctx, s: _Spec) -> Finding:
    if c.is_single_page:
        return s.skip("not_applicable", "Single crawled page: cross-page consistency does not apply.")
    base = set(c.home.semantic_landmarks)
    sims = [_jaccard(set(p.semantic_landmarks), base) for p in c.ok if p is not c.home]
    mean = fmean(sims)
    target = c.cfg["ui_ux"]["template_similarity_ok"]
    return s.score(
        2.0 * min(1.0, mean / target),
        f"Inner pages share {mean:.0%} of the homepage's structural landmarks.",
        severity="low",
        impact="low",
        evidence={"mean_similarity": round(mean, 2)},
        recommendation="Reuse a shared header/nav/footer template across all pages.",
    )


@_check("UX07", "ui_ux", 1.0)
def _ux07(c: _Ctx, s: _Spec) -> Finding:
    cfg = c.cfg["ui_ux"]
    pages = [p for p in c.ok if p.word_count >= cfg["min_words_for_readability"]]
    if not pages:
        return s.skip("not_applicable", "No page has enough text to assess scannability.")
    avg = fmean(p.word_count / max(1, len(p.headings)) for p in pages)
    pts = 1.0 if avg <= cfg["words_per_heading_good"] else 0.5 if avg <= cfg["words_per_heading_ok"] else 0.0
    return s.score(
        pts,
        f"Text pages average {avg:.0f} words per heading.",
        severity="low",
        impact="low",
        evidence={"avg_words_per_heading": round(avg)},
        recommendation="Break long sections up with descriptive subheadings.",
    )


# ---------------------------------------------------------------------------
# 5. CONTENT QUALITY (15)
# ---------------------------------------------------------------------------


@_check("CT01", "content", 3.0)
def _ct01(c: _Ctx, s: _Spec) -> Finding:
    if not c.home_ok:
        return s.skip("not_tested", "Homepage did not load successfully.")
    cfg = c.cfg["content"]
    words = c.home.word_count
    pts = (
        3.0
        if words >= cfg["min_words_excellent"]
        else 1.5
        if words >= cfg["min_words_good"]
        else 0.5
        if words >= cfg["min_words_minimal"]
        else 0.0
    )
    return s.score(
        pts,
        f"Homepage contains {words} words of visible text.",
        severity="high",
        impact="high",
        urls=[] if pts == 3.0 else [c.home.url],
        evidence={"homepage_words": words},
        recommendation="Explain what the site offers with at least 300 words of substantive copy.",
    )


@_check("CT02", "content", 3.0)
def _ct02(c: _Ctx, s: _Spec) -> Finding:
    if c.is_single_page:
        return s.skip("not_applicable", "Single crawled page: site-wide thin-content check does not apply.")
    thin_limit = c.cfg["content"]["thin_page_words"]
    thin = [p.url for p in c.ok if p.word_count < thin_limit]
    return s.score(
        3.0 * (1 - len(thin) / len(c.ok)),
        f"{len(thin)} of {len(c.ok)} pages have fewer than {thin_limit} words.",
        urls=thin,
        evidence={"thin_pages": len(thin), "pages": len(c.ok)},
        recommendation="Expand or consolidate thin pages.",
    )


def _stems(text: str) -> set[str]:
    return {t[:5] for t in re.findall(r"[a-z]{4,}", text.lower()) if t not in STOPWORDS}


@_check("CT03", "content", 2.0)
def _ct03(c: _Ctx, s: _Spec) -> Finding:
    min_words = c.cfg["ui_ux"]["min_words_for_readability"]
    results: list[bool] = []
    for p in c.ok:
        if p.word_count < min_words:
            continue
        head_stems = _stems(f"{p.title or ''} {' '.join(p.h1s)}")
        if head_stems:
            results.append(bool(head_stems & {t[:5] for t in p.top_terms}))
    kw_ratio: float | None = None
    if c.keywords:
        home_text = f"{c.home.title or ''} {' '.join(c.home.h1s)} {c.home.meta_description or ''}".lower()
        kw_ratio = sum(1 for k in c.keywords if k.lower() in home_text) / len(c.keywords)
    if not results and kw_ratio is None:
        return s.skip("not_applicable", "No page has enough text and headings to compare.")
    parts = ([fmean(results)] if results else []) + ([kw_ratio] if kw_ratio is not None else [])
    return s.score(
        2.0 * fmean(parts),
        f"Title/H1 terms match the body's dominant terms on {sum(results)}/{len(results)} text pages"
        + (f"; {kw_ratio:.0%} of target keywords appear in title/H1/meta." if kw_ratio is not None else "."),
        evidence={"pages_aligned": sum(results), "pages_checked": len(results), "keyword_coverage": kw_ratio},
        recommendation="Make titles and H1s reflect what the page body is actually about.",
    )


@_check("CT04", "content", 2.0)
def _ct04(c: _Ctx, s: _Spec) -> Finding:
    min_words = c.cfg["ui_ux"]["min_words_for_readability"]
    scores = [
        textstat.flesch_reading_ease(p.clean_text)
        for p in c.ok
        if p.word_count >= min_words and p.clean_text
    ]
    if not scores:
        return s.skip("not_applicable", "No page has enough text to compute readability.")
    cfg = c.cfg["content"]
    mean = fmean(scores)
    pts = 2.0 if mean >= cfg["flesch_good"] else 1.0 if mean >= cfg["flesch_ok"] else 0.0
    return s.score(
        pts,
        f"Average Flesch reading ease is {mean:.0f} (higher is easier; grammar is not assessed).",
        severity="low",
        impact="low",
        evidence={"flesch_reading_ease": round(mean, 1), "pages": len(scores)},
        recommendation="Use shorter sentences and plainer wording.",
    )


@_check("CT05", "content", 2.0)
def _ct05(c: _Ctx, s: _Spec) -> Finding:
    cfg = c.cfg["content"]
    pages = [p for p in c.ok if p.word_count >= cfg["min_words_for_duplicate"] and p.clean_text]
    if len(pages) < 2:
        return s.skip("not_applicable", "Fewer than two text pages: duplicate analysis does not apply.")
    sh = {p.url: _shingles(p.clean_text) for p in pages}
    involved: set[str] = set()
    for a, b in combinations(pages, 2):
        if _jaccard(sh[a.url], sh[b.url]) >= cfg["duplicate_similarity"]:
            involved.update((a.url, b.url))
    return s.score(
        2.0 * (1 - len(involved) / len(pages)),
        f"{len(involved)} of {len(pages)} text pages are near-duplicates of another page.",
        urls=sorted(involved),
        evidence={"duplicate_pages": len(involved), "pages": len(pages)},
        recommendation="Rewrite, merge or canonicalise near-duplicate pages.",
    )


@_check("CT06", "content", 2.0)
def _ct06(c: _Ctx, s: _Spec) -> Finding:
    flagged = [p.url for p in c.ok if p.has_placeholder_content]
    return s.score(
        0.0 if flagged else 2.0,
        f"Placeholder text ('Lorem ipsum', 'Coming soon', ...) found on {len(flagged)} page(s)."
        if flagged
        else "No placeholder text detected.",
        severity="critical" if flagged else "medium",
        impact="high",
        urls=flagged,
        evidence={"placeholder_pages": len(flagged)},
        recommendation="Replace placeholder copy with real content.",
    )


@_check("CT07", "content", 1.0)
def _ct07(c: _Ctx, s: _Spec) -> Finding:
    found = any(p.has_contact_signal for p in c.ok)
    return s.score(
        1.0 if found else 0.0,
        "A contact/about link or mailto/tel link was found."
        if found
        else "No contact or about information found.",
        severity="low",
        impact="medium",
        recommendation="Expose contact details (email, phone, form) in header or footer.",
    )


# ---------------------------------------------------------------------------
# 6. FUNCTIONALITY (15)
# ---------------------------------------------------------------------------


@_check("FN01", "functionality", 3.0, needs_pages=False)
def _fn01(c: _Ctx, s: _Spec) -> Finding:
    limit = c.cfg["functionality"]["redirect_chain_max"]
    bad = [p.url for p in c.pages if p.status_code == 0 or len(p.redirect_chain) > limit]
    return s.score(
        3.0 * (1 - len(bad) / len(c.pages)),
        f"{len(bad)} of {len(c.pages)} pages timed out/failed to fetch or redirect more than {limit} times.",
        severity="high",
        impact="high",
        urls=bad,
        evidence={"problem_pages": len(bad), "pages": len(c.pages)},
        recommendation="Fix unreachable pages and collapse long redirect chains.",
    )


@_check("FN02", "functionality", 3.0)
def _fn02(c: _Ctx, s: _Spec) -> Finding:
    total = sum(p.form_inputs_total for p in c.ok)
    if total == 0:
        return s.skip("not_applicable", "No form inputs found.")
    validated = sum(p.form_inputs_validated for p in c.ok)
    target = c.cfg["functionality"]["form_validation_ratio_ok"]
    return s.score(
        3.0 * min(1.0, (validated / total) / target),
        f"{validated}/{total} form inputs use HTML5 validation (required/pattern/typed).",
        urls=[p.url for p in c.ok if p.form_inputs_total > p.form_inputs_validated],
        evidence={"inputs": total, "validated": validated},
        recommendation="Add required, type=email/tel and pattern attributes to form fields.",
    )


@_check("FN03", "functionality", 2.0)
def _fn03(c: _Ctx, s: _Spec) -> Finding:
    cfg = c.cfg["functionality"]
    anchors = sum(p.anchors_total for p in c.ok)
    if anchors == 0:
        return s.skip("not_applicable", "No links found.")
    dead = sum(p.dead_links for p in c.ok)
    ratio = dead / anchors
    pts = 2.0 if dead == 0 else 1.5 if ratio <= cfg["dead_link_ratio_good"] else 1.0 if ratio <= cfg["dead_link_ratio_ok"] else 0.0
    return s.score(
        pts,
        f"{dead} of {anchors} links point nowhere (href='#', empty or javascript:).",
        urls=[p.url for p in c.ok if p.dead_links],
        evidence={"dead_links": dead, "links": anchors},
        recommendation="Replace placeholder links with real destinations or <button> elements.",
    )


@_check("FN04", "functionality", 2.0)
def _fn04(c: _Ctx, s: _Spec) -> Finding:
    unsafe = sum(p.unsafe_blank_links for p in c.ok)
    pts = 2.0 if unsafe == 0 else 1.0 if unsafe <= c.cfg["functionality"]["unsafe_blank_links_ok"] else 0.0
    return s.score(
        pts,
        f"{unsafe} link(s) open a new tab without rel='noopener'.",
        severity="low",
        impact="low",
        urls=[p.url for p in c.ok if p.unsafe_blank_links],
        evidence={"unsafe_links": unsafe},
        recommendation="Add rel='noopener noreferrer' to links using target='_blank'.",
    )


@_check("FN05", "functionality", 2.0)
def _fn05(c: _Ctx, s: _Spec) -> Finding:
    return s.skip("not_tested", "Interactive widgets need a real browser session; not measured.")


@_check("FN06", "functionality", 2.0)
def _fn06(c: _Ctx, s: _Spec) -> Finding:
    return s.skip("not_tested", "JavaScript console errors need a real browser session; not measured.")


@_check("FN07", "functionality", 1.0)
def _fn07(c: _Ctx, s: _Spec) -> Finding:
    return s.skip("not_tested", "Critical user flows (checkout, signup) need scripted interaction; not measured.")


# ---------------------------------------------------------------------------
# 7. SECURITY (5)
# ---------------------------------------------------------------------------


@_check("SC01", "security", 1.0, needs_pages=False)
def _sc01(c: _Ctx, s: _Spec) -> Finding:
    if not c.home.final_url.lower().startswith("https://"):
        return s.score(
            0.0,
            "Site is not served over HTTPS.",
            severity="critical",
            impact="high",
            urls=[c.home.url],
            recommendation="Serve the site over HTTPS and redirect all HTTP traffic.",
        )
    redirects = c.site.http_redirects_to_https if c.site else None
    if redirects is None:
        return s.skip("not_tested", "HTTP-to-HTTPS redirect was not probed.")
    return s.score(
        1.0 if redirects else 0.0,
        "Plain HTTP permanently redirects to HTTPS."
        if redirects
        else "Plain HTTP does not redirect to HTTPS.",
        severity="high",
        impact="high",
        recommendation="Add a 301 redirect from http:// to https:// for every URL.",
    )


@_check("SC02", "security", 1.0)
def _sc02(c: _Ctx, s: _Spec) -> Finding:
    if not c.home.final_url.lower().startswith("https://"):
        return s.skip("not_applicable", "Site is not on HTTPS, so mixed content cannot occur.")
    mixed = [p.url for p in c.ok if p.mixed_content_urls]
    return s.score(
        0.0 if mixed else 1.0,
        f"HTTP subresources loaded on {len(mixed)} HTTPS page(s)." if mixed else "No mixed content found.",
        severity="high" if mixed else "medium",
        impact="high",
        urls=mixed,
        evidence={"examples": [u for p in c.ok for u in p.mixed_content_urls][:5]},
        recommendation="Load every script, stylesheet and image over HTTPS.",
    )


@_check("SC03", "security", 2.0)
def _sc03(c: _Ctx, s: _Spec) -> Finding:
    if not c.home_ok:
        return s.skip("not_tested", "Homepage did not load successfully.")
    headers = c.home.headers
    https = c.home.final_url.lower().startswith("https://")
    present: list[str] = []
    for name in c.cfg["security"]["security_headers"]:
        if name == "strict-transport-security" and not https:
            continue
        if name == "x-frame-options":
            if name in headers or "frame-ancestors" in headers.get("content-security-policy", "").lower():
                present.append(name)
        elif name in headers:
            present.append(name)
    wanted = c.cfg["security"]["security_headers"]
    return s.score(
        2.0 * len(present) / len(wanted),
        f"{len(present)}/{len(wanted)} security headers present: {', '.join(present) or 'none'}.",
        evidence={"present": present, "missing": [h for h in wanted if h not in present]},
        recommendation="Send HSTS, CSP, X-Content-Type-Options and X-Frame-Options headers.",
    )


@_check("SC04", "security", 1.0)
def _sc04(c: _Ctx, s: _Spec) -> Finding:
    if not c.home_ok:
        return s.skip("not_tested", "Homepage did not load successfully.")
    h = c.home.headers
    server, powered = h.get("server", ""), h.get("x-powered-by", "")
    versioned = bool(re.search(r"\d+\.\d+", f"{server} {powered}"))
    pts = 0.0 if versioned else 0.5 if powered else 1.0
    return s.score(
        pts,
        "Response headers disclose software versions."
        if versioned
        else "X-Powered-By discloses the technology stack."
        if powered
        else "No technology/version disclosure in response headers.",
        severity="low",
        impact="low",
        evidence={"server": server, "x_powered_by": powered},
        recommendation="Remove X-Powered-By and version numbers from Server headers.",
    )


# ---------------------------------------------------------------------------
# 8. ACCESSIBILITY (10)
# ---------------------------------------------------------------------------


@_check("AC01", "accessibility", 2.0)
def _ac01(c: _Ctx, s: _Spec) -> Finding:
    total = sum(p.images_total for p in c.ok)
    if total == 0:
        return s.skip("not_applicable", "No images found.")
    missing = sum(p.images_missing_alt for p in c.ok)
    return s.score(
        2.0 * (1 - missing / total),
        f"{total - missing}/{total} images have an alt attribute (alt='' marks decorative images).",
        urls=[p.url for p in c.ok if p.images_missing_alt],
        evidence={"images": total, "missing_alt": missing},
        recommendation="Add alt text to informative images and alt='' to decorative ones.",
    )


@_check("AC02", "accessibility", 2.0)
def _ac02(c: _Ctx, s: _Spec) -> Finding:
    total = sum(p.form_inputs_total for p in c.ok)
    if total == 0:
        return s.skip("not_applicable", "No form inputs found.")
    unlabeled = sum(p.form_inputs_without_labels for p in c.ok)
    return s.score(
        2.0 * (1 - min(unlabeled, total) / total),
        f"{unlabeled} of {total} form inputs have no label or aria-label.",
        urls=[p.url for p in c.ok if p.form_inputs_without_labels],
        evidence={"inputs": total, "unlabeled": unlabeled},
        recommendation="Associate each input with a <label for=...> or aria-label.",
    )


_LANG_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


@_check("AC03", "accessibility", 2.0)
def _ac03(c: _Ctx, s: _Spec) -> Finding:
    lang = c.home.html_lang
    lang_ok = bool(lang and _LANG_RE.match(lang))
    bad_tab = sum(p.positive_tabindex_count for p in c.ok)
    vc = (c.home.viewport_content or "").replace(" ", "")
    scale = re.search(r"maximum-scale=(\d+(?:\.\d+)?)", vc)
    zoom_blocked = "user-scalable=no" in vc or "user-scalable=0" in vc or bool(scale and float(scale.group(1)) < 2)
    pts = (0.8 if lang_ok else 0.0) + (0.6 if bad_tab == 0 else 0.0) + (0.6 if not zoom_blocked else 0.0)
    return s.score(
        pts,
        f"<html lang>: {lang or 'missing'}; positive tabindex elements: {bad_tab}; "
        f"pinch-zoom {'blocked' if zoom_blocked else 'allowed'}.",
        evidence={"lang": lang, "positive_tabindex": bad_tab, "zoom_blocked": zoom_blocked},
        recommendation="Set <html lang>, avoid tabindex > 0 and never disable zoom.",
    )


@_check("AC04", "accessibility", 2.0)
def _ac04(c: _Ctx, s: _Spec) -> Finding:
    return s.skip("not_tested", "Colour contrast needs rendered CSS; not measured by the HTML crawler.")


@_check("AC05", "accessibility", 2.0)
def _ac05(c: _Ctx, s: _Spec) -> Finding:
    if not c.home_ok:
        return s.skip("not_tested", "Homepage did not load successfully.")
    lm = set(c.home.semantic_landmarks)
    chrome = len(lm & {"header", "nav", "footer"})
    pts = (1.0 if "main" in lm else 0.0) + chrome / 3
    return s.score(
        pts,
        f"Landmarks on homepage: {', '.join(sorted(lm)) or 'none'}.",
        evidence={"landmarks": sorted(lm)},
        recommendation="Structure pages with <header>, <nav>, <main> and <footer>.",
    )


# ---------------------------------------------------------------------------
# Caps and orchestration
# ---------------------------------------------------------------------------


def _detect_caps(c: _Ctx) -> list[tuple[str, float]]:
    cfg = c.cfg["caps"]
    caps: list[tuple[str, float]] = []
    home = c.home
    code = home.status_code

    if code == 0:
        caps.append(("Homepage unreachable (DNS, TLS, connection or timeout failure)", cfg["unreachable_cap"]))
    elif code in (401, 403, 429):
        caps.append(
            (f"Homepage denied access (HTTP {code}); site cannot be meaningfully audited", cfg["unreachable_cap"])
        )
    elif code >= 500:
        caps.append((f"Homepage returns HTTP {code} Server Error", cfg["homepage_5xx_cap"]))
    elif code >= 400:
        caps.append((f"Submitted homepage returns HTTP {code}", cfg["homepage_404_cap"]))

    if c.ok:
        share = sum(1 for p in c.ok if p.has_placeholder_content) / len(c.ok)
        if c.home.has_placeholder_content or share >= c.cfg["content"]["placeholder_site_share"]:
            caps.append(
                ("Site exhibits placeholder or unfinished content ('Lorem ipsum' / 'Coming soon')", cfg["placeholder_content_cap"])
            )

    broken = sum(1 for p in c.pages if p.status_code >= 400)
    if broken >= cfg["broken_pages_min_count"] and broken / len(c.pages) >= cfg["broken_pages_min_share"]:
        caps.append(
            (f"Many crawled pages are broken ({broken} of {len(c.pages)} return 4xx/5xx)", cfg["broken_pages_cap"])
        )

    if len(c.ok) > 1 and sum(len(p.internal_links) for p in c.ok) == 0:
        caps.append(("Major navigation is broken (0 internal links discovered across pages)", cfg["broken_navigation_cap"]))

    if code != 0 and not home.final_url.lower().startswith("https://"):
        caps.append(("Insecure plain HTTP origin without HTTPS enforcement", cfg["insecure_http_cap"]))

    if c.home_ok:
        if home.viewport_content is None:
            caps.append(
                ("No usable mobile layout on a site expected to be responsive (missing viewport)", cfg["missing_viewport_cap"])
            )
        if len(c.ok) <= cfg["shallow_site_max_pages"] and home.word_count < cfg["shallow_site_words"]:
            caps.append(
                (f"Shallow site: homepage has under {cfg['shallow_site_words']} words and little else", cfg["shallow_site_cap"])
            )
    return caps


def evaluate_checks_and_caps(
    pages: list[PageData],
    target_url: str,
    target_keywords: list[str] | None = None,
    site: SiteSignals | None = None,
) -> tuple[list[Finding], list[tuple[str, float]]]:
    """Run every registered check and detect critical issue caps.

    Returns:
        Tuple of (findings, caps) where caps is a list of (reason, score_limit).
    """
    if not pages:
        reason = "Confirmed unreachable/undeployed origin due to DNS or network failure"
        if site and site.robots_blocks_all:
            reason = "robots.txt disallows all crawling, so no page could be audited"
        return [], [(reason, AUDIT_THRESHOLDS["caps"]["unreachable_cap"])]

    ctx = _Ctx(pages, target_url, target_keywords or [], site, AUDIT_THRESHOLDS)
    findings: list[Finding] = []
    for spec, needs_pages, fn in _REGISTRY:
        if needs_pages and not ctx.ok:
            findings.append(spec.skip("not_tested", "No HTML page loaded successfully."))
        else:
            findings.append(fn(ctx, spec))
    return findings, _detect_caps(ctx)


def _confidence(ok_pages: int, coverage: float) -> str:
    if ok_pages <= 0:
        return "not_assessable"
    pages_tier = 2 if ok_pages >= 5 else 1 if ok_pages >= 2 else 0
    coverage_tier = 2 if coverage >= 80 else 1 if coverage >= 60 else 0
    return ("low", "medium", "high")[min(pages_tier, coverage_tier)]


def calculate_scores(findings: list[Finding], total_pages: int) -> AuditScore:
    """Aggregate findings into category scores, an overall score and confidence.

    Legacy 4-category findings (max_points == 0) are scored with the old penalty model.
    """
    effective_pages = max(1, total_pages)

    is_legacy = any(f.category in ("technical", "onpage") for f in findings) and all(
        f.max_points == 0.0 for f in findings
    )

    if is_legacy:
        category_results: dict[str, CategoryScore] = {}
        for cat_key, meta in LEGACY_CATEGORIES.items():
            cat_findings = [f for f in findings if f.category == cat_key]
            crit_count = sum(1 for f in cat_findings if f.severity == "critical" and not f.passed)
            warn_count = sum(1 for f in cat_findings if f.severity == "warning" and not f.passed)
            info_count = sum(1 for f in cat_findings if f.severity == "info" and not f.passed)

            penalties = 0.0
            for f in cat_findings:
                if not f.passed:
                    base = 10.0 if f.severity == "critical" else 4.0 if f.severity == "warning" else 1.0
                    ratio = len(f.affected_urls) / effective_pages if f.affected_urls else 1.0
                    penalties += base * max(0.25, min(ratio, 1.0))

            raw_cat_score = max(0.0, min(100.0, 100.0 - penalties))
            category_results[cat_key] = CategoryScore(
                id=cat_key,
                name=meta["name"],
                weight=meta["weight"] * 100.0,
                earned_points=round(raw_cat_score * meta["weight"], 1),
                max_points=round(100.0 * meta["weight"], 1),
                score=round(raw_cat_score, 1),
                coverage_percent=100.0,
                grade=_get_letter_grade(raw_cat_score),
                critical_count=crit_count,
                warning_count=warn_count,
                info_count=info_count,
            )

        overall = round(
            sum(category_results[cat].score * LEGACY_CATEGORIES[cat]["weight"] for cat in LEGACY_CATEGORIES),
            1,
        )
        return AuditScore(
            raw_score=overall,
            final_score=overall,
            overall=overall,
            grade=_get_letter_grade(overall),
            rating=_get_rating_band(overall),
            confidence="high" if total_pages >= 10 else ("medium" if total_pages >= 3 else "low"),
            coverage_percent=100.0,
            score_caps_applied=[],
            categories=category_results,
        )

    category_scores: dict[str, CategoryScore] = {}
    weighted_pct = 0.0
    assessed_weight = 0.0
    coverage_weighted = 0.0
    total_weight = sum(info["weight"] for info in CATEGORY_WEIGHTS.values())

    for cat_id, info in CATEGORY_WEIGHTS.items():
        weight = info["weight"]
        cat_findings = [f for f in findings if f.category == cat_id]
        scored = [f for f in cat_findings if f.status not in SKIPPED_STATUSES]
        total_max = sum(f.max_points for f in cat_findings)
        scored_max = sum(f.max_points for f in scored)
        coverage = (scored_max / total_max * 100.0) if total_max > 0 else 0.0
        coverage_weighted += weight * coverage / 100.0

        crit = sum(1 for f in scored if f.severity in ("critical", "high") and f.status == "fail")
        warn = sum(1 for f in scored if f.severity in ("medium", "warning") and f.status in ("fail", "partial"))
        inf = sum(1 for f in scored if f.severity in ("low", "info") and f.status in ("fail", "partial"))

        if scored_max <= 0:
            category_scores[cat_id] = CategoryScore(
                id=cat_id,
                name=info["name"],
                weight=weight,
                earned_points=0.0,
                max_points=weight,
                score=0.0,
                coverage_percent=0.0,
                grade="N/A",
                status="not_assessed",
            )
            continue

        pct = sum(f.points_earned for f in scored) / scored_max * 100.0
        weighted_pct += weight * pct
        assessed_weight += weight
        category_scores[cat_id] = CategoryScore(
            id=cat_id,
            name=info["name"],
            weight=weight,
            earned_points=round(pct * weight / 100.0, 1),
            max_points=weight,
            score=round(pct, 1),
            coverage_percent=round(coverage, 1),
            grade=_get_letter_grade(pct),
            status="assessed",
            critical_count=crit,
            warning_count=warn,
            info_count=inf,
        )

    raw_score = round(weighted_pct / assessed_weight, 1) if assessed_weight else 0.0
    coverage_total = round(coverage_weighted / total_weight * 100.0, 1)

    return AuditScore(
        raw_score=raw_score,
        final_score=raw_score,
        overall=raw_score,
        grade=_get_letter_grade(raw_score),
        rating=_get_rating_band(raw_score),
        confidence=_confidence(total_pages, coverage_total),
        coverage_percent=coverage_total,
        score_caps_applied=[],
        not_tested_checks=[f.check_id for f in findings if f.status in SKIPPED_STATUSES],
        categories=category_scores,
    )


def compute_audit_score_with_caps(
    pages: list[PageData],
    target_url: str,
    target_keywords: list[str] | None = None,
    site: SiteSignals | None = None,
) -> tuple[list[Finding], AuditScore]:
    """Execute checks, aggregate them and apply critical issue caps.

    Args:
        pages: Crawled PageData items (homepage first).
        target_url: Original submitted URL.
        target_keywords: Optional target keywords for the topical-focus check.
        site: Site-level evidence from the crawler (robots.txt, sitemap, HTTP redirect).

    Returns:
        Tuple of (findings, final_audit_score).
    """
    findings, caps = evaluate_checks_and_caps(pages, target_url, target_keywords, site)

    ok_pages = sum(1 for p in pages if p.status_code == 200 and p.raw_html)
    base_score = calculate_scores(findings, total_pages=ok_pages)
    raw_score = base_score.raw_score

    caps_applied_text = [f"{reason} (Max cap: {limit:.0f}/100)" for reason, limit in caps]
    max_cap = min((limit for _, limit in caps), default=None)
    final_score = round(min(raw_score, max_cap) if max_cap is not None else raw_score, 1)

    is_assessable = len(pages) > 0 and not any(limit == 0.0 for _, limit in caps)

    return findings, AuditScore(
        raw_score=raw_score,
        final_score=final_score,
        overall=final_score,
        maximum_cap=max_cap,
        grade=_get_letter_grade(final_score, is_assessable=is_assessable),
        rating=_get_rating_band(final_score, is_assessable=is_assessable),
        confidence=base_score.confidence if is_assessable else "not_assessable",
        coverage_percent=base_score.coverage_percent,
        score_caps_applied=caps_applied_text,
        not_tested_checks=base_score.not_tested_checks,
        categories=base_score.categories,
    )
