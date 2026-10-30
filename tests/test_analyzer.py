"""Tests for free-tier LLM analyzer, grounding verification, and fallback engine."""

from unittest.mock import MagicMock, patch

from auditpilot.llm.analyzer import SEOAnalyzer
from auditpilot.llm.base import BaseLLMClient
from auditpilot.llm.gemini_client import GeminiClient
from auditpilot.llm.groq_client import GroqClient
from auditpilot.models import ActionItem, Finding, LLMReport, PageData


class FakeLLMClient(BaseLLMClient):
    """Fake client returning predefined structured response without network."""

    def __init__(self, response: LLMReport) -> None:
        self.response = response

    def generate_structured(self, system_prompt: str, user_prompt: str, schema):
        return self.response


def test_analyzer_deterministic_fallback() -> None:
    """Verify fallback engine generates valid report when no API keys are present."""
    with patch.dict("os.environ", {"GROQ_API_KEY": "", "GEMINI_API_KEY": ""}):
        analyzer = SEOAnalyzer()
        analyzer.client = None
        pages = [
            PageData(url="https://example.com", status_code=200, final_url="https://example.com"),
            PageData(
                url="https://example.com/about", status_code=200, final_url="https://example.com/about"
            ),
        ]
        findings = [
            Finding(
                check_id="OP01",
                category="onpage",
                severity="critical",
                passed=False,
                message="Title tag missing",
                affected_urls=["https://example.com/about"],
            ),
            Finding(
                check_id="TC01",
                category="technical",
                severity="warning",
                passed=False,
                message="Redirect chain detected",
                affected_urls=["https://example.com"],
            ),
        ]
        scores = {"overall": 80.0, "grade": "B", "categories": {}}

        report = analyzer.analyze("https://example.com", pages, findings, scores)

        assert isinstance(report, LLMReport)
        assert "example.com" in report.executive_summary
        assert len(report.action_plan) == 2
        assert report.action_plan[0].rank == 1
        assert report.action_plan[0].impact == "high"  # Critical severity mapped to high impact


def test_analyzer_grounding_filter_removes_hallucinations() -> None:
    """Verify that hallucinated URLs not present in crawl data are pruned."""
    fake_report = LLMReport(
        executive_summary="Summary",
        action_plan=[
            ActionItem(
                rank=1,
                title="Fix Title",
                why_it_matters="SEO",
                how_to_fix="Add title",
                affected_urls=[
                    "https://example.com/real-page",
                    "https://example.com/hallucinated-fake-page",
                ],
                impact="high",
                effort="low",
            )
        ],
        quick_wins=["Win 1"],
        content_insights=["Insight 1"],
    )

    client = FakeLLMClient(fake_report)
    analyzer = SEOAnalyzer(client=client)

    pages = [
        PageData(
            url="https://example.com/real-page",
            status_code=200,
            final_url="https://example.com/real-page",
        )
    ]
    report = analyzer.analyze("https://example.com", pages, [], {})

    # The hallucinated page must be pruned
    assert "https://example.com/real-page" in report.action_plan[0].affected_urls
    assert "https://example.com/hallucinated-fake-page" not in report.action_plan[0].affected_urls


def test_groq_client_structured_generation() -> None:
    """Verify GroqClient parses chat completion JSON output into Pydantic schema."""
    client = GroqClient(api_key="gsk_test_key")

    mock_chat_completion = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"rank": 1, "title": "Test Item", "why_it_matters": "Why", "how_to_fix": "How", "affected_urls": [], "impact": "low", "effort": "low"}'
    mock_chat_completion.choices = [mock_choice]

    with patch.object(client, "_get_client") as mock_get_client:
        mock_groq = MagicMock()
        mock_groq.chat.completions.create.return_value = mock_chat_completion
        mock_get_client.return_value = mock_groq

        res = client.generate_structured("sys", "user", ActionItem)
        assert isinstance(res, ActionItem)
        assert res.title == "Test Item"
        assert res.rank == 1


def test_gemini_client_structured_generation() -> None:
    """Verify GeminiClient parses models.generate_content into Pydantic schema."""
    client = GeminiClient(api_key="gemini_test_key")

    mock_response = MagicMock()
    mock_response.text = '{"rank": 2, "title": "Gemini Item", "why_it_matters": "Why", "how_to_fix": "How", "affected_urls": [], "impact": "high", "effort": "medium"}'

    with patch.object(client, "_get_client") as mock_get_client:
        mock_gemini = MagicMock()
        mock_gemini.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_gemini

        res = client.generate_structured("sys", "user", ActionItem)
        assert isinstance(res, ActionItem)
        assert res.title == "Gemini Item"
        assert res.rank == 2
