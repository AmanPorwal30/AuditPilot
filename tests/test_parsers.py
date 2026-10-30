"""Tests for HTML DOM parser."""

from auditpilot.parsers import parse_page_html


def test_parse_page_html_full_features() -> None:
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Test Page Title for SEO Parsing</title>
        <meta name="description" content="This is an exact meta description for testing the parser.">
        <link rel="canonical" href="https://example.com/canonical-page">
        <meta name="robots" content="index, follow">
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Cynbit Technologies"
        }
        </script>
    </head>
    <body>
        <h1>Primary H1 Heading</h1>
        <h2>Secondary H2 Heading</h2>
        <p>This is paragraph content with multiple descriptive words to ensure word count exceeds twenty words easily.</p>
        <img src="logo.png" alt="Company Logo">
        <img src="banner.png">
        <a href="/about">About</a>
        <a href="https://external.com/partner">External</a>
    </body>
    </html>
    """
    page = parse_page_html(
        url="https://example.com",
        html=html,
        status_code=200,
        response_time_ms=150.0,
        html_size_bytes=len(html),
    )

    assert page.title == "Test Page Title for SEO Parsing"
    assert page.meta_description == "This is an exact meta description for testing the parser."
    assert page.canonical == "https://example.com/canonical-page"
    assert page.h1s == ["Primary H1 Heading"]
    assert len(page.headings) == 2
    assert page.word_count > 15
    assert page.images_total == 2
    assert page.images_missing_alt == 1
    assert "https://example.com/about" in page.internal_links
    assert "https://external.com/partner" in page.external_links
    assert "Organization" in page.json_ld_types

