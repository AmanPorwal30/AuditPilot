"""SEO Analyzer orchestrating free-tier LLM reasoning, grounding, and fallback."""

import logging
from typing import Any

from auditpilot.config import settings
from auditpilot.llm.base import BaseLLMClient
from auditpilot.llm.gemini_client import GeminiClient
from auditpilot.llm.groq_client import GroqClient
from auditpilot.llm.prompts import SYSTEM_PROMPT, build_user_prompt
from auditpilot.models import ActionItem, Finding, LLMReport, PageData

logger = logging.getLogger(__name__)


class SEOAnalyzer:
    """Orchestrates LLM analysis with retry, grounding verification, and fallback."""

    def __init__(self, client: BaseLLMClient | None = None) -> None:
        """Initialize with provided client or resolve from free-tier configuration."""
        self.client = client

    def _resolve_client(self) -> BaseLLMClient | None:
        """Resolve available free-tier client (Groq or Gemini)."""
        if self.client is not None:
            return self.client

        provider = settings.LLM_PROVIDER.lower()

        # 1. Check primary configured provider
        if provider == "groq" and settings.GROQ_API_KEY:
            return GroqClient()
        if provider == "gemini" and settings.GEMINI_API_KEY:
            return GeminiClient()

        # 2. Check alternative free provider if primary key is missing
        if settings.GROQ_API_KEY:
            logger.info("Using Groq free-tier client.")
            return GroqClient()
        if settings.GEMINI_API_KEY:
            logger.info("Using Gemini free-tier client.")
            return GeminiClient()

        logger.warning("No LLM API keys detected. Falling back to deterministic rule engine.")
        return None

    def analyze(
        self,
        target_url: str,
        pages: list[PageData],
        findings: list[Finding],
        scores: dict[str, Any],
        business_description: str | None = None,
        target_keywords: list[str] | None = None,
        competitor_urls: list[str] | None = None,
    ) -> LLMReport:
        """Run token-budgeted analysis with grounding validation and fallback."""
        client = self._resolve_client()

        if client is not None:
            user_prompt = build_user_prompt(
                target_url=target_url,
                pages=pages,
                findings=findings,
                scores=scores,
                business_description=business_description,
                target_keywords=target_keywords,
                competitor_urls=competitor_urls,
            )

            try:
                report = client.generate_structured(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    schema=LLMReport,
                )
                # Verify grounding against crawled page URLs
                return self._verify_grounding(report, pages, target_url)
            except Exception as e:
                logger.error(f"LLM generation failed: {e}. Triggering deterministic rule fallback.")

        # Fallback to deterministic rule engine
        return self._generate_rule_based_fallback(
            target_url=target_url,
            pages=pages,
            findings=findings,
            scores=scores,
        )

    def _verify_grounding(
        self, report: LLMReport, pages: list[PageData], target_url: str
    ) -> LLMReport:
        """Verify that all URLs cited by the LLM exist in the crawled dataset."""
        valid_urls = {p.url for p in pages} | {p.final_url for p in pages}

        for item in report.action_plan:
            # Filter out any hallucinated URLs
            grounded_urls = [u for u in item.affected_urls if u in valid_urls]
            if not grounded_urls and valid_urls:
                # If all cited URLs were invalid, fall back to target_url
                grounded_urls = [target_url]
            item.affected_urls = grounded_urls

        return report

    def _generate_rule_based_fallback(
        self,
        target_url: str,
        pages: list[PageData],
        findings: list[Finding],
        scores: dict[str, Any],
    ) -> LLMReport:
        """Deterministic rule-based report generator when LLM API is unavailable."""
        failed = [f for f in findings if not f.passed]

        # Sort: Critical first, then Warning, then Info
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        failed.sort(key=lambda x: severity_order.get(x.severity, 3))

        action_plan: list[ActionItem] = []
        quick_wins: list[str] = []

        for rank, f in enumerate(failed[:10], start=1):
            impact = (
                "high"
                if f.severity == "critical"
                else "medium"
                if f.severity == "warning"
                else "low"
            )
            effort = "low" if f.check_id in ("OP01", "OP02", "OP04", "OP07", "OP09") else "medium"

            title = f"Resolve {f.category.capitalize()} Issue: {f.check_id}"
            why = f"{f.message} Addressing this improves crawler accessibility and indexing health."
            how = "Audit affected URLs and update the corresponding HTML tags or server configuration."

            item = ActionItem(
                rank=rank,
                title=title,
                why_it_matters=why,
                how_to_fix=how,
                affected_urls=f.affected_urls[:5] if f.affected_urls else [target_url],
                impact=impact,
                effort=effort,
            )
            action_plan.append(item)

            if impact == "high" and effort == "low" and len(quick_wins) < 3:
                quick_wins.append(f"{title} (Impact: High, Effort: Low)")

        overall_score = scores.get("overall", 85.0)
        grade = scores.get("grade", "B")

        exec_summary = (
            f"Technical audit for {target_url} completed across {len(pages)} crawled pages. "
            f"Overall SEO health score is {overall_score:.1f}/100 (Grade {grade}). "
            f"Identified {len(failed)} areas requiring attention across on-page tags, technical infrastructure, "
            f"and performance baselines."
        )

        content_insights = [
            f"Crawled inventory covers {len(pages)} distinct pages.",
            "Prioritize meta tag optimization and image alt attribute hygiene across primary templates.",
        ]

        return LLMReport(
            executive_summary=exec_summary,
            action_plan=action_plan,
            quick_wins=quick_wins
            if quick_wins
            else ["Optimize missing title and meta tags across crawled pages."],
            content_insights=content_insights,
            competitor_notes=None,
        )
