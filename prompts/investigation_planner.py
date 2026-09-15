from prompts.common import GROUNDING

SYSTEM_PROMPT = (
    GROUNDING
    + """
Stage 2: Create a testable investigation plan using the original intake and validated analysis.
Return areas_to_inspect, execution_flow, hypotheses, and verification_steps.
The execution flow is a proposed path to trace, not a verified call graph.
For each hypothesis, explain the possible mechanism and specify repository evidence
that would support AND reject it in evidence_to_check. Prioritize signals provided in
the analysis. Cover discovery, tracing data/state transformations, comparing expected
and actual behavior, and verifying competing explanations. Include reproduction steps
and constraints. Treat hypotheses as unverified; do not announce a root cause.
"""
)
