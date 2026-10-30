"""Google Gemini LLM client using the official google-genai SDK."""

import logging
import os
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from auditpilot.config import settings
from auditpilot.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiClient(BaseLLMClient):
    """Gemini API client with structured JSON output and free-tier support."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        """Initialize Gemini client with API key and model selection."""
        self.api_key = api_key or settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        self.model = model or settings.GEMINI_MODEL or "gemini-1.5-flash"
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        """Lazy initialization of Gemini Client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "GEMINI_API_KEY is not set. Please set GEMINI_API_KEY in your environment or .env file."
                )
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> T:
        """Generate structured Pydantic object via Gemini API.

        Args:
            system_prompt: System instructions and grounding constraints.
            user_prompt: Compact findings payload.
            schema: Pydantic model class for response schema.

        Returns:
            Validated Pydantic instance matching schema.
        """
        client = self._get_client()

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.2,
        )

        response = client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=config,
        )

        raw_text = response.text or "{}"
        return schema.model_validate_json(raw_text)
