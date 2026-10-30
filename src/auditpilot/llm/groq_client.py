"""Groq LLM client for fast, free-tier inference using the groq SDK."""

import json
import logging
import os
from typing import TypeVar

from groq import Groq
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from auditpilot.config import settings
from auditpilot.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GroqClient(BaseLLMClient):
    """Groq API client utilizing free models (Llama 3.3 70B / Llama 3.1 8B)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        """Initialize Groq client with API key and model selection."""
        self.api_key = api_key or settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
        self.model = model or settings.GROQ_MODEL or "llama-3.3-70b-versatile"
        self._client: Groq | None = None

    def _get_client(self) -> Groq:
        """Lazy initialization of Groq client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "GROQ_API_KEY is not set. Please set GROQ_API_KEY in your environment or .env file."
                )
            self._client = Groq(api_key=self.api_key)
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
        """Generate structured Pydantic object using Groq's JSON mode.

        Args:
            system_prompt: Guiding system rules and constraints.
            user_prompt: Findings payload to interpret.
            schema: Pydantic model to parse and validate into.

        Returns:
            Validated instance of schema.
        """
        client = self._get_client()

        # Augment system prompt with explicit JSON schema definition
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        augmented_system = (
            f"{system_prompt}\n\n"
            f"You MUST output valid JSON matching this schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"Respond with raw JSON only. Do not enclose in markdown codeblocks."
        )

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": augmented_system},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        raw_content = response.choices[0].message.content or "{}"

        # Clean any accidental markdown backticks
        cleaned_content = raw_content.strip()
        if cleaned_content.startswith("```"):
            cleaned_content = cleaned_content.split("\n", 1)[-1]
            if cleaned_content.endswith("```"):
                cleaned_content = cleaned_content.rsplit("\n", 1)[0]
            cleaned_content = cleaned_content.strip()

        return schema.model_validate_json(cleaned_content)
