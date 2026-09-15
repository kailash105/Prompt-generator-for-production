# Investigation Prompt Generator

A one-page Streamlit MVP that turns a developer's issue and evidence into an investigation prompt for Cursor, Windsurf, Claude Code, or Copilot.

**Intake → evidence analysis → investigation plan → AI IDE prompt**

## Run locally

Python 3.12 recommended.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Open http://localhost:8501. In **Settings**, select a provider, enter its API key, and choose a model available to your account. You can also configure defaults in `.env`. Existing `OPENAI_API_KEY` and `OPENAI_MODEL` settings continue to work.

## Providers

| Provider | API key variable | Model variable | Endpoint setup |
| --- | --- | --- | --- |
| OpenAI | `OPENAI_API_KEY` | `OPENAI_MODEL` | Built in |
| Google Gemini | `GEMINI_API_KEY` | `GEMINI_MODEL` | Built in |
| Groq | `GROQ_API_KEY` | `GROQ_MODEL` | Built in |
| OpenRouter | `OPENROUTER_API_KEY` | `OPENROUTER_MODEL` | Built in; enter an exact model ID |
| Ollama (local) | Optional `OLLAMA_API_KEY` | `OLLAMA_MODEL` | Defaults to `http://localhost:11434/v1`; enter an installed model name |
| Custom OpenAI-compatible API | `CUSTOM_API_KEY` if required | `CUSTOM_MODEL` | Set `CUSTOM_BASE_URL` or enter it in Settings |

### Use Gemini

Choose **Google Gemini** in Settings and paste your Gemini key. You can obtain a key through [Google AI Studio](https://aistudio.google.com/apikey). To make Gemini the default, set:

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.8-flash
```

Restart Streamlit after changing `.env`. Model IDs are editable because account access and provider offerings vary.

### Use open models

Choose **Groq** or **OpenRouter**, supply that provider's key, and use a supported model ID. The Groq preset uses `openai/gpt-oss-20b`. OpenRouter leaves the model blank so you can choose one from its catalog.

For local models, run an Ollama server with a model already installed, select **Ollama (local)**, and enter its exact model name. A local Ollama server does not require an API key; the SDK receives a placeholder that Ollama ignores. See [Ollama's compatibility documentation](https://docs.ollama.com/api/openai-compatibility).

For another service or local server, select **Custom OpenAI-compatible API** and enter its API root (for example `http://localhost:1234/v1`), model ID, and key if required. The service must implement OpenAI-compatible `/chat/completions`; arbitrary provider-specific APIs are not supported by this adapter.

Keys belong to individual providers and are never reused across provider selections. A hosted open model can still require an account, quota, or payment; the app does not supply API keys or credits.

### Output compatibility

Compatible providers offer three output formats:

- **JSON schema:** requests a response matching the Pydantic model's schema.
- **JSON only:** requests a JSON object and includes the schema in the instructions.
- **Prompted JSON:** includes the schema in the instructions without sending `response_format`, for basic compatible servers.

All modes validate the response with Pydantic before passing it to the next stage. If the provider rejects JSON schema, explicitly select another format and retry. There is no automatic provider or format fallback. Unsupported models, incomplete answers, and invalid JSON surface as stage errors.

Set `LLM_PROVIDER` to `openai`, `gemini`, `groq`, `openrouter`, `ollama`, or `custom`. Non-OpenAI providers also accept `<PREFIX>_OUTPUT_MODE=json_schema`, `json_object`, or `prompted_json`. Ollama and Custom allow `<PREFIX>_BASE_URL`; hosted presets use their fixed endpoints. See [.env.example](.env.example).

### Troubleshoot provider errors

- **HTTP 503 / 5xx:** the provider is temporarily unavailable or overloaded. Retry shortly or choose another model. Changing JSON format does not fix a server availability error.
- **HTTP 404:** check the model ID and endpoint. A catalog entry alone does not guarantee that generation is available for that model.
- **HTTP 403:** check key permissions, project restrictions, and model access.
- **HTTP 400:** check the request settings and the model's output-format support.
- **HTTP 429:** check quota/billing or wait for the rate limit to reset.

The app reports the failed stage and status category without exposing provider response bodies or keys. After editing a model in `.env`, restart Streamlit; to change the active session immediately, edit **Settings → Model**.

## Generate an investigation

Click **Load example issue** to populate the SIP redraw example, replace it with your own bug, then choose **Generate investigation**. Issue, expected behavior, and actual behavior are required. Evidence is optional; missing evidence is explicitly treated as an unknown. Each text field accepts 20,000 characters, with a 60,000-character combined limit; oversized input is rejected rather than truncated.

Review the evidence analysis and investigation plan. Use the copy icon at the top right of the final prompt, or download it as Markdown. Results remain available across UI reruns; edits take effect on the next submission. A failed new submission clears the previous result to avoid stale output.

## What V1 includes

- Separate inputs for notes, logs, stack traces, code, and git diffs.
- Three sequential LLM calls, each parsed and validated with Pydantic.
- Provider selection for Gemini, Groq, OpenRouter, Ollama, OpenAI, and compatible APIs.
- Facts with requested source labels, assumptions, unknowns, and search signals.
- Competing hypotheses with supporting/rejecting evidence checks.
- Quick, Standard, and Deep depth instructions applied to every stage.
- Original intake and evidence preserved verbatim in the final prompt.
- Investigation-first instructions and all 12 requested report sections.
- Stage progress and actionable errors for credentials, limits, connectivity, refusal, and invalid output.

The generator does not read a repository or verify a root cause. The downstream coding agent must do that. Structured validation checks the output shape; it does not prove that model claims are correct. Screenshot/file uploads, history, and repository integrations are outside V1.

## Architecture

```text
app.py                      Streamlit intake and result display
models/investigation.py     Pydantic input, analysis, plan, and draft contracts
core/analyzer.py            LLM stage 1: evidence analysis
core/planner.py             LLM stage 2: investigation planning
core/generator.py           LLM stage 3: instructions + final prompt rendering
core/pipeline.py            Sequential orchestration and stage progress
prompts/                   Stage-specific instructions and depth guidance
utils/llm.py               Responses/Chat Completions adapters and safe errors
utils/providers.py         Provider presets and separate environment settings
tests/                     Pipeline, API adapter, and Streamlit integration checks
```

The third model synthesizes actionable instructions from the intake, analysis, and plan. Python then wraps those instructions with the original input, full hypotheses, verification plan, and fixed report requirements. This prevents a summarization step from dropping supplied evidence or required sections. Code fences are sized to preserve embedded backticks.

## Data and API behavior

On generation, intake/evidence and intermediate results are sent to the selected provider's endpoint. The app does not write evidence, results, or API keys to disk; a key you manually put in `.env` is stored there. The sidebar key and generated results live in Streamlit's server-side session memory. No shared result cache or history is used. OpenAI Responses requests use `store=False`; compatible Chat Completions requests omit that provider-specific option. Each provider's retention policies apply. Requests use a 90-second timeout. HTTP 500/502/503/504 errors retry the current stage up to three times, waiting approximately 2, 4, and 8 seconds with a little random jitter. Progress reports each retry. SDK retries are disabled to avoid multiplying attempts. Authentication, permission, model-not-found, quota, connection, and validation errors stop immediately. Completed stages are not repeated during an automatic retry. Manually submitting a failed investigation again starts all three stages and can incur additional API usage.

The default server binds to localhost. This MVP has no authentication layer for public hosting.

API implementation references: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [GPT-4.1 mini capabilities](https://developers.openai.com/api/docs/models/gpt-4.1-mini). UI tests use [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).

Compatible adapter references: [Gemini](https://ai.google.dev/gemini-api/docs/openai), [Groq structured outputs](https://console.groq.com/docs/structured-outputs), [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs).

## Verify

```bash
pip install -r requirements-dev.txt
python -m pytest -q
ruff check .
ruff format --check .
```

Tests stub model responses and make no paid API calls. Compatible-provider tests exercise the real SDK using a mocked HTTP transport through all three stages. Checks cover routing, credentials, output formats, stage ordering, context propagation, evidence preservation, depth, input limits, failure handling, response validation, and the actual Streamlit submission/provider-switching flow. Live provider access and model quality still require credentials and evaluation with real bugs.

## Validate prompt quality

Use [docs/evaluation.md](docs/evaluation.md) to compare this workflow with a direct investigation request on 10 previously solved bugs. Keep each known fix hidden from both agents during investigation.
