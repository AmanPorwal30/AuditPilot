"""Tests for the evidence-based scoring engine, built from real HTML through the parser."""

import pytest

from auditpilot.models import Finding, PageData, SiteSignals
from auditpilot.parsers import parse_page_html
from auditpilot.scoring import calculate_scores, compute_audit_score_with_caps

GOOD_HEADERS = {
    "strict-transport-security": "max-age=31536000",
    "content-security-policy": "default-src 'self'",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "content-encoding": "br",
}
GOOD_SITE = SiteSignals(
    robots_found=True,
    robots_valid=True,
    robots_blocks_all=False,
    robots_directive_count=3,
    sitemap_found=True,
    sitemap_valid=True,
    sitemap_url="https://example.com/sitemap.xml",
    sitemap_url_count=3,
    http_redirects_to_https=True,
)

PARAGRAPHS = [
    "Our engineering team designs scalable automation platforms that help companies reduce manual work. "
    "We combine cloud architecture, careful testing and clear documentation to deliver reliable systems. "
    "Every project starts with a short discovery phase where we map the processes that cost the most time.",
    "Clients choose us because we explain trade-offs plainly and ship small improvements every week. "
    "Our support plans include monitoring, regular reviews and a named contact who knows your setup well. "
    "We publish our pricing openly so there are no surprises when a project moves from planning to delivery.",
    "The about page describes how the company started, who leads each practice and what values guide the work. "
    "Case studies show measurable outcomes such as faster onboarding, fewer support tickets and lower costs. "
    "Visitors can contact us by email or phone, or request a call using the short form on the contact page.",
]


def _body(topic: str, paragraphs: list[str]) -> str:
    sections = "".join(
        f"<section><h2>{topic} part {i}</h2><p>{p}</p></section>" for i, p in enumerate(paragraphs, 1)
    )
    return sections


def _strong_html(path: str, title: str, h1: str, topic: str, paragraphs: list[str]) -> str:
    return f"""<!DOCTYPE html><html lang="en"><head>
<title>{title}</title>
<meta name="description" content="{h1} - practical automation, cloud engineering and support for growing companies.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="https://example.com{path}">
<meta property="og:title" content="{title}"><meta property="og:description" content="{h1}">
<meta property="og:image" content="https://example.com/og.png">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"Organization","name":"Example"}}</script>
<script src="/app.js" defer></script>
</head><body>
<header><nav><a href="/">Home</a> <a href="/about">About</a> <a href="/contact">Contact</a>
<a href="/services">Services</a></nav></header>
<main><h1>{h1}</h1>{_body(topic, paragraphs)}
<a href="/contact">Get started today</a> <button>Request a demo</button>
<img src="/a.webp" alt="Team photo" width="600" height="400" loading="lazy">
<form action="/contact"><label for="e">Email</label><input id="e" type="email" required></form>
</main><footer>Contact: <a href="mailto:hi@example.com">hi@example.com</a></footer>
</body></html>"""


def _page(url: str, html: str | None, status: int = 200, ms: float = 300.0, headers=None, **kw) -> PageData:
    return parse_page_html(
        url=url,
        html=html,
        status_code=status,
        final_url=kw.pop("final_url", url),
        response_time_ms=ms,
        html_size_bytes=len(html or ""),
        headers=headers if headers is not None else GOOD_HEADERS,
        **kw,
    )


def _strong_site() -> list[PageData]:
    specs = [
        ("/", "Example Automation | Cloud Engineering and Support Services", "Automation that works", "Home", PARAGRAPHS),
        ("/about", "About Example | Our Team, Values and Company History", "About our company", "About", PARAGRAPHS[::-1]),
        ("/contact", "Contact Example | Email, Phone and Call Requests Page", "Contact the team", "Contact", [PARAGRAPHS[1] + " " + PARAGRAPHS[2]]),
        ("/services", "Services | Automation, Cloud Engineering and Managed Support", "Our services", "Services", [PARAGRAPHS[0] + " " + PARAGRAPHS[2]]),
    ]
    return [
        _page(f"https://example.com{path}", _strong_html(path, title, h1, topic, paras))
        for path, title, h1, topic, paras in specs
    ]


def test_strong_site_scores_high_with_no_caps() -> None:
    findings, score = compute_audit_score_with_caps(_strong_site(), "https://example.com", site=GOOD_SITE)
    assert score.score_caps_applied == []
    assert score.maximum_cap is None
    assert score.final_score >= 80.0, [f"{f.check_id}:{f.status}" for f in findings if f.status != "pass"]
    assert score.confidence in ("medium", "high")
    assert {"PF02", "UX02", "FN05", "FN06", "FN07", "AC04"} <= set(score.not_tested_checks)


def test_all_eight_categories_present_and_no_legacy_aliases() -> None:
    _, score = compute_audit_score_with_caps(_strong_site(), "https://example.com", site=GOOD_SITE)
    assert set(score.categories) == {
        "availability", "seo", "performance", "ui_ux", "content", "functionality", "security", "accessibility",
    }
    assert sum(c.weight for c in score.categories.values()) == 100.0


def test_not_tested_checks_do_not_change_the_score() -> None:
    findings, score = compute_audit_score_with_caps(_strong_site(), "https://example.com", site=GOOD_SITE)
    skipped = [f for f in findings if f.status in ("not_tested", "not_applicable")]
    assert skipped and all(f.points_earned == 0.0 for f in skipped)
    assert score.coverage_percent < 100.0


def test_missing_site_signals_are_not_tested_not_failed() -> None:
    findings, _ = compute_audit_score_with_caps(_strong_site(), "https://example.com", site=None)
    by_id = {f.check_id: f for f in findings}
    assert by_id["SE05"].status == "not_tested"
    assert by_id["SE06"].status == "not_tested"
    assert by_id["SC01"].status == "not_tested"


def test_sitemap_and_robots_use_real_signals() -> None:
    bad = SiteSignals(
        robots_found=True, robots_valid=True, robots_blocks_all=True,
        sitemap_found=False, http_redirects_to_https=False,
    )
    findings, _ = compute_audit_score_with_caps(_strong_site(), "https://example.com", site=bad)
    by_id = {f.check_id: f for f in findings}
    assert by_id["SE05"].status == "fail" and by_id["SE05"].points_earned == 0.0
    assert by_id["SE06"].status == "fail"
    assert by_id["SC01"].status == "fail"
    good_findings, _ = compute_audit_score_with_caps(_strong_site(), "https://example.com", site=GOOD_SITE)
    good = {f.check_id: f for f in good_findings}
    assert good["SE05"].status == "pass" and good["SE06"].status == "pass" and good["SC01"].status == "pass"


def test_weak_site_scores_much_lower_than_strong_site() -> None:
    weak_html = """<html><head><title>Home</title></head><body>
    <div><a href="#">Click</a><a href="javascript:void(0)">More</a></div>
    <img src="a.jpg"><img src="b.jpg">
    <form><input name="q"><input name="r"></form>
    <p>We do things. Contact later.</p></body></html>"""
    pages = [_page("http://weak.example.com/", weak_html, ms=2600.0, final_url="http://weak.example.com/", headers={})]
    _, weak = compute_audit_score_with_caps(pages, "http://weak.example.com/")
    _, strong = compute_audit_score_with_caps(_strong_site(), "https://example.com", site=GOOD_SITE)
    assert weak.final_score <= 40.0
    assert strong.final_score - weak.final_score >= 40.0
    assert weak.maximum_cap is not None


def test_average_site_lands_between_weak_and_strong() -> None:
    pages = _strong_site()
    for p in pages:
        p.meta_description = None
        p.canonical = None
        p.open_graph_tags = []
        p.json_ld_types = []
        p.headers = {}
        p.response_time_ms = 1500.0
    _, avg = compute_audit_score_with_caps(pages, "https://example.com")
    _, strong = compute_audit_score_with_caps(_strong_site(), "https://example.com", site=GOOD_SITE)
    assert 50.0 <= avg.final_score < strong.final_score


@pytest.mark.parametrize("status", [0, 401, 403, 429])
def test_unreachable_or_blocked_homepage_is_not_assessable(status: int) -> None:
    pages = [PageData(url="https://example.com", final_url="https://example.com", status_code=status)]
    _, score = compute_audit_score_with_caps(pages, "https://example.com")
    assert score.maximum_cap == 0.0
    assert score.final_score == 0.0
    assert score.rating == "Not assessable"
    assert score.grade == "N/A"
    assert score.confidence == "not_assessable"


def test_no_pages_is_not_assessable() -> None:
    findings, score = compute_audit_score_with_caps([], "https://example.com")
    assert findings == []
    assert score.rating == "Not assessable"
    assert score.final_score == 0.0


def test_robots_blocking_everything_is_reported_as_such() -> None:
    _, score = compute_audit_score_with_caps(
        [], "https://example.com", site=SiteSignals(robots_found=True, robots_blocks_all=True)
    )
    assert any("robots.txt" in c for c in score.score_caps_applied)


def test_cap_homepage_404() -> None:
    pages = [_page("https://example.com", "<html><body>Not Found</body></html>", status=404)]
    _, score = compute_audit_score_with_caps(pages, "https://example.com")
    assert score.maximum_cap == 10.0
    assert score.final_score <= 10.0
    assert any("404" in c for c in score.score_caps_applied)
    assert score.rating == "Critical"


def test_cap_homepage_5xx() -> None:
    pages = [_page("https://example.com", "<html><body>Error</body></html>", status=500)]
    _, score = compute_audit_score_with_caps(pages, "https://example.com")
    assert score.maximum_cap == 20.0
    assert any("500" in c for c in score.score_caps_applied)


def test_cap_placeholder_content() -> None:
    html = "<html lang='en'><head><meta name='viewport' content='width=device-width'></head><body><h1>Coming Soon</h1><p>Lorem ipsum dolor sit amet.</p></body></html>"
    _, score = compute_audit_score_with_caps([_page("https://example.com", html)], "https://example.com")
    assert score.maximum_cap == 30.0
    assert any("placeholder" in c.lower() for c in score.score_caps_applied)


def test_placeholder_phrase_on_one_inner_page_does_not_cap_the_site() -> None:
    pages = _strong_site()
    pages[2].has_placeholder_content = True
    _, score = compute_audit_score_with_caps(pages, "https://example.com", site=GOOD_SITE)
    assert not any("placeholder" in c.lower() for c in score.score_caps_applied)


def test_cap_missing_viewport() -> None:
    html = _strong_html("/", "Example Automation | Cloud Engineering and Support", "Welcome", "Home", PARAGRAPHS)
    html = html.replace('<meta name="viewport" content="width=device-width, initial-scale=1">', "")
    _, score = compute_audit_score_with_caps([_page("https://example.com/", html)], "https://example.com")
    assert score.maximum_cap == 65.0
    assert any("viewport" in c.lower() for c in score.score_caps_applied)


def test_cap_shallow_one_page_site() -> None:
    html = "<html lang='en'><head><title>Hi</title><meta name='viewport' content='width=device-width'></head><body><h1>Hi</h1><p>Hello there.</p></body></html>"
    _, score = compute_audit_score_with_caps([_page("https://example.com/", html)], "https://example.com")
    assert score.maximum_cap == 50.0
    assert any("shallow" in c.lower() for c in score.score_caps_applied)


def test_cap_broken_navigation_on_multi_page_site() -> None:
    html = "<html lang='en'><head><meta name='viewport' content='width=device-width'></head><body><h1>Page</h1></body></html>"
    pages = [_page("https://example.com/", html), _page("https://example.com/p2", html)]
    _, score = compute_audit_score_with_caps(pages, "https://example.com")
    assert score.maximum_cap <= 50.0
    assert any("navigation" in c.lower() for c in score.score_caps_applied)


def test_one_broken_page_on_a_large_site_does_not_cap() -> None:
    pages = _strong_site() + [_page("https://example.com/gone", "<html></html>", status=404)]
    pages += [_page(f"https://example.com/x{i}", _strong_html(f"/x{i}", f"Extra page {i} | Example Automation Services", f"Extra {i}", f"Extra{i}", [PARAGRAPHS[i % 3]])) for i in range(6)]
    _, score = compute_audit_score_with_caps(pages, "https://example.com", site=GOOD_SITE)
    assert not any("broken" in c.lower() for c in score.score_caps_applied)


def test_insecure_origin_is_capped_and_http_final_url_decides() -> None:
    pages = [_page("http://example.com/", _strong_html("/", "Example Automation | Cloud Engineering", "Hi", "Home", PARAGRAPHS), final_url="http://example.com/")]
    _, score = compute_audit_score_with_caps(pages, "http://example.com/")
    assert score.maximum_cap is not None and score.maximum_cap <= 60.0
    assert any("HTTP" in c for c in score.score_caps_applied)


def test_https_redirect_from_http_target_is_not_capped_as_insecure() -> None:
    pages = _strong_site()
    _, score = compute_audit_score_with_caps(pages, "http://example.com", site=GOOD_SITE)
    assert not any("Insecure" in c for c in score.score_caps_applied)


def test_legitimate_single_page_site_is_not_penalised_for_being_single_page() -> None:
    html = _strong_html("/", "Alex Doe | Principal Software Architect and Engineer", "Alex Doe", "Portfolio", PARAGRAPHS)
    html = html.replace('href="/about"', 'href="#about"').replace('href="/contact"', 'href="#contact"').replace('href="/services"', 'href="#projects"')
    findings, score = compute_audit_score_with_caps([_page("https://example.com/", html)], "https://example.com", site=GOOD_SITE)
    by_id = {f.check_id: f for f in findings}
    for cid in ("SE09", "UX06", "CT02", "CT05"):
        assert by_id[cid].status == "not_applicable", cid
    assert by_id["UX01"].status in ("pass", "partial") and by_id["UX01"].points_earned >= 1.5
    assert score.maximum_cap is None
    assert score.final_score >= 75.0
    assert score.confidence == "low"


def test_duplicate_pages_are_detected() -> None:
    pages = _strong_site()
    dup = pages[1].model_copy(update={"url": "https://example.com/about-copy", "final_url": "https://example.com/about-copy"})
    dup.clean_text = pages[1].clean_text
    pages.append(dup)
    findings, _ = compute_audit_score_with_caps(pages, "https://example.com", site=GOOD_SITE)
    ct05 = next(f for f in findings if f.check_id == "CT05")
    assert ct05.points_earned < 2.0
    assert "https://example.com/about-copy" in ct05.affected_urls


def test_orphan_and_broken_link_graph_checks() -> None:
    pages = _strong_site()
    pages.append(_page("https://example.com/hidden", _strong_html("/hidden", "Hidden Page | Example Automation Services", "Hidden", "Hidden", [PARAGRAPHS[0]])))
    broken = _page("https://example.com/services", "<html></html>", status=404)
    pages[3] = broken
    pages[0].internal_links.append("https://example.com/services")
    findings, _ = compute_audit_score_with_caps(pages, "https://example.com", site=GOOD_SITE)
    by_id = {f.check_id: f for f in findings}
    assert "https://example.com/hidden" in by_id["SE09"].affected_urls
    assert by_id["UX04"].points_earned < 2.0
    assert "https://example.com/services" in by_id["UX04"].affected_urls


def test_mixed_content_and_missing_security_headers_are_measured() -> None:
    html = _strong_html("/", "Example Automation | Cloud Engineering and Support", "Hi", "Home", PARAGRAPHS)
    html = html.replace("<main>", '<main><img src="http://cdn.example.com/x.png" alt="x" width="1" height="1">')
    pages = [_page("https://example.com/", html, headers={"server": "nginx/1.18.0"})]
    findings, _ = compute_audit_score_with_caps(pages, "https://example.com", site=GOOD_SITE)
    by_id = {f.check_id: f for f in findings}
    assert by_id["SC02"].status == "fail"
    assert by_id["SC03"].points_earned == 0.0
    assert by_id["SC04"].points_earned == 0.0
    assert by_id["PF04"].points_earned == 0.0


def test_every_scored_finding_has_evidence_or_message_and_valid_points() -> None:
    findings, _ = compute_audit_score_with_caps(_strong_site(), "https://example.com", site=GOOD_SITE)
    ids = [f.check_id for f in findings]
    assert len(ids) == len(set(ids))
    for f in findings:
        assert 0.0 <= f.points_earned <= f.max_points
        assert f.message
        if f.status in ("not_tested", "not_applicable"):
            assert f.points_earned == 0.0


def test_category_max_points_match_weights() -> None:
    findings, _ = compute_audit_score_with_caps(_strong_site(), "https://example.com", site=GOOD_SITE)
    expected = {"availability": 10, "seo": 15, "performance": 15, "ui_ux": 15, "content": 15, "functionality": 15, "security": 5, "accessibility": 10}
    for cat, weight in expected.items():
        assert sum(f.max_points for f in findings if f.category == cat) == weight, cat


def test_keywords_influence_topical_check() -> None:
    with_kw, _ = compute_audit_score_with_caps(_strong_site(), "https://example.com", target_keywords=["blockchain mining"], site=GOOD_SITE)
    without_kw, _ = compute_audit_score_with_caps(_strong_site(), "https://example.com", site=GOOD_SITE)
    a = next(f for f in with_kw if f.check_id == "CT03")
    b = next(f for f in without_kw if f.check_id == "CT03")
    assert a.points_earned < b.points_earned


def test_legacy_perfect_score_calculation() -> None:
    findings = [
        Finding(check_id="TC01", category="technical", severity="critical", passed=True, message="OK"),
        Finding(check_id="OP01", category="onpage", severity="critical", passed=True, message="OK"),
        Finding(check_id="CT01", category="content", severity="warning", passed=True, message="OK"),
        Finding(check_id="PF01", category="performance", severity="warning", passed=True, message="OK"),
    ]
    score = calculate_scores(findings, total_pages=5)
    assert score.overall == 100.0
    assert score.grade == "A"


def test_legacy_penalty_deduction_and_weighting() -> None:
    findings = [
        Finding(check_id="TC01", category="technical", severity="critical", passed=False, message="Insecure HTTP", affected_urls=["http://example.com"]),
        Finding(check_id="OP02", category="onpage", severity="warning", passed=False, message="Short title", affected_urls=["http://example.com"]),
    ]
    score = calculate_scores(findings, total_pages=1)
    assert score.categories["technical"].score == 90.0
    assert score.categories["onpage"].score == 96.0
    assert score.overall == 95.3
