from models.investigation import EvidenceAnalysis, InvestigationInput, InvestigationPlan
from prompts.common import DEPTH_GUIDANCE
from prompts.investigation_planner import SYSTEM_PROMPT
from utils.llm import StructuredLLM


def create_investigation_plan(
    data: InvestigationInput, analysis: EvidenceAnalysis, llm: StructuredLLM
) -> InvestigationPlan:
    return llm.generate(
        SYSTEM_PROMPT + DEPTH_GUIDANCE[data.depth],
        {"intake": data.model_dump(), "analysis": analysis.model_dump()},
        InvestigationPlan,
    )
