# Deployment guide

Deploy the Investigation Prompt Generator from [kailash105/Prompt-generator-for-production](https://github.com/kailash105/Prompt-generator-for-production).

This is a Python/Streamlit server application. It needs a running Python process, outbound access to your selected LLM API, and a host that supports WebSockets. A static host such as GitHub Pages cannot run it.

## Choose a deployment path

| Option | Use it when | Preparation |
| --- | --- | --- |
| Render web service | You want an explicit build/start command and environment settings | Follow section 2; no application code changes required |
| Streamlit Community Cloud | You want deployment directly from GitHub through Streamlit | Follow section 3, including the server-address change |

This guide documents deployment; no hosted service has been provisioned by adding this file. Hosting charges and provider API usage are separate. Check the host's current plan before creating a service.

## 1. Before deployment

### Repository and runtime

- Repository: `kailash105/Prompt-generator-for-production`
- Branch: `main`
- Entry point: `app.py`
- Working directory: repository root
- Runtime: Python 3.12; local verification used 3.12.12
- Dependency installation: `python -m pip install -r requirements.txt`
- No database, migrations, or persistent disk are required for V1.

The source and these files must be committed: `app.py`, `core/`, `models/`, `prompts/`, `utils/`, `requirements.txt`, and `.streamlit/config.toml`. Keep `.env`, `.venv/`, and `.streamlit/secrets.toml` out of Git; the repository already ignores them.

### Select an API-key arrangement

- **Public demo:** leave hosted API keys unset. Visitors select a provider and enter their own key in the sidebar.
- **Shared team key:** configure a key in the host's secret settings. Every visitor who can access the app can generate requests using that key, so restrict the app's audience through your hosting/access layer.

The current app has no built-in login or per-user API usage limits. A masked key field does not restrict who can use a configured server key.

### Provider configuration

Configure one provider to start. This Gemini model completed a live three-stage check during development; availability still depends on the provider at deployment time:

```dotenv
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_OUTPUT_MODE=json_schema
GEMINI_API_KEY=replace-with-your-key
```

Enter real keys only in the hosting dashboard. Omit `GEMINI_API_KEY` for a demo where visitors bring their own keys. `.env.example` is a reference file; the app does not automatically load it.

| `LLM_PROVIDER` | Key setting | Model setting | Additional settings |
| --- | --- | --- | --- |
| `openai` | `OPENAI_API_KEY` | `OPENAI_MODEL` | Uses the built-in OpenAI endpoint |
| `gemini` | `GEMINI_API_KEY` | `GEMINI_MODEL` | Optional `GEMINI_OUTPUT_MODE` |
| `groq` | `GROQ_API_KEY` | `GROQ_MODEL` | Optional `GROQ_OUTPUT_MODE` |
| `openrouter` | `OPENROUTER_API_KEY` | `OPENROUTER_MODEL` | Exact model ID required |
| `ollama` | Optional `OLLAMA_API_KEY` | `OLLAMA_MODEL` | `OLLAMA_BASE_URL` |
| `custom` | `CUSTOM_API_KEY` if required | `CUSTOM_MODEL` | `CUSTOM_BASE_URL` required |

Compatible providers accept `json_schema`, `json_object`, or `prompted_json` through their `<PREFIX>_OUTPUT_MODE` setting. All three modes still validate model responses with Pydantic. See [.env.example](.env.example) and [README.md](README.md) for the complete configuration.

## 2. Deploy on Render

### Create the service

1. Sign in to the [Render dashboard](https://dashboard.render.com/).
2. Choose **New → Web Service**.
3. Connect your GitHub account and select `kailash105/Prompt-generator-for-production`.
4. Use these settings:

| Field | Value |
| --- | --- |
| Branch | `main` |
| Language/runtime | Python |
| Root directory | Leave blank; use repository root |
| Build command | `python -m pip install -r requirements.txt` |
| Health check path | `/_stcore/health` |

Use this **Start Command**:

```bash
python -m streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT --server.headless=true
```

Render supplies `PORT`; enter the command exactly as shown. The address flag overrides this repository's local `127.0.0.1` binding. [Render web services](https://render.com/docs/web-services) require an externally reachable bind address; [Streamlit command-line flags](https://docs.streamlit.io/develop/concepts/configuration/options) take precedence over the config file.

### Add environment variables

In the service's environment settings, add:

```dotenv
PYTHON_VERSION=3.12.12
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_OUTPUT_MODE=json_schema
```

For a shared team key, also add `GEMINI_API_KEY` with its real value as a secret. Render's `PYTHON_VERSION` setting needs a full version number. [Python version configuration](https://render.com/docs/python-version).

Choose a compute plan and create the service. Inspect the build/start logs, then open the service URL after deployment succeeds. Set `/_stcore/health` in the service's HTTP health-check configuration. [Render health checks](https://render.com/docs/health-checks).

## 3. Deploy on Streamlit Community Cloud

### Prepare the server address

This repository currently contains the following local setting in [.streamlit/config.toml](.streamlit/config.toml):

```toml
[server]
address = "127.0.0.1"
```

For this deployment path, change that existing section to:

```toml
[server]
address = "0.0.0.0"
headless = true
```

Keep the existing theme and browser settings; do not add a second `[server]` section. Commit and push this configuration change before deployment:

```bash
git add .streamlit/config.toml
git commit -m "Configure Streamlit server for cloud deployment"
git push origin main
```

After this change, you can still bind only to localhost during local development:

```bash
python -m streamlit run app.py --server.address=127.0.0.1
```

### Create the app

1. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) and connect GitHub.
2. Choose **Create app** and select the repository.
3. Set branch to `main` and main file path to `app.py`.
4. In **Advanced settings**, select Python 3.12 and configure secrets.
5. Deploy and open the generated app URL. [Community Cloud deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

### Add secrets in TOML format

Paste this into the host's **Secrets** field, replacing the key for a shared-key deployment:

```toml
LLM_PROVIDER = "gemini"
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_OUTPUT_MODE = "json_schema"
GEMINI_API_KEY = "replace-with-your-key"
```

Keep these values at the top level, without a `[gemini]` or `[secrets]` table. Root-level secrets are exposed as environment variables, which this app reads. Do not paste `.env` syntax into the TOML field, and do not upload your local `.env`. [Community Cloud secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

For visitor-provided keys, omit the `GEMINI_API_KEY` line. For shared keys, configure the intended audience using the app's available sharing controls. [Community Cloud app settings](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/app-settings).

## 4. Verify the deployed app

1. Open its public HTTPS URL and confirm that the form and sidebar load.
2. Confirm the intended provider and model in Settings.
3. Supply a key if the deployment does not have one configured.
4. Click **Load example issue**, then **Generate investigation**. This sends a synthetic example through three API stages and uses provider quota.
5. Confirm that evidence analysis, investigation plan, and final prompt appear.
6. Test the copy icon and Markdown download.

Check the server endpoint, replacing the placeholder URL:

```bash
curl --fail --show-error https://YOUR-APP-HOST/_stcore/health
```

Expected result: HTTP 200 with `ok`. This confirms server health, not API-key validity or model availability; the example-generation check verifies those separately. If an access layer protects the endpoint, configure the host's health probe accordingly.

## 5. Updates and rollback

Before publishing application changes, run from an activated local virtual environment:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
ruff check .
ruff format --check .
```

Commit the intended files and push to `main`. On Render, use a linked GitHub repository with automatic deploys enabled, or deploy the latest commit manually. On Community Cloud, check the app's deployment status after pushing. Repeat the checks in section 4 after each release.

For provider changes, edit the **host's** environment/secrets settings and restart or redeploy. Editing your laptop's `.env` does not update a hosted app. A browser session may retain its selected model; edit **Settings → Model** or start a new session.

To roll back a single faulty commit without rewriting Git history, replace `COMMIT_SHA` below with that commit:

```bash
git revert COMMIT_SHA
git push origin main
```

Redeploy the reverted branch and verify again. Provider-secret changes must be reverted separately in the host's dashboard. The dependency ranges in `requirements.txt` are not a complete lockfile, so rebuilding an older commit may install newer compatible dependencies.

## 6. Troubleshooting

| Symptom | What to check |
| --- | --- |
| Host reports no open port or the page is unreachable | Bind to `0.0.0.0`; on Render, use `$PORT` in the start command. Follow the Community Cloud config preparation when using that route. |
| `ModuleNotFoundError` during startup | Build from repository root with `python -m pip install -r requirements.txt`. |
| Missing API key | Set the chosen provider's exact key variable, or enter a sidebar key. On Community Cloud, use top-level TOML values. |
| Wrong model remains selected | Check host settings, restart the service, and update the current browser session's Model field. |
| HTTP 503 / 500 / 502 / 504 | The app retries the failed stage three times. If it still fails, choose another accessible model or retry later. |
| HTTP 404 | Verify the exact model ID and endpoint. A listed model may still be unavailable for generation. |
| HTTP 401 / 403 | Check key validity, provider project permissions, and model access. |
| HTTP 429 | Check provider quota/billing and rate limits. |
| Output-format rejection | Try JSON only or Prompted JSON for a compatible model that does not accept JSON schemas. |
| Page loads but repeatedly disconnects | Check host/proxy WebSocket support, idle timeouts, and instance restarts. |
| Ollama connection fails after deployment | `localhost` refers to the hosted server, not your laptop. Configure a reachable Ollama endpoint or use a hosted provider. |

## 7. Runtime limits to account for

- Start with one server instance. Results and sidebar values live in server session memory; restarts and lost sessions can discard them. V1 has no durable investigation history.
- Each generation uses three sequential API stages. Temporary server errors can cause additional attempts and several minutes of waiting. Health probes should check server readiness without triggering generation.
- The app sends supplied evidence to the selected endpoint. Use the intended provider when processing project code and logs.
- Custom and Ollama URLs are user-editable and are contacted by the deployment server. For an untrusted public audience, restrict outbound access to internal network destinations or remove these options before hosting on a private network.
- A hosted app cannot reach your laptop's Ollama through `localhost`. Hosting a model requires its own service and suitable compute; it is not installed by this app's `requirements.txt`.

For usage and architecture, see [README.md](README.md).
