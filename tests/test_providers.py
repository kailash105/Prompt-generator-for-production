"""Exercise the real SDK against a fake HTTP transport; no remote calls."""

import json

import httpx
import pytest
from openai import OpenAI

from core.pipeline import generate_investigation_prompt
from models.investigation import EvidenceAnalysis
from utils.llm import LLMError, create_llm
from utils.providers import PROVIDERS


def install_transport(monkeypatch, handler):
    def client(**kwargs):
        return OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    monkeypatch.setattr("utils.llm.OpenAI", client)


def completion(content, finish_reason="stop", refusal=None):
    return {
        "id": "test-completion",
        "object": "chat.completion",
        "created": 0,
        "model": "test",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content, "refusal": refusal},
            }
        ],
    }


@pytest.mark.parametrize("provider_id", ["gemini", "groq", "openrouter", "ollama", "custom"])
def test_full_pipeline_through_compatible_sdk(monkeypatch, provider_id, intake, outputs):
    requests = []

    def handler(request):
        result = outputs[len(requests)]
        requests.append(request)
        return httpx.Response(200, json=completion(result.model_dump_json()))

    install_transport(monkeypatch, handler)
    provider = PROVIDERS[provider_id]
    client = create_llm(
        provider_id, "provider-test-key", "test-model", base_url="http://localhost:1234/v1"
    )
    try:
        result = generate_investigation_prompt(intake, client)
    finally:
        client.close()
    assert len(requests) == 3
    expected_url = "http://localhost:1234/v1" if provider.editable_url else provider.base_url
    for request in requests:
        assert str(request.url) == expected_url.rstrip("/") + "/chat/completions"
        assert request.headers["authorization"] == "Bearer provider-test-key"
        body = json.loads(request.content)
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["model"] == "test-model"
        assert "store" not in body
    assert intake.evidence.code in result.prompt
    assert "Hypotheses to validate" in result.prompt


@pytest.mark.parametrize(
    "mode, expected",
    [("json_schema", "json_schema"), ("json_object", "json_object"), ("prompted_json", None)],
)
def test_output_modes(monkeypatch, outputs, mode, expected):
    def handler(request):
        body = json.loads(request.content)
        assert body.get("response_format", {}).get("type") == expected
        assert "facts" in body["messages"][0]["content"]
        return httpx.Response(200, json=completion(outputs[0].model_dump_json()))

    install_transport(monkeypatch, handler)
    client = create_llm("ollama", "", "installed-model", output_mode=mode)
    try:
        assert client.generate("Analyze", {}, EvidenceAnalysis) == outputs[0]
    finally:
        client.close()


@pytest.mark.parametrize(
    "content, finish, refusal, message",
    [
        ('{"facts": []}', "stop", None, "failed validation"),
        ("not json", "stop", None, "failed validation"),
        ("{}", "length", None, "incomplete"),
        (None, "stop", "refused", "declined"),
        (None, "content_filter", None, "declined"),
        ("", "stop", None, "no structured result"),
    ],
)
def test_compatible_response_failures(monkeypatch, content, finish, refusal, message):
    install_transport(
        monkeypatch, lambda request: httpx.Response(200, json=completion(content, finish, refusal))
    )
    client = create_llm("gemini", "test-key", "test-model")
    try:
        with pytest.raises(LLMError, match=message):
            client.generate("Analyze", {}, EvidenceAnalysis)
    finally:
        client.close()


def test_provider_error_is_named_and_sanitized(monkeypatch):
    install_transport(
        monkeypatch,
        lambda request: httpx.Response(
            401, json={"error": {"message": "private-details", "type": "authentication_error"}}
        ),
    )
    client = create_llm("gemini", "bad-key", "test-model")
    try:
        with pytest.raises(LLMError, match="Google Gemini rejected the API key") as exc:
            client.generate("Analyze", {}, EvidenceAnalysis)
        assert "private-details" not in str(exc.value)
    finally:
        client.close()


def test_local_does_not_inherit_openai_credentials_or_endpoint(monkeypatch, outputs):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://unrelated.example/v1")

    def handler(request):
        assert request.url.host == "localhost"
        assert request.headers["authorization"] == "Bearer local-no-key"
        return httpx.Response(200, json=completion(outputs[0].model_dump_json()))

    install_transport(monkeypatch, handler)
    client = create_llm("ollama", "", "installed-model")
    try:
        client.generate("Analyze", {}, EvidenceAnalysis)
    finally:
        client.close()


@pytest.mark.parametrize(
    "url",
    [
        "",
        "example.com",
        "ftp://example.com",
        "https://user:secret@example.com",
        "https://example.com?key=secret",
        "http://localhost:bad/v1",
    ],
)
def test_invalid_custom_urls_rejected(url):
    with pytest.raises(LLMError, match="base URL"):
        create_llm("custom", "", "model", base_url=url)


@pytest.mark.parametrize("provider_id", ["gemini", "groq", "openrouter"])
def test_hosted_providers_require_own_key(provider_id, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    with pytest.raises(LLMError, match="API key"):
        create_llm(provider_id, "", "model")


@pytest.mark.parametrize(
    "status, message",
    [
        (503, "temporarily unavailable or overloaded"),
        (500, "temporarily unavailable or overloaded"),
        (502, "temporarily unavailable or overloaded"),
        (404, "could not find the model or endpoint"),
        (403, "denied access"),
    ],
)
def test_status_specific_errors(monkeypatch, status, message):
    calls = []

    def handler(request):
        calls.append(request)
        # Gemini returns a list envelope for some errors, including 503 overload.
        return httpx.Response(
            status,
            json=[
                {
                    "error": {
                        "code": status,
                        "message": "private-provider-details",
                        "status": "UNAVAILABLE",
                    }
                }
            ],
        )

    install_transport(monkeypatch, handler)
    client = create_llm("gemini", "test-key", "test-model")
    client.client = client.client.with_options(max_retries=0)
    client.retry_delays = ()
    try:
        with pytest.raises(LLMError, match=message) as exc:
            client.generate("Analyze", {}, EvidenceAnalysis)
        assert f"HTTP {status}" in str(exc.value)
        assert "private-provider-details" not in str(exc.value)
        if status >= 500:
            assert "try JSON only" not in str(exc.value)
        assert len(calls) == 1
    finally:
        client.close()


def test_overload_retries_only_failed_stage(monkeypatch, intake, outputs):
    requests = []
    waits = []
    notifications = []
    by_name = {type(output).__name__: output for output in outputs}

    def handler(request):
        body = json.loads(request.content)
        name = body["response_format"]["json_schema"]["name"]
        requests.append(name)
        if name == "InvestigationPlan" and requests.count(name) == 1:
            return httpx.Response(503, json={"error": {"message": "overloaded"}})
        return httpx.Response(200, json=completion(by_name[name].model_dump_json()))

    install_transport(monkeypatch, handler)
    monkeypatch.setattr("utils.llm.time.sleep", waits.append)
    monkeypatch.setattr("utils.llm.random.uniform", lambda *args: 0)
    client = create_llm("gemini", "test-key", "test-model")
    client.on_retry = notifications.append
    try:
        result = generate_investigation_prompt(intake, client)
        assert result.prompt
        assert requests == [
            "EvidenceAnalysis",
            "InvestigationPlan",
            "InvestigationPlan",
            "PromptDraft",
        ]
        assert waits == [2.0]
        assert "Retrying this stage" in notifications[0]
        assert "test-key" not in notifications[0]
    finally:
        client.close()


def test_persistent_overload_stops_after_three_retries(monkeypatch):
    calls = []
    waits = []

    def handler(request):
        calls.append(request)
        return httpx.Response(503, json={"error": {"message": "overloaded"}})

    install_transport(monkeypatch, handler)
    monkeypatch.setattr("utils.llm.time.sleep", waits.append)
    monkeypatch.setattr("utils.llm.random.uniform", lambda *args: 0)
    client = create_llm("gemini", "test-key", "test-model")
    try:
        with pytest.raises(LLMError, match="after automatic retries"):
            client.generate("Analyze", {}, EvidenceAnalysis)
        assert len(calls) == 4
        assert waits == [2.0, 4.0, 8.0]
    finally:
        client.close()


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429])
def test_client_errors_are_not_retried(monkeypatch, status):
    calls = []
    waits = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": "request error"}})

    install_transport(monkeypatch, handler)
    monkeypatch.setattr("utils.llm.time.sleep", waits.append)
    client = create_llm("gemini", "test-key", "test-model")
    try:
        with pytest.raises(LLMError):
            client.generate("Analyze", {}, EvidenceAnalysis)
        assert len(calls) == 1
        assert waits == []
    finally:
        client.close()
