"""Base interface for LLM providers."""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseLLMClient(ABC):
    """Abstract interface for LLM structured output generation."""

    @abstractmethod
    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> T:
        """Generate structured Pydantic object from system and user prompts.

        Args:
            system_prompt: System instructions and constraints.
            user_prompt: User data and findings payload.
            schema: Pydantic model class to validate and parse output into.

        Returns:
            Validated Pydantic instance matching schema.
        """
        pass
