from models.investigation import EvidenceAnalysis, InvestigationInput
from prompts.common import DEPTH_GUIDANCE
from prompts.evidence_analyzer import SYSTEM_PROMPT
from utils.llm import StructuredLLM


def analyze_evidence(data: InvestigationInput, llm: StructuredLLM) -> EvidenceAnalysis:
    return llm.generate(
        SYSTEM_PROMPT + DEPTH_GUIDANCE[data.depth],
        {"intake": data.model_dump()},
        EvidenceAnalysis,
    )
