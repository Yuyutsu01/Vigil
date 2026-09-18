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
from typing import List, Type

from pydantic import BaseModel

from app.schemas.finding import RawLLMFinding, RawLLMResponse
from app.models.finding import EvidenceKind, Severity

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
    ) -> RawLLMResponse:
        """
        Return a deterministic response based on a hash of the prompt content.
        Used for AC-4 and AC-7 test reliability.
        """
        # Derive a deterministic seed from the prompt
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        seed_int = int(prompt_hash[:8], 16)

        # Produce zero findings for clean code, one advisory finding for any code
        # The presence of <<<SOURCE_START>>> marker confirms this is a real analysis call
        if "<<<SOURCE_START>>>" not in prompt:
            return RawLLMResponse(findings=[])

        # Extract a snippet of source code between delimiters for context
        try:
            start_idx = prompt.index("<<<SOURCE_START>>>") + len("<<<SOURCE_START>>>")
            end_idx = prompt.index("<<<SOURCE_END>>>")
            source_snippet = prompt[start_idx:end_idx].strip()[:100]
        except ValueError:
            source_snippet = ""

        # Deterministic: same source_snippet hash → same findings
        source_hash = hashlib.sha256(source_snippet.encode("utf-8")).hexdigest()

        # Return a minimal but valid finding to satisfy schema
        finding = RawLLMFinding(
            rule_id=f"LLM-SEC-{seed_int % 900 + 100:03d}",
            category="security",
            severity=Severity.info,
            confidence=0.50,
            title="Mock LLM analysis complete (no real findings in mock mode)",
            rationale=f"MockProvider produced deterministic output for source hash {source_hash[:8]}.",
            remediation="Switch to a live LLM provider for real security analysis.",
            evidence_kind=EvidenceKind.llm_reasoning,
        )
        return RawLLMResponse(findings=[finding])


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
    ) -> RawLLMResponse:
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
                return RawLLMResponse(findings=[])

            data = json.loads(content[start:end])
            return RawLLMResponse(**data)
        except Exception as e:
            logger.error("OpenAI provider error: %s", e)
            return RawLLMResponse(findings=[])


def get_provider(provider_name: str, **kwargs) -> ModelProvider:
    """Factory: return the configured ModelProvider."""
    if provider_name == "mock":
        return MockProvider()
    elif provider_name == "openai":
        return OpenAIProvider(
            model_name=kwargs.get("model_name", "gpt-4o-mini"),
            api_key=kwargs.get("api_key", ""),
        )
    else:
        logger.warning("Unknown provider '%s'; falling back to mock", provider_name)
        return MockProvider()
