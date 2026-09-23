"""
ModelProvider interface and MockProvider implementation.

ModelProvider.generate_structured() is the ONLY path through which LLMs
are called. Every call MUST go through agents/policy.py first.
See Implementation Plan [M3], [A6].
"""
from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Type

from pydantic import BaseModel

from app.schemas.finding import RawLLMFinding, RawLLMResponse
from app.models.finding import EvidenceKind, Severity
from app.errors import ConfigurationError
# Module-level import for test patching target: app.agents.llm_provider.get_settings
from app.config import get_settings

logger = logging.getLogger(__name__)


class ModelProvider(ABC):
    """Abstract interface for all LLM providers."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
    ) -> RawLLMResponse:
        """
        Call the LLM with the given prompt and parse the response
        into the given Pydantic schema.

        MUST be called only after the policy layer has verified budget/deadline.
        MUST retry-once on schema validation failure (handled in policy.py).
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name for logging."""
        ...


class MockProvider(ModelProvider):
    """
    Deterministic mock LLM provider for offline testing and CI.
    Same input → same output, same order, same fingerprints. [A6]
    No network calls, no API keys required.
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
    ) -> Any:
        """
        Return a deterministic response based on a hash of the prompt content.
        Supports RawLLMResponse, PatchDraft, and PRReviewDraftOutput schemas.
        """
        # Support PatchDraft schema
        if schema.__name__ == "PatchDraft":
            diff = (
                "--- a/file.py\n"
                "+++ b/file.py\n"
                "@@ -1,3 +1,3 @@\n"
                "-# vulnerable\n"
                "+# remediated\n"
            )
            return schema(
                unified_diff=diff,
                rationale="Remediate vulnerability with safe input sanitization.",
                assumptions="Assumes clean caller parameters.",
                tests_to_run=["pytest tests/test_security.py"],
            )

        # Support PRReviewDraftOutput schema
        if schema.__name__ == "PRReviewDraftOutput":
            return schema(
                summary_markdown="### Vigil Governed PR Review\n\n- Security scan: Clean\n- Recommendations provided.",
                comments=[
                    {
                        "path": "file.py",
                        "line": 1,
                        "body": "Consider parameterized queries here to prevent injection.",
                    }
                ],
            )

        # Mock mode is a deterministic no-op for the LLM layer.
        # Real findings come from the deterministic rule engine and
        # the static tool adapters (Bandit, Semgrep, Ruff, ESLint).
        return RawLLMResponse(findings=[])


class RulesOnlyProvider(ModelProvider):
    """
    Deterministic rules-only provider for environments without active LLM keys.
    Operates strictly via deterministic AST static analyzers and rule engines.
    Does not execute LLM inference or synthesize artificial findings.
    """

    @property
    def provider_name(self) -> str:
        return "rules_only"

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
    ) -> Any:
        """
        Return an empty structured response conforming to the requested schema
        without running or mocking LLM inference.
        """
        if schema.__name__ == "PatchDraft":
            return schema(
                unified_diff="",
                rationale="Rules-only mode active; no automated LLM patch generated.",
                assumptions="",
                tests_to_run=[],
            )

        if schema.__name__ == "PRReviewDraftOutput":
            return schema(
                summary_markdown="### Vigil Rules-Only Review\n\nDeterministic rule-based scan completed without LLM synthesis.",
                comments=[],
            )

        return RawLLMResponse(findings=[])


class GroqProvider(ModelProvider):
    """
    Live Groq LLM provider utilizing OpenAI-compatible API specifications.
    Default model: llama-3.3-70b-versatile (128K context, ultra-fast).
    """

    def __init__(
        self,
        model_name: str = "llama-3.3-70b-versatile",
        api_key: str = "",
    ) -> None:
        self._model_name = model_name
        self._api_key = api_key
        if api_key:
            try:
                from groq import AsyncGroq
                self._client = AsyncGroq(api_key=api_key)
            except ImportError:
                logger.error("groq package not installed; GroqProvider client cannot be initialized")
                self._client = None
        else:
            self._client = None

    @property
    def provider_name(self) -> str:
        return f"groq/{self._model_name}"

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
    ) -> Any:
        """
        Execute structured LLM invocation with strict JSON output parsing.
        """
        if self._client is None:
            raise RuntimeError("Groq API key not configured")

        # Use JSON mode: instruct model to respond ONLY with valid JSON conforming to schema
        response = await self._client.chat.completions.create(
            model=self._model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a security code review assistant. "
                        "Respond ONLY with valid JSON matching the "
                        "requested schema. No prose. No markdown fences."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )

        import json
        content = response.choices[0].message.content or "{}"
        logger.debug("Groq raw response: %s", content)
        data = json.loads(content)
        logger.debug("Groq parsed response: %s", data)
        return schema(**data)


class OpenAIProvider(ModelProvider):
    """Live OpenAI provider via LangChain. Requires OPENAI_API_KEY."""

    def __init__(self, model_name: str = "gpt-4o-mini", api_key: str = "") -> None:
        self._model_name = model_name
        self._api_key = api_key

    @property
    def provider_name(self) -> str:
        return f"openai/{self._model_name}"

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
    ) -> Any:
        try:
            from langchain_openai import ChatOpenAI  # type: ignore
            from langchain_core.messages import HumanMessage  # type: ignore
            import json

            llm = ChatOpenAI(
                model=self._model_name,
                openai_api_key=self._api_key,
                temperature=0,
            )
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content

            # Extract JSON from response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start == -1:
                return schema()

            data = json.loads(content[start:end])
            return schema(**data)
        except Exception as e:
            logger.error("OpenAI provider error: %s", e, exc_info=True)
            return schema()


def get_provider(provider_name: Optional[str] = None, **kwargs) -> ModelProvider:
    """Factory: return the configured ModelProvider with strict validation."""
    try:
        settings = get_settings()
    except Exception as exc:
        raise ConfigurationError(f"Failed to load settings: {exc}") from exc

    if provider_name is None:
        provider_name = settings.llm_provider

    if provider_name == "rules_only":
        return RulesOnlyProvider()

    if provider_name == "mock":
        if settings.environment == "production":
            raise ConfigurationError("MockProvider is forbidden in production")
        return MockProvider()

    if provider_name == "groq":
        api_key = kwargs.get("api_key") or settings.groq_api_key
        if not api_key:
            raise ConfigurationError("Groq API key is required for provider 'groq'")
        return GroqProvider(
            api_key=api_key,
            model_name=kwargs.get("model_name") or settings.llm_model_name,
        )

    if provider_name == "openai":
        api_key = kwargs.get("api_key") or settings.openai_api_key
        if not api_key:
            raise ConfigurationError("OpenAI API key is required for provider 'openai'")
        return OpenAIProvider(
            api_key=api_key,
            model_name=kwargs.get("model_name") or settings.llm_model_name,
        )

    raise ConfigurationError(f"Unknown LLM provider: {provider_name!r}")

