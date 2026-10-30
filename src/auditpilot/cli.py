"""Command Line Interface (CLI) for AuditPilot.

Usage:
  python -m auditpilot.cli https://cynbit.in --max-pages 10
"""

import argparse
import asyncio
import os
import sys

from auditpilot.crawler import AsyncCrawler
from auditpilot.llm.analyzer import SEOAnalyzer
from auditpilot.scoring import CATEGORY_WEIGHTS, compute_audit_score_with_caps
from auditpilot.validators import is_safe_url, normalize_url


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="auditpilot",
        description="AuditPilot: Autonomous Technical SEO Audit Agent by Cynbit",
    )
    parser.add_argument("url", help="Target website URL to audit")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=25,
        help="Maximum pages to crawl (default: 25, cap: 50)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Concurrent crawl workers (default: 5)",
    )
    parser.add_argument(
        "--output-dir",
        default="./reports",
        help="Directory to save generated reports (default: ./reports)",
    )
    parser.add_argument(
        "--keywords",
        help="Comma-separated target keywords for placement checks",
    )
    parser.add_argument(
        "--description",
        help="Short business description to improve LLM recommendations",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Run deterministic checks and scoring only, skip LLM reasoning",
    )
    return parser.parse_args(args)


async def run_cli_audit(args: argparse.Namespace) -> int:
    """Execute end-to-end audit from CLI."""
    target_url = args.url

    # 1. SSRF & Scheme Validation
    is_safe, reason = is_safe_url(target_url)
    if not is_safe:
        print(f"❌ Security Error: {reason}", file=sys.stderr)
        return 1

    norm_url = normalize_url(target_url)
    print(f"\n⚡ Starting AuditPilot for: {norm_url}")
    print(f"⚙️ Config: Max pages={args.max_pages}, Concurrency={args.concurrency}\n")

    # 2. Async Crawl
    crawler = AsyncCrawler(
        base_url=norm_url,
        max_pages=args.max_pages,
        concurrency=args.concurrency,
    )
    pages = []
    print("🕷️ Crawling pages...")
    async for page in crawler.crawl():
        status_marker = "✅" if page.status_code == 200 else "⚠️"
        print(
            f"  {status_marker} [{page.status_code}] {page.url} ({page.response_time_ms:.0f}ms, {page.word_count} words)"
        )
        pages.append(page)

    if not pages:
        print(
            "❌ No pages could be crawled. Check robots.txt or site accessibility.", file=sys.stderr
        )
        return 1

    print(f"\n📊 Crawl completed: {len(pages)} page(s) analyzed.")

    # 3 & 4. Evidence-Based Checks & Mathematical Scoring with Caps
    keywords_list = [k.strip() for k in args.keywords.split(",")] if args.keywords else None
    print("🔍 Executing evidence-based checks across 8 categories with critical caps...")
    findings, score = compute_audit_score_with_caps(
        pages=pages,
        target_url=norm_url,
        target_keywords=keywords_list,
        site=crawler.site_signals,
    )

    print("\n" + "=" * 65)
    print(f"🏁 AUDIT RESULTS: {norm_url}")
    print(f"Overall Health Score: {score.overall}/100 (Grade {score.grade} - Rating: {score.rating})")
    print(
        f"Confidence: {score.confidence.capitalize()} | Raw: {score.raw_score}/100 "
        f"| Coverage: {score.coverage_percent:.0f}%"
    )
    if score.not_tested_checks:
        print(f"Not tested (excluded from score): {', '.join(score.not_tested_checks)}")
    if score.score_caps_applied:
        print("⚠️ Critical Issue Caps Applied:")
        for cap in score.score_caps_applied:
            print(f"   - {cap}")
    print("=" * 65)
    for _cat_key, cs in score.categories.items():
        if cs.id in CATEGORY_WEIGHTS:
            print(
                f"  • {cs.name:<28}: {cs.earned_points:>4.1f}/{cs.max_points:>4.1f} pts ({cs.score:>5.1f}%) [Grade {cs.grade}] coverage {cs.coverage_percent:.0f}%"
            )
    print("=" * 65)

    # 5. LLM Analysis Layer
    if not args.no_llm:
        print("\n🤖 Running Free AI Reasoning Layer (Groq / Gemini)...")
        analyzer = SEOAnalyzer()
        scores_dict = {
            "overall": score.overall,
            "grade": score.grade,
            "categories": {k: {"score": v.score} for k, v in score.categories.items()},
        }
        llm_report = analyzer.analyze(
            target_url=norm_url,
            pages=pages,
            findings=findings,
            scores=scores_dict,
            business_description=args.description,
            target_keywords=keywords_list,
        )

        print("\n📋 Executive Summary:")
        print(f"  {llm_report.executive_summary}\n")

        print("⚡ Top Action Items:")
        for item in llm_report.action_plan[:5]:
            print(
                f"  #{item.rank} [{item.impact.upper()} IMPACT | {item.effort.upper()} EFFORT] {item.title}"
            )
            print(f"     Why: {item.why_it_matters}")
            print(f"     Fix: {item.how_to_fix}")

        if llm_report.quick_wins:
            print("\n🎯 Quick Wins:")
            for qw in llm_report.quick_wins:
                print(f"  • {qw}")

    # 6. Save Reports to disk
    os.makedirs(args.output_dir, exist_ok=True)
    domain_clean = norm_url.split("//")[-1].split("/")[0].replace(":", "_")
    report_file = os.path.join(args.output_dir, f"audit_{domain_clean}.md")

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"# SEO Technical Audit: {norm_url}\n")
        f.write(f"**Overall Score:** {score.overall}/100 (Grade {score.grade})\n")
        f.write(f"**Pages Crawled:** {len(pages)}\n\n")
        for _cat_key, cs in score.categories.items():
            if cs.id in CATEGORY_WEIGHTS:
                f.write(f"- **{cs.name}:** {cs.score}% (Grade {cs.grade})\n")

    print(f"\n💾 Report saved to: {report_file}")
    return 0


def main() -> int:
    """CLI main entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    return asyncio.run(run_cli_audit(args))


if __name__ == "__main__":
    sys.exit(main())
