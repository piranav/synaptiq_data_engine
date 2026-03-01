"""
Multi-LLM model configuration.

Maps user-friendly model identifiers to provider-specific model names
and handles Agent construction for both OpenAI and Anthropic models.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ModelInfo:
    id: str
    display_name: str
    provider: str  # "openai" | "anthropic"
    model_name: str  # actual name sent to the provider
    is_reasoning: bool = False


AVAILABLE_MODELS: list[ModelInfo] = [
    ModelInfo(
        id="gpt-4.1",
        display_name="GPT-4.1",
        provider="openai",
        model_name="gpt-4.1",
    ),
    ModelInfo(
        id="gpt-5.2",
        display_name="GPT-5.2",
        provider="openai",
        model_name="gpt-5.2",
    ),
    ModelInfo(
        id="gpt-5.2-thinking",
        display_name="GPT-5.2 Thinking",
        provider="openai",
        model_name="gpt-5.2-thinking",
        is_reasoning=True,
    ),
    ModelInfo(
        id="claude-4.6-sonnet",
        display_name="Claude 4.6 Sonnet",
        provider="anthropic",
        model_name="anthropic/claude-sonnet-4-6-20260301",
    ),
    ModelInfo(
        id="claude-4.6-opus",
        display_name="Claude 4.6 Opus",
        provider="anthropic",
        model_name="anthropic/claude-opus-4-6-20260301",
    ),
    ModelInfo(
        id="claude-4.5-haiku",
        display_name="Claude 4.5 Haiku",
        provider="anthropic",
        model_name="anthropic/claude-haiku-4-5-20260301",
    ),
]

MODEL_MAP: dict[str, ModelInfo] = {m.id: m for m in AVAILABLE_MODELS}

DEFAULT_MODEL_ID = "gpt-5.2"


def get_model_info(model_id: str) -> ModelInfo:
    """Look up a ModelInfo by its short identifier, falling back to default."""
    return MODEL_MAP.get(model_id, MODEL_MAP[DEFAULT_MODEL_ID])


def resolve_model_for_agent(
    model_id: str,
    anthropic_api_key: Optional[str] = None,
):
    """
    Return an object suitable for the ``model`` parameter of ``Agent()``.

    - For OpenAI models: returns the plain model-name string (SDK default).
    - For Anthropic models: returns a ``LitellmModel`` instance backed by
      the user's Anthropic API key.
    """
    info = get_model_info(model_id)

    if info.provider == "openai":
        return info.model_name

    if info.provider == "anthropic":
        key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key

        try:
            from agents.extensions.models.litellm_model import LitellmModel

            return LitellmModel(model=info.model_name)
        except ImportError:
            logger.warning(
                "litellm not installed – falling back to default OpenAI model"
            )
            return MODEL_MAP[DEFAULT_MODEL_ID].model_name

    return info.model_name
