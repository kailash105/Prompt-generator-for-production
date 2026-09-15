"""Small structured-output gateway; no evidence or credentials are logged."""

import json
import random
import time
from collections.abc import Callable
from typing import Any, Protocol, TypeVar
from urllib.parse import urlsplit

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from utils.providers import OUTPUT_MODES, PROVIDERS

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Safe, actionable message suitable for display."""


class StructuredLLM(Protocol):
    def generate(self, instructions: str, payload: dict[str, Any], schema: type[T]) -> T: ...


class LLMClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        provider: str,
        base_url: str,
        use_responses: bool = False,
        requires_key: bool = True,
        output_mode: str = "json_schema",
    ):
        if requires_key and not api_key.strip():
            raise LLMError(f"Add an {provider} API key in Settings or your .env file.")
        if not model.strip():
            raise LLMError("Enter a model ID available from your selected provider in Settings.")
        if output_mode not in OUTPUT_MODES:
            raise LLMError("Select a supported output format in Settings.")
        try:
            parsed = urlsplit(base_url.strip())
            valid_url = (
                parsed.scheme in {"https", "http"}
                and parsed.hostname
                and not parsed.username
                and not parsed.password
                and not parsed.query
                and not parsed.fragment
            )
            _ = parsed.port
        except ValueError:
            valid_url = False
        if not valid_url:
            raise LLMError(
                "Enter a valid HTTP(S) API base URL without credentials, query, or fragment."
            )
        self.provider = provider
        self.use_responses = use_responses
        self.output_mode = output_mode
        self.model = model.strip()
        self.retry_delays = (2.0, 4.0, 8.0)
        self.on_retry: Callable[[str], None] | None = None
        # Explicit URL and key prevent SDK environment defaults leaking across providers.
        self.client = OpenAI(
            api_key=api_key.strip() or "local-no-key",
            base_url=base_url.strip(),
            timeout=90.0,
            max_retries=0,
        )

    def close(self):
        self.client.close()

    def _request(self, operation: Callable[..., Any], **kwargs: Any) -> Any:
        """Retry this stage only, with bounded backoff and visible progress."""
        for attempt in range(len(self.retry_delays) + 1):
            try:
                return operation(**kwargs)
            except APIStatusError as exc:
                if exc.status_code not in {500, 502, 503, 504} or attempt == len(self.retry_delays):
                    raise
                delay = self.retry_delays[attempt] + random.uniform(0, 0.5)
                if self.on_retry:
                    self.on_retry(
                        f"{self.provider} / {self.model} is temporarily unavailable "
                        f"(HTTP {exc.status_code}). Retrying this stage in {delay:.0f}s "
                        f"({attempt + 1}/{len(self.retry_delays)})…"
                    )
                time.sleep(delay)

    def generate(self, instructions: str, payload: dict[str, Any], schema: type[T]) -> T:
        try:
            if not self.use_responses:
                return self._generate_chat(instructions, payload, schema)
            response = self._request(
                self.client.responses.parse,
                model=self.model,
                input=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                text_format=schema,
                max_output_tokens=6000,
                store=False,
            )
            if response.status != "completed":
                raise LLMError(
                    "The model returned an incomplete response. Shorten the evidence or try again."
                )
            if any(
                getattr(part, "type", None) == "refusal"
                for item in response.output
                for part in getattr(item, "content", [])
            ):
                raise LLMError(
                    "The model declined this request. Review the input before trying again."
                )
            if response.output_parsed is None:
                raise LLMError(
                    "The model returned no structured result. Try again or select another compatible model."
                )
            return schema.model_validate(response.output_parsed)
        except AuthenticationError:
            raise LLMError(
                f"{self.provider} rejected the API key. Check the key in Settings or .env."
            ) from None
        except RateLimitError:
            raise LLMError(
                f"{self.provider} quota or rate limit reached. Check billing/quota, or wait and retry."
            ) from None
        except APITimeoutError:
            raise LLMError(
                f"{self.provider} timed out. Try again with a shorter evidence excerpt."
            ) from None
        except APIConnectionError:
            raise LLMError(
                f"Could not connect to {self.provider}. Check the endpoint/server and connection, then retry."
            ) from None
        except APIStatusError as exc:
            status = exc.status_code
            if status >= 500:
                raise LLMError(
                    f"{self.provider} is temporarily unavailable or overloaded (HTTP {status}). "
                    "Still unavailable after automatic retries. Wait briefly and retry, "
                    "or select another model in Settings. "
                    "Changing the output format will not resolve this server error."
                ) from None
            if status == 404:
                raise LLMError(
                    f"{self.provider} could not find the model or endpoint (HTTP 404). "
                    "Check the exact model ID and API base URL in Settings."
                ) from None
            if status == 403:
                raise LLMError(
                    f"{self.provider} denied access (HTTP 403). Check the API key's permissions, "
                    "project restrictions, and access to the selected model."
                ) from None
            raise LLMError(
                f"{self.provider} rejected the request (HTTP {status}). Check the model ID, endpoint, and model access. "
                "For compatible APIs, try JSON only or Prompted JSON if JSON schema is unsupported."
            ) from None
        except (ValidationError, ValueError):
            raise LLMError(
                "The model output failed validation. Try again or choose another compatible model."
            ) from None
        except APIError:
            raise LLMError(f"{self.provider} could not complete the request. Try again.") from None

    def _generate_chat(self, instructions: str, payload: dict[str, Any], schema: type[T]) -> T:
        json_schema = schema.model_json_schema()
        instructions += (
            "\nReturn only a JSON object matching this schema. No Markdown fences or commentary.\n"
            + json.dumps(json_schema, ensure_ascii=False)
        )
        options: dict[str, Any] = {}
        if self.output_mode == "json_schema":
            options["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "strict": True, "schema": json_schema},
            }
        elif self.output_mode == "json_object":
            options["response_format"] = {"type": "json_object"}
        response = self._request(
            self.client.chat.completions.create,
            model=self.model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            max_tokens=6000,
            **options,
        )
        if not response.choices:
            raise LLMError("The model returned no choices. Try again or choose another model.")
        choice = response.choices[0]
        if getattr(choice.message, "refusal", None) or choice.finish_reason == "content_filter":
            raise LLMError("The model declined this request. Review the input before trying again.")
        if choice.finish_reason != "stop":
            raise LLMError(
                "The model returned an incomplete response. Shorten the evidence or try another model."
            )
        content = choice.message.content
        if not content or not content.strip():
            raise LLMError("The model returned no structured result. Try another model.")
        return schema.model_validate_json(content)


class OpenAILLM(LLMClient):
    """Retained for existing Python callers; the UI uses create_llm."""

    def __init__(self, api_key: str, model: str):
        super().__init__(
            api_key,
            model,
            provider="OpenAI",
            base_url=PROVIDERS["openai"].base_url,
            use_responses=True,
        )


def create_llm(
    provider_id: str,
    api_key: str,
    model: str,
    *,
    base_url: str | None = None,
    output_mode: str = "json_schema",
) -> LLMClient:
    if provider_id not in PROVIDERS:
        raise LLMError("Select a supported provider in Settings.")
    provider = PROVIDERS[provider_id]
    if provider_id == "openai":
        return OpenAILLM(api_key=api_key, model=model)
    return LLMClient(
        api_key,
        model,
        provider=provider.label,
        base_url=(provider.base_url if base_url is None else base_url)
        if provider.editable_url
        else provider.base_url,
        requires_key=provider.requires_key,
        output_mode=output_mode,
    )
