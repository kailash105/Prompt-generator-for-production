from prompts.common import GROUNDING

SYSTEM_PROMPT = (
    GROUNDING
    + """
Stage 1: Analyze the evidence. Return facts, assumptions, unknowns, and signals.
Each fact must name its source, e.g. [issue: developer report], [logs], [code], or [git_diff],
and point to a short concrete excerpt or observation. Reported expected/actual behavior
is a developer report, not independently verified. Do not promote inference into facts.
Assumptions are tentative interpretations; unknowns are questions still unresolved.
Signals are evidence-backed search terms, identifiers, errors, or transitions to investigate.
Leave a category empty if unsupported. Missing evidence must appear in unknowns.
"""
)
