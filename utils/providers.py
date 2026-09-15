"""Provider defaults and environment names, independent of UI and API transport."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    label: str
    env_prefix: str
    base_url: str
    model: str = ""
    requires_key: bool = True
    editable_url: bool = False

    def setting(self, suffix: str, default: str = "") -> str:
        return os.getenv(f"{self.env_prefix}_{suffix}", "").strip() or default


PROVIDERS = {
    "openai": Provider("OpenAI", "OPENAI", "https://api.openai.com/v1", "gpt-4.1-mini"),
    "gemini": Provider(
        "Google Gemini",
        "GEMINI",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        "gemini-3.8-flash",
    ),
    "groq": Provider("Groq", "GROQ", "https://api.groq.com/openai/v1", "openai/gpt-oss-20b"),
    "openrouter": Provider("OpenRouter", "OPENROUTER", "https://openrouter.ai/api/v1"),
    "ollama": Provider(
        "Ollama (local)",
        "OLLAMA",
        "http://localhost:11434/v1",
        requires_key=False,
        editable_url=True,
    ),
    "custom": Provider(
        "Custom OpenAI-compatible API",
        "CUSTOM",
        "",
        requires_key=False,
        editable_url=True,
    ),
}

OUTPUT_MODES = {
    "json_schema": "JSON schema (recommended)",
    "json_object": "JSON only",
    "prompted_json": "Prompted JSON (basic compatibility)",
}


def default_provider() -> str:
    selected = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    return selected if selected in PROVIDERS else "openai"
