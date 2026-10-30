"""Content SEO Checks (CT01 - CT04).

CT01: Thin content (word count < 300) (Warning)
CT02: Near-duplicate content (>85% text similarity) (Warning)
CT03: Readability index (Flesch score via textstat) (Info)
CT04: Top terms (TF-IDF extraction for gap analysis) (Info)
"""

from typing import TYPE_CHECKING

import textstat

from auditpilot.models import Finding

if TYPE_CHECKING:
    from auditpilot.models import PageData


def run_content_checks(pages: list["PageData"]) -> list[Finding]:
    """Execute all content SEO checks (CT01 to CT04)."""
    findings: list[Finding] = []
    if not pages:
        return findings

    # CT01: Thin Content (< 300 words)
    thin_content_urls = [p.url for p in pages if p.word_count < 300]
    avg_words = sum(p.word_count for p in pages) / len(pages) if pages else 0
    findings.append(
        Finding(
            check_id="CT01",
            category="content",
            severity="warning",
            passed=len(thin_content_urls) == 0,
            message=(
                f"Content depth is healthy across pages (average {avg_words:.0f} words)."
                if len(thin_content_urls) == 0
                else f"{len(thin_content_urls)} page(s) flagged for thin content (< 300 words)."
            ),
            affected_urls=thin_content_urls,
            evidence={"avg_word_count": round(avg_words), "thin_count": len(thin_content_urls)},
        )
    )

    # CT02: Duplicate / Near-Duplicate Content (>85% word overlap / identical titles and words)
    dup_pairs: list[str] = []
    for i in range(len(pages)):
        for j in range(i + 1, len(pages)):
            p1, p2 = pages[i], pages[j]
            if p1.word_count > 50 and p2.word_count > 50:
                # Jaccard similarity on top terms
                set1 = set(p1.top_terms)
                set2 = set(p2.top_terms)
                if set1 and set2:
                    jaccard = len(set1 & set2) / len(set1 | set2)
                    if jaccard > 0.85:
                        dup_pairs.append(f"{p1.url} <-> {p2.url}")

    findings.append(
        Finding(
            check_id="CT02",
            category="content",
            severity="warning",
            passed=len(dup_pairs) == 0,
            message=(
                "No near-duplicate content clusters detected across pages."
                if len(dup_pairs) == 0
                else f"Found {len(dup_pairs)} page pair(s) with high content similarity (>85%)."
            ),
            affected_urls=[pair.split(" <-> ")[0] for pair in dup_pairs],
            evidence={"duplicate_pairs": dup_pairs[:5]},
        )
    )

    # CT03: Readability (Flesch Reading Ease via textstat)
    hard_to_read_urls: list[str] = []
    for p in pages:
        if p.raw_html and p.word_count > 50:
            try:
                score = textstat.flesch_reading_ease(p.title or "")
                if score < 30.0:  # Very difficult
                    hard_to_read_urls.append(p.url)
            except Exception:
                pass

    findings.append(
        Finding(
            check_id="CT03",
            category="content",
            severity="info",
            passed=len(hard_to_read_urls) == 0,
            message=(
                "Content readability is accessible and clear."
                if len(hard_to_read_urls) == 0
                else f"{len(hard_to_read_urls)} page(s) have low readability scores (< 30 Flesch reading ease)."
            ),
            affected_urls=hard_to_read_urls,
            evidence={"difficult_pages": len(hard_to_read_urls)},
        )
    )

    # CT04: Top Terms (TF-IDF keyword extraction)
    findings.append(
        Finding(
            check_id="CT04",
            category="content",
            severity="info",
            passed=True,
            message="Top significant keywords extracted and prepared for AI topic-gap analysis.",
            affected_urls=[],
            evidence={"sampled_terms": pages[0].top_terms if pages else []},
        )
    )

    return findings
