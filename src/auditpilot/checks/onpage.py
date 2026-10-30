"""On-Page SEO Checks (OP01 - OP11).

OP01: Title present (Critical)
OP02: Title length 30-60 chars (Warning)
OP03: Duplicate titles across pages (Warning)
OP04: Meta description present (Warning)
OP05: Meta description length 70-160 chars (Warning)
OP06: Duplicate meta descriptions (Warning)
OP07: Exactly one H1 per page (Warning)
OP08: Heading hierarchy without skipped levels (Info)
OP09: Image alt text coverage >80% (Warning)
OP10: Internal link count >= 2 (Info)
OP11: Keyword placement in title/H1 (Info)
"""

from collections import Counter
from typing import TYPE_CHECKING

from auditpilot.models import Finding

if TYPE_CHECKING:
    from auditpilot.models import PageData


def run_onpage_checks(
    pages: list["PageData"], target_keywords: list[str] | None = None
) -> list[Finding]:
    """Execute all on-page checks (OP01 to OP11) against the crawled page set."""
    findings: list[Finding] = []
    if not pages:
        return findings

    # OP01: Title Present
    missing_title_urls = [p.url for p in pages if not p.title or not p.title.strip()]
    findings.append(
        Finding(
            check_id="OP01",
            category="onpage",
            severity="critical",
            passed=len(missing_title_urls) == 0,
            message=(
                "All pages have a title tag."
                if len(missing_title_urls) == 0
                else f"{len(missing_title_urls)} page(s) missing title tag."
            ),
            affected_urls=missing_title_urls,
            evidence={"missing_count": len(missing_title_urls)},
        )
    )

    # OP02: Title Length (30 to 60 characters)
    bad_length_titles = [
        p.url for p in pages if p.title and (len(p.title) < 30 or len(p.title) > 60)
    ]
    findings.append(
        Finding(
            check_id="OP02",
            category="onpage",
            severity="warning",
            passed=len(bad_length_titles) == 0,
            message=(
                "All page titles are within optimal length (30-60 characters)."
                if len(bad_length_titles) == 0
                else f"{len(bad_length_titles)} page(s) have suboptimal title length (<30 or >60 chars)."
            ),
            affected_urls=bad_length_titles,
            evidence={"suboptimal_count": len(bad_length_titles)},
        )
    )

    # OP03: Duplicate Titles
    titles = [p.title.strip() for p in pages if p.title and p.title.strip()]
    title_counts = Counter(titles)
    duplicate_titles = {t for t, c in title_counts.items() if c > 1}
    dup_title_urls = [p.url for p in pages if p.title and p.title.strip() in duplicate_titles]
    findings.append(
        Finding(
            check_id="OP03",
            category="onpage",
            severity="warning",
            passed=len(duplicate_titles) == 0,
            message=(
                "No duplicate page titles detected."
                if len(duplicate_titles) == 0
                else f"Found {len(duplicate_titles)} duplicate title(s) across {len(dup_title_urls)} page(s)."
            ),
            affected_urls=dup_title_urls,
            evidence={"duplicate_titles": list(duplicate_titles)[:5]},
        )
    )

    # OP04: Meta Description Present
    missing_desc_urls = [
        p.url for p in pages if not p.meta_description or not p.meta_description.strip()
    ]
    findings.append(
        Finding(
            check_id="OP04",
            category="onpage",
            severity="warning",
            passed=len(missing_desc_urls) == 0,
            message=(
                "All pages have a meta description tag."
                if len(missing_desc_urls) == 0
                else f"{len(missing_desc_urls)} page(s) missing meta description."
            ),
            affected_urls=missing_desc_urls,
            evidence={"missing_count": len(missing_desc_urls)},
        )
    )

    # OP05: Meta Description Length (70 to 160 characters)
    bad_length_descs = [
        p.url
        for p in pages
        if p.meta_description and (len(p.meta_description) < 70 or len(p.meta_description) > 160)
    ]
    findings.append(
        Finding(
            check_id="OP05",
            category="onpage",
            severity="warning",
            passed=len(bad_length_descs) == 0,
            message=(
                "All meta descriptions are within recommended length (70-160 characters)."
                if len(bad_length_descs) == 0
                else f"{len(bad_length_descs)} page(s) have meta description outside 70-160 characters."
            ),
            affected_urls=bad_length_descs,
            evidence={"suboptimal_count": len(bad_length_descs)},
        )
    )

    # OP06: Duplicate Meta Descriptions
    descs = [
        p.meta_description.strip()
        for p in pages
        if p.meta_description and p.meta_description.strip()
    ]
    desc_counts = Counter(descs)
    duplicate_descs = {d for d, c in desc_counts.items() if c > 1}
    dup_desc_urls = [
        p.url for p in pages if p.meta_description and p.meta_description.strip() in duplicate_descs
    ]
    findings.append(
        Finding(
            check_id="OP06",
            category="onpage",
            severity="warning",
            passed=len(duplicate_descs) == 0,
            message=(
                "No duplicate meta descriptions detected."
                if len(duplicate_descs) == 0
                else f"Found {len(duplicate_descs)} duplicate meta description(s) across {len(dup_desc_urls)} page(s)."
            ),
            affected_urls=dup_desc_urls,
            evidence={"duplicate_count": len(duplicate_descs)},
        )
    )

    # OP07: Exactly One H1 Tag
    h1_violation_urls = [p.url for p in pages if len(p.h1s) != 1]
    findings.append(
        Finding(
            check_id="OP07",
            category="onpage",
            severity="warning",
            passed=len(h1_violation_urls) == 0,
            message=(
                "All pages contain exactly one H1 tag."
                if len(h1_violation_urls) == 0
                else f"{len(h1_violation_urls)} page(s) violate single H1 guideline (found 0 or multiple H1s)."
            ),
            affected_urls=h1_violation_urls,
            evidence={"violation_count": len(h1_violation_urls)},
        )
    )

    # OP08: Heading Hierarchy (no skipped levels, e.g. H2 -> H4)
    skipped_hierarchy_urls: list[str] = []
    for p in pages:
        prev_level = 1
        for level, _ in p.headings:
            if level > prev_level + 1:
                skipped_hierarchy_urls.append(p.url)
                break
            prev_level = level

    findings.append(
        Finding(
            check_id="OP08",
            category="onpage",
            severity="info",
            passed=len(skipped_hierarchy_urls) == 0,
            message=(
                "Heading hierarchy is consistent with no skipped levels."
                if len(skipped_hierarchy_urls) == 0
                else f"{len(skipped_hierarchy_urls)} page(s) have skipped heading hierarchy levels (e.g. H2 directly to H4)."
            ),
            affected_urls=skipped_hierarchy_urls,
            evidence={"skipped_count": len(skipped_hierarchy_urls)},
        )
    )

    # OP09: Image Alt Text (Flag if >20% missing alt text)
    missing_alt_pages = []
    total_imgs = sum(p.images_total for p in pages)
    total_missing = sum(p.images_missing_alt for p in pages)
    for p in pages:
        if p.images_total > 0 and (p.images_missing_alt / p.images_total) > 0.2:
            missing_alt_pages.append(p.url)

    findings.append(
        Finding(
            check_id="OP09",
            category="onpage",
            severity="warning",
            passed=len(missing_alt_pages) == 0,
            message=(
                f"Image alt attributes are well-maintained ({total_missing}/{total_imgs} missing alt)."
                if len(missing_alt_pages) == 0
                else f"{len(missing_alt_pages)} page(s) have >20% images missing alt text ({total_missing}/{total_imgs} images unannotated)."
            ),
            affected_urls=missing_alt_pages,
            evidence={"total_images": total_imgs, "missing_alt": total_missing},
        )
    )

    # OP10: Internal Link Count (Pages with < 2 internal links)
    low_internal_urls = [p.url for p in pages if len(p.internal_links) < 2]
    findings.append(
        Finding(
            check_id="OP10",
            category="onpage",
            severity="info",
            passed=len(low_internal_urls) == 0,
            message=(
                "All pages have adequate internal link connectivity (>= 2 internal links)."
                if len(low_internal_urls) == 0
                else f"{len(low_internal_urls)} page(s) have fewer than 2 internal links."
            ),
            affected_urls=low_internal_urls,
            evidence={"low_link_pages": len(low_internal_urls)},
        )
    )

    # OP11: Keyword Placement
    if target_keywords:
        kw_missing_urls = []
        kw_clean = [k.strip().lower() for k in target_keywords if k.strip()]
        for p in pages:
            text_to_check = f"{p.title or ''} {' '.join(p.h1s)}".lower()
            if not any(k in text_to_check for k in kw_clean):
                kw_missing_urls.append(p.url)

        findings.append(
            Finding(
                check_id="OP11",
                category="onpage",
                severity="info",
                passed=len(kw_missing_urls) == 0,
                message=(
                    "Target keywords detected in title or H1 tags across crawled pages."
                    if len(kw_missing_urls) == 0
                    else f"{len(kw_missing_urls)} page(s) do not contain target keywords in Title or H1."
                ),
                affected_urls=kw_missing_urls,
                evidence={"target_keywords": target_keywords},
            )
        )

    return findings
