"""Check registry for AuditPilot.

Manages registration and execution of deterministic SEO checks.
"""

from auditpilot.checks.content import run_content_checks
from auditpilot.checks.onpage import run_onpage_checks
from auditpilot.checks.performance import run_perf_checks
from auditpilot.checks.technical import run_technical_checks
from auditpilot.models import Finding, PageData


class CheckRegistry:
    """Registry maintaining active check functions and their metadata."""

    def run_all(
        self,
        pages: list[PageData],
        target_keywords: list[str] | None = None,
        pagespeed_api_key: str | None = None,
    ) -> list[Finding]:
        """Execute all 27 deterministic SEO checks across all categories.

        Args:
            pages: List of crawled PageData instances.
            target_keywords: Optional keywords for placement checks.
            pagespeed_api_key: Optional Google PageSpeed API key.

        Returns:
            List of generated Finding objects with evidence.
        """
        findings: list[Finding] = []
        findings.extend(run_technical_checks(pages))
        findings.extend(run_onpage_checks(pages, target_keywords=target_keywords))
        findings.extend(run_content_checks(pages))
        findings.extend(run_perf_checks(pages, pagespeed_api_key=pagespeed_api_key))
        return findings


registry = CheckRegistry()
