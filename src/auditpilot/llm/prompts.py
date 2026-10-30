"""System and user prompt templates for SEO audit reasoning.

Engineered for token compression (<2,500 tokens input) and factual grounding.
"""

import json
from typing import Any

from auditpilot.models import Finding, PageData

SYSTEM_PROMPT = """You are a Principal Technical SEO Consultant at Cynbit Technologies Private Limited.
Your task is to interpret deterministic technical audit findings for a business client.

CRITICAL INVARIANTS:
1. STRICT FACTUAL GROUNDING: Rely exclusively on the structured audit findings and page data provided. Never hallucinate rankings, traffic estimates, backlink quantities, or fictitious URLs.
2. EVIDENCE CITATIONS: Every action item MUST cite real affected URLs from the provided findings evidence.
3. CONCRETE ACTIONABILITY: State exactly what needs to be changed in code, configuration, or content.
4. TONE & READABILITY: Clear, professional, concise, and business-focused. Avoid unnecessary jargon; explain technical concepts simply.
5. SCHEMA CONFORMANCE: Output must strictly conform to the required JSON schema.
"""


def build_user_prompt(
    target_url: str,
    pages: list[PageData],
    findings: list[Finding],
    scores: dict[str, Any],
    business_description: str | None = None,
    target_keywords: list[str] | None = None,
    competitor_urls: list[str] | None = None,
) -> str:
    """Format structured audit summary into a compact, token-compressed prompt."""
    failed_findings = [f for f in findings if not f.passed]
    passed_findings_count = len([f for f in findings if f.status == "pass" and f.passed])

    # Compress findings: group by category and limit representative URLs to top 4
    compressed_issues = []
    for f in failed_findings:
        compressed_issues.append(
            {
                "check_id": f.check_id,
                "category": f.category,
                "severity": f.severity,
                "issue": f.message,
                "affected_count": len(f.affected_urls),
                "sample_urls": f.affected_urls[:4],
            }
        )

    # Sample top terms from weakest pages
    content_samples = []
    for p in sorted(pages, key=lambda x: x.word_count)[:3]:
        if p.top_terms:
            content_samples.append(
                {
                    "url": p.url,
                    "word_count": p.word_count,
                    "top_terms": p.top_terms[:5],
                }
            )

    summary_payload = {
        "site": {
            "target_url": target_url,
            "pages_crawled": len(pages),
            "overall_score": scores.get("overall", 0),
            "grade": scores.get("grade", "N/A"),
            "category_scores": {
                k: v.get("score") if isinstance(v, dict) else getattr(v, "score", v)
                for k, v in scores.get("categories", {}).items()
            },
        },
        "context": {
            "business_description": business_description or "Digital services and engineering firm",
            "target_keywords": target_keywords or [],
            "competitor_urls": competitor_urls or [],
        },
        "audit_metrics": {
            "passed_checks_count": passed_findings_count,
            "failed_checks_count": len(failed_findings),
            "detected_issues": compressed_issues,
            "content_samples": content_samples,
        },
    }

    prompt_body = f"""Analyze the technical audit findings for: {target_url}

AUDIT DATA SUMMARY (JSON):
```json
{json.dumps(summary_payload, indent=2)}
```

INSTRUCTIONS:
1. Executive Summary: Maximum 120 words. Plain English summarizing the site's overall technical health, primary strengths, and biggest liabilities.
2. Prioritized Action Plan: Up to 10 fixes ordered from highest to lowest priority (Rank 1 to 10). Each must have:
   - title: Direct, actionable directive.
   - why_it_matters: Impact on crawl budget, indexing, or ranking.
   - how_to_fix: Specific technical instructions.
   - affected_urls: Sample URLs from the issues data above.
   - impact: "high", "medium", or "low".
   - effort: "high", "medium", or "low".
3. Quick Wins: List 2-4 items that have high impact and low effort.
4. Content Insights: 2-3 strategic observations based on keywords, word counts, and content coverage.
5. Competitor Notes: Brief comparison notes if competitor URLs were provided, else null.
"""
    return prompt_body
