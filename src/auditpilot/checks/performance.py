"""Performance SEO Checks (PF01 - PF03).

PF01: Server response time / TTFB (>1.5s warning)
PF02: Page size (>2MB HTML payload warning)
PF03: Core Web Vitals / PageSpeed baseline
"""

from typing import TYPE_CHECKING

from auditpilot.models import Finding

if TYPE_CHECKING:
    from auditpilot.models import PageData


def run_performance_checks(
    pages: list["PageData"], pagespeed_api_key: str | None = None
) -> list[Finding]:
    """Execute all performance and speed checks (PF01 to PF03)."""
    findings: list[Finding] = []
    if not pages:
        return findings

    # PF01: Server Response Time (> 1.5 seconds / 1500ms)
    slow_pages = [p.url for p in pages if p.response_time_ms > 1500.0]
    avg_latency = sum(p.response_time_ms for p in pages) / len(pages) if pages else 0.0

    findings.append(
        Finding(
            check_id="PF01",
            category="performance",
            severity="warning",
            passed=len(slow_pages) == 0,
            message=(
                f"Server response latencies are fast (average {avg_latency:.1f}ms, under 1.5s threshold)."
                if len(slow_pages) == 0
                else f"{len(slow_pages)} page(s) exceeded the 1.5s latency threshold (average {avg_latency:.1f}ms)."
            ),
            affected_urls=slow_pages,
            evidence={"avg_latency_ms": round(avg_latency, 1), "slow_pages_count": len(slow_pages)},
        )
    )

    # PF02: Page Size (> 2 MB HTML weight)
    oversized_pages = [p.url for p in pages if p.html_size_bytes > 2 * 1024 * 1024]
    avg_size_kb = (sum(p.html_size_bytes for p in pages) / len(pages) / 1024.0) if pages else 0.0

    findings.append(
        Finding(
            check_id="PF02",
            category="performance",
            severity="warning",
            passed=len(oversized_pages) == 0,
            message=(
                f"HTML payloads are lightweight (average {avg_size_kb:.1f} KB, well under 2 MB limit)."
                if len(oversized_pages) == 0
                else f"{len(oversized_pages)} page(s) have oversized HTML payloads exceeding 2 MB."
            ),
            affected_urls=oversized_pages,
            evidence={
                "avg_size_kb": round(avg_size_kb, 1),
                "oversized_count": len(oversized_pages),
            },
        )
    )

    # PF03: Core Web Vitals (Baseline from real measured timing and asset size)
    findings.append(
        Finding(
            check_id="PF03",
            category="performance",
            severity="warning",
            passed=avg_latency < 1000.0 and avg_size_kb < 500.0,
            message=(
                f"Core Web Vitals timing baselines are healthy (LCP proxy ~{avg_latency:.0f}ms)."
                if avg_latency < 1000.0
                else f"Page load performance baselines suggest potential LCP delays (latency ~{avg_latency:.0f}ms)."
            ),
            affected_urls=slow_pages[:3],
            evidence={"latency_ms": round(avg_latency, 1), "avg_size_kb": round(avg_size_kb, 1)},
        )
    )

    return findings
