from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from utils.llm import LLMError

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture(autouse=True)
def isolate_app_config(monkeypatch):
    # A developer's real .env must never turn UI tests into paid API calls.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    for prefix in ("OPENAI", "GEMINI", "GROQ", "OPENROUTER", "OLLAMA", "CUSTOM"):
        for setting in ("API_KEY", "MODEL", "BASE_URL", "OUTPUT_MODE"):
            monkeypatch.delenv(f"{prefix}_{setting}", raising=False)


def submit(app):
    return (
        next(button for button in app.button if button.label == "Generate investigation")
        .click()
        .run()
    )


def example(app):
    return (
        next(button for button in app.button if button.label == "Load example issue").click().run()
    )


def test_empty_submission_shows_validation():
    app = AppTest.from_file(APP).run()
    submit(app)
    assert not app.exception
    assert any("Issue is required" in item.value for item in app.error)


def test_example_and_missing_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    app = example(AppTest.from_file(APP).run())
    assert "SIP" in app.text_area(key="issue").value
    submit(app)
    assert not app.exception
    assert any("Add an OpenAI API key" in error.value for error in app.error)


def test_success_persists_and_new_failure_clears_output(monkeypatch, fake_llm):
    fake_llm.close = Mock()
    monkeypatch.setattr("utils.llm.OpenAILLM", lambda **kwargs: fake_llm)
    app = example(AppTest.from_file(APP).run())
    submit(app)
    assert not app.exception
    assert len(fake_llm.calls) == 3
    assert len(app.code) == 1
    assert "Route buttons disappear" in app.code[0].value
    assert len(app.get("download_button")) == 1
    app.run()
    assert len(app.code) == 1
    assert len(fake_llm.calls) == 3  # Reruns and downloads must not trigger more API calls.
    fake_llm.outputs = [LLMError("Test failure")]
    submit(app)
    assert not app.exception
    assert any("Evidence analysis failed" in error.value for error in app.error)
    assert len(app.code) == 0
    assert fake_llm.close.call_count == 2


def test_switch_to_gemini_uses_only_gemini_settings(monkeypatch, fake_llm):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    fake_llm.close = Mock()
    factory = Mock(return_value=fake_llm)
    monkeypatch.setattr("utils.llm.create_llm", factory)
    app = example(AppTest.from_file(APP).run())
    app.text_input(key="openai_api_key").set_value("typed-openai-key").run()
    app.selectbox(key="provider").select("gemini").run()
    assert app.text_input(key="gemini_api_key").value == ""
    assert app.text_input(key="gemini_model").value == "gemini-test-model"
    submit(app)
    assert not app.exception
    assert factory.call_args.kwargs["provider_id"] == "gemini"
    assert factory.call_args.kwargs["api_key"] == "gemini-test-key"
    assert factory.call_args.kwargs["model"] == "gemini-test-model"
    assert "Google Gemini" == app.session_state.result_provider
    assert len(fake_llm.calls) == 3


def test_custom_endpoint_and_format_reach_factory(monkeypatch, fake_llm):
    fake_llm.close = Mock()
    factory = Mock(return_value=fake_llm)
    monkeypatch.setattr("utils.llm.create_llm", factory)
    app = example(AppTest.from_file(APP).run())
    app.selectbox(key="provider").select("custom").run()
    app.text_input(key="custom_base_url").set_value("http://localhost:1234/v1")
    app.text_input(key="custom_model").set_value("local-model")
    app.selectbox(key="custom_output_mode").select("prompted_json").run()
    submit(app)
    assert not app.exception
    assert factory.call_args.kwargs["base_url"] == "http://localhost:1234/v1"
    assert factory.call_args.kwargs["output_mode"] == "prompted_json"


def test_provider_environment_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    app = AppTest.from_file(APP).run()
    assert not app.exception
    assert app.selectbox(key="provider").value == "gemini"
