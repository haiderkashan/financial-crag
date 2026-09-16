import os
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq

from backend.app.core.config import settings


def get_llm(
    temperature: float = 0.0,
    model: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
) -> BaseChatModel:
    """Factory function to initialize and return a configured BaseChatModel.

    Defaults to the provider and model defined in application settings
    (default: Groq with qwen/qwen3.8-27b).

    Args:
        temperature: Sampling temperature for deterministic generation (default: 0.0).
        model: Optional model name override.
        provider: Optional provider name override ("groq", "openai").
        api_key: Optional API key override.
        max_tokens: Optional token generation limit (default: settings.LLM_MAX_TOKENS).

    Returns:
        BaseChatModel: Configured LangChain chat model.

    Raises:
        ValueError: If provider is unsupported or required API key is missing.
    """
    effective_provider = (provider or settings.LLM_PROVIDER).lower()
    effective_model = model or settings.LLM_MODEL_NAME
    effective_max_tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS

    if effective_provider == "groq":
        effective_key = api_key or settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "")
        if not effective_key:
            raise ValueError(
                "GROQ_API_KEY is not configured in settings or environment. "
                "Please set GROQ_API_KEY in backend/.env"
            )
        return ChatGroq(
            model_name=effective_model,
            groq_api_key=effective_key,
            temperature=temperature,
            max_tokens=effective_max_tokens,
        )

    elif effective_provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            raise ImportError(
                "langchain-openai is required for OpenAI provider. "
                "Install with `pip install langchain-openai`"
            ) from e

        effective_key = api_key or settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY", "")
        if not effective_key:
            raise ValueError(
                "OPENAI_API_KEY is not configured in settings or environment. "
                "Please set OPENAI_API_KEY in backend/.env"
            )
        return ChatOpenAI(
            model=effective_model,
            api_key=effective_key,
            temperature=temperature,
            max_tokens=effective_max_tokens,
        )

    else:
        raise ValueError(
            f"Unsupported LLM provider: '{effective_provider}'. Supported: 'groq', 'openai'"
        )
