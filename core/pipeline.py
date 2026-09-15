from collections.abc import Callable

from core.analyzer import analyze_evidence
from core.generator import generate_ide_prompt
from core.planner import create_investigation_plan
from models.investigation import InvestigationInput, InvestigationResult
from utils.llm import LLMError, StructuredLLM


def generate_investigation_prompt(
    input_data: InvestigationInput,
    llm: StructuredLLM,
    on_stage: Callable[[str], None] | None = None,
) -> InvestigationResult:
    stage = "Evidence analysis"
    try:
        if on_stage:
            on_stage(stage)
        analysis = analyze_evidence(input_data, llm)
        stage = "Investigation planning"
        if on_stage:
            on_stage(stage)
        plan = create_investigation_plan(input_data, analysis, llm)
        stage = "Prompt generation"
        if on_stage:
            on_stage(stage)
        prompt = generate_ide_prompt(input_data, analysis, plan, llm)
        return InvestigationResult(analysis=analysis, plan=plan, prompt=prompt)
    except LLMError as exc:
        raise LLMError(f"{stage} failed. {exc}") from None
