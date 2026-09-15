"""Run with: streamlit run app.py"""

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from pydantic import ValidationError

from core.pipeline import generate_investigation_prompt
from models.investigation import Evidence, InvestigationInput
from utils.llm import LLMError, create_llm
from utils.providers import OUTPUT_MODES, PROVIDERS, default_provider

load_dotenv(Path(__file__).parent / ".env")
st.set_page_config(page_title="Investigation Prompt Generator", page_icon="🔎", layout="centered")


def load_example():
    st.session_state.update(
        {
            "project": "pragathirail-UI",
            "technology": "Angular + TypeScript + Leaflet",
            "issue": "Route buttons disappear after SIP redraw.",
            "expected": "Existing route buttons remain available after redraw.",
            "actual": "The SIP redraw completes, but the route buttons are no longer visible.",
            "reproduction_steps": "1. Upload a SIP.\n2. Draw a route.\n3. Redraw the SIP.\n4. Observe that route buttons disappear.",
            "constraints": "Do not refactor unrelated functionality. Preserve existing route data.",
            "logs": "",
            "stack_trace": "",
            "code": "",
            "git_diff": "",
            "other": "Developer observation: route buttons are present in the source JSON and absent in the UI after redraw.\nSearch leads to verify: digitalize(), keepHandles, computed_data, extracted_elements.",
            "depth": "Standard",
        }
    )
    st.session_state.pop("result", None)
    st.session_state.pop("result_input", None)


with st.sidebar:
    st.header("Settings")
    provider_id = st.selectbox(
        "Provider",
        list(PROVIDERS),
        index=list(PROVIDERS).index(default_provider()),
        format_func=lambda value: PROVIDERS[value].label,
        key="provider",
    )
    provider = PROVIDERS[provider_id]
    api_key = st.text_input(
        f"{provider.label} API key" + (" (optional)" if not provider.requires_key else ""),
        type="password",
        key=f"{provider_id}_api_key",
        help=f"Leave blank to use {provider.env_prefix}_API_KEY from your environment or .env file.",
    )
    model = st.text_input(
        "Model",
        value=provider.setting("MODEL", provider.model),
        key=f"{provider_id}_model",
        placeholder="Enter the exact provider model ID",
    )
    base_url = provider.base_url
    if provider.editable_url:
        base_url = st.text_input(
            "API base URL",
            value=provider.setting("BASE_URL", provider.base_url),
            key=f"{provider_id}_base_url",
            placeholder="https://your-provider.example/v1",
            help="The OpenAI-compatible API root, without /chat/completions. For Ollama, enter an installed model name above.",
        )
    output_mode = "json_schema"
    if provider_id != "openai":
        mode_default = provider.setting("OUTPUT_MODE", "json_schema")
        output_mode = st.selectbox(
            "Output format",
            list(OUTPUT_MODES),
            key=f"{provider_id}_output_mode",
            index=list(OUTPUT_MODES).index(mode_default) if mode_default in OUTPUT_MODES else 0,
            format_func=lambda value: OUTPUT_MODES[value],
            help="Use JSON only or Prompted JSON if your model doesn't support JSON schemas. All outputs are still validated.",
        )
    configured_key = api_key.strip() or provider.setting("API_KEY")
    st.caption(
        "API key configured"
        if configured_key
        else (
            "Add an API key to generate an investigation."
            if provider.requires_key
            else "No API key needed for a local server. Hosted endpoints may require one."
        )
    )
    st.divider()
    st.markdown(
        "**How it works**\n\n1. Separate facts from assumptions\n2. Plan a testable investigation\n3. Generate your AI IDE prompt"
    )
    st.caption(
        f"Generation sends your intake and evidence to {provider.label} at the selected endpoint in three stages. Results remain in this session unless downloaded."
    )

st.caption("DEVELOPER TOOLS / V1")
st.title("Investigate first.\nFix with evidence.")
st.write(
    "Turn bug reports, logs, and code into a systematic investigation prompt for your AI coding agent."
)
st.caption("Cursor · Windsurf · Claude Code · GitHub Copilot")
st.button("Load example issue", on_click=load_example)

with st.form("intake"):
    st.subheader("01 / Project context")
    left, right = st.columns(2)
    project = left.text_input(
        "Project / repository", key="project", placeholder="e.g. pragathirail-UI", max_chars=20_000
    )
    technology = right.text_input(
        "Technology", key="technology", placeholder="e.g. Angular + TypeScript", max_chars=20_000
    )

    st.subheader("02 / Describe the issue")
    issue = st.text_area("What is the issue? *", key="issue", height=100, max_chars=20_000)
    left, right = st.columns(2)
    expected = left.text_area("Expected behavior *", key="expected", max_chars=20_000)
    actual = right.text_area("Actual behavior *", key="actual", max_chars=20_000)
    reproduction = st.text_area(
        "Reproduction steps",
        key="reproduction_steps",
        placeholder="1. Open…\n2. Click…\n3. Observe…",
        height=100,
        max_chars=20_000,
    )

    st.subheader("03 / Add evidence")
    st.caption(
        "Keep evidence in its category. Include filenames when known. Each field accepts up to 20,000 characters; total intake is limited to 60,000."
    )
    evidence_fields = {}
    tabs = st.tabs(["Text / notes", "Logs", "Stack trace", "Code", "Git diff"])
    for tab, name, label in zip(
        tabs,
        ["other", "logs", "stack_trace", "code", "git_diff"],
        ["Text evidence / notes", "Logs", "Stack trace / errors", "Code snippets", "Git diff"],
    ):
        with tab:
            evidence_fields[name] = st.text_area(label, key=name, height=180, max_chars=20_000)

    st.subheader("04 / Set the boundaries")
    constraints = st.text_area(
        "Constraints",
        key="constraints",
        placeholder="e.g. Preserve public APIs. Avoid unrelated refactoring.",
        height=90,
        max_chars=20_000,
    )
    depth = st.radio(
        "Investigation depth", ["Quick", "Standard", "Deep"], index=1, horizontal=True, key="depth"
    )
    st.caption(
        "Quick: focused checks · Standard: full relevant flow · Deep: competing explanations and edge cases"
    )
    submitted = st.form_submit_button(
        "Generate investigation", type="primary", use_container_width=True
    )

if submitted:
    # Clear any previous successful output so a failed new request cannot show stale results.
    st.session_state.pop("result", None)
    st.session_state.pop("result_input", None)
    try:
        data = InvestigationInput(
            project=project,
            technology=technology,
            issue=issue,
            expected=expected,
            actual=actual,
            reproduction_steps=reproduction,
            constraints=constraints,
            depth=depth,
            evidence=Evidence(**evidence_fields),
        )
        if not any(value.strip() for value in evidence_fields.values()):
            st.info(
                "No evidence supplied. The investigation will focus on discovery and missing information."
            )
        llm = create_llm(
            provider_id=provider_id,
            api_key=configured_key,
            model=model,
            base_url=base_url,
            output_mode=output_mode,
        )
        try:
            with st.status("Building your investigation…", expanded=True) as status:
                llm.on_retry = st.write
                try:
                    result = generate_investigation_prompt(
                        data, llm, on_stage=lambda stage: st.write(f"{stage}…")
                    )
                except LLMError:
                    status.update(label="Generation stopped", state="error")
                    raise
                status.update(label="Investigation ready", state="complete", expanded=False)
            st.session_state.result = result
            st.session_state.result_input = data
            st.session_state.result_model = model.strip()
            st.session_state.result_provider = provider.label
        finally:
            llm.close()
    except ValidationError as exc:
        for error in exc.errors(include_input=False):
            st.error(error["msg"].removeprefix("Value error, "))
    except LLMError as exc:
        st.error(str(exc))

if "result" in st.session_state:
    result = st.session_state.result
    original = st.session_state.result_input
    st.divider()
    st.header("Your investigation")
    st.caption(
        f"Last generated submission · {original.depth} · {st.session_state.get('result_provider', 'OpenAI')} · {st.session_state.result_model}. Submit again to apply any input changes."
    )
    with st.expander("Evidence analysis", expanded=True):
        for name, items in result.analysis.model_dump().items():
            st.markdown(f"**{name.title()}**")
            if not items:
                st.caption("None identified.")
            for item in items:
                st.write(f"• {item}")
    with st.expander("Investigation plan", expanded=True):
        st.markdown("**Areas to inspect**")
        for item in result.plan.areas_to_inspect:
            st.write(f"• {item}")
        st.markdown("**Proposed execution flow — verify in the repository**")
        for i, item in enumerate(result.plan.execution_flow, 1):
            st.write(f"{i}. {item}")
        st.markdown("**Hypotheses to validate**")
        for i, hypothesis in enumerate(result.plan.hypotheses, 1):
            st.write(f"H{i}: {hypothesis.title}")
            st.write(hypothesis.description)
            for check in hypothesis.evidence_to_check:
                st.write(f"• {check}")
        st.markdown("**Verification steps**")
        for i, item in enumerate(result.plan.verification_steps, 1):
            st.write(f"{i}. {item}")
    st.subheader("Final AI IDE prompt")
    st.caption(
        "Use the copy icon in the top-right corner of the prompt, then paste it into your AI IDE."
    )
    st.code(result.prompt, language=None, wrap_lines=True)
    st.download_button(
        "Download prompt (.md)",
        result.prompt,
        file_name="investigation-prompt.md",
        mime="text/markdown",
    )
