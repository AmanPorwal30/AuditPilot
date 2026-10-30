"""Tests for SEO checks and check registry."""

from auditpilot.checks.onpage import run_onpage_checks
from auditpilot.checks.registry import registry
from auditpilot.models import PageData


def test_registry_runs_all_categories() -> None:
    """Verify registry executes checks across all categories."""
    pages = [
        PageData(
            url="https://example.com",
            status_code=200,
            final_url="https://example.com",
            title="Example Title Meeting Recommended Length",
            meta_description="A descriptive and well-optimized meta description for example page.",
            h1s=["Example H1 Heading"],
            word_count=450,
            images_total=5,
            images_missing_alt=0,
            internal_links=["https://example.com/about", "https://example.com/contact"],
            canonical="https://example.com",
            response_time_ms=120.0,
            html_size_bytes=15000,
        )
    ]
    findings = registry.run_all(pages)
    assert len(findings) >= 20
    categories = {f.category for f in findings}
    assert "technical" in categories
    assert "onpage" in categories
    assert "content" in categories
    assert "performance" in categories


def test_onpage_checks_detect_violations() -> None:
    """Verify onpage checks detect missing title and multiple H1s."""
    bad_page = PageData(
        url="https://example.com/bad",
        status_code=200,
        final_url="https://example.com/bad",
        title="",  # Missing title
        meta_description="",  # Missing meta
        h1s=["First H1", "Second H1"],  # Violation: multiple H1s
        word_count=120,  # Thin content
        images_total=10,
        images_missing_alt=5,  # 50% missing alt
    )
    findings = run_onpage_checks([bad_page])

    op01 = next(f for f in findings if f.check_id == "OP01")
    assert not op01.passed
    assert "https://example.com/bad" in op01.affected_urls

    op07 = next(f for f in findings if f.check_id == "OP07")
    assert not op07.passed
    assert "https://example.com/bad" in op07.affected_urls
