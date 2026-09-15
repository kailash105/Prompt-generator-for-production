import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

from models.investigation import EvidenceAnalysis
from utils.llm import LLMError, OpenAILLM


@pytest.fixture
def gateway(monkeypatch):
    client = Mock()
    monkeypatch.setattr("utils.llm.OpenAI", Mock(return_value=client))
    return OpenAILLM("test-key", "test-model")


def test_gateway_requests_and_validates_structured_output(gateway, outputs):
    gateway.client.responses.parse.return_value = SimpleNamespace(
        status="completed", output=[], output_parsed=outputs[0]
    )
    result = gateway.generate("Analyze", {"evidence": {"logs": "trace"}}, EvidenceAnalysis)
    assert result == outputs[0]
    kwargs = gateway.client.responses.parse.call_args.kwargs
    assert kwargs["text_format"] is EvidenceAnalysis
    assert kwargs["store"] is False
    assert json.loads(kwargs["input"][1]["content"])["evidence"]["logs"] == "trace"
    gateway.close()
    gateway.client.close.assert_called_once()


@pytest.mark.parametrize(
    "status, parsed, output, message",
    [
        ("incomplete", None, [], "incomplete"),
        ("completed", None, [], "no structured result"),
        (
            "completed",
            None,
            [SimpleNamespace(content=[SimpleNamespace(type="refusal")])],
            "declined",
        ),
        ("completed", {"facts": [3]}, [], "failed validation"),
    ],
)
def test_invalid_and_refused_responses(gateway, status, parsed, output, message):
    gateway.client.responses.parse.return_value = SimpleNamespace(
        status=status, output=output, output_parsed=parsed
    )
    with pytest.raises(LLMError, match=message):
        gateway.generate("Analyze", {}, EvidenceAnalysis)


@pytest.mark.parametrize(
    "error_type, status, message",
    [
        (AuthenticationError, 401, "rejected the API key"),
        (RateLimitError, 429, "quota or rate limit"),
        (BadRequestError, 400, "rejected the request"),
    ],
)
def test_provider_errors_are_sanitized(gateway, error_type, status, message):
    response = httpx.Response(
        status, request=httpx.Request("POST", "https://api.openai.com/v1/responses")
    )
    gateway.client.responses.parse.side_effect = error_type(
        "secret-provider-details", response=response, body=None
    )
    with pytest.raises(LLMError, match=message) as exc:
        gateway.generate("Analyze", {}, EvidenceAnalysis)
    assert "secret-provider-details" not in str(exc.value)


@pytest.mark.parametrize(
    "error_type, message", [(APIConnectionError, "connect"), (APITimeoutError, "timed out")]
)
def test_connection_errors(gateway, error_type, message):
    gateway.client.responses.parse.side_effect = error_type(
        request=httpx.Request("POST", "https://api.openai.com")
    )
    with pytest.raises(LLMError, match=message):
        gateway.generate("Analyze", {}, EvidenceAnalysis)


def test_missing_key_rejected():
    with pytest.raises(LLMError, match="API key"):
        OpenAILLM(" ", "gpt-4.1-mini")
