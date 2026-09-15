from prompts.common import GROUNDING

SYSTEM_PROMPT = (
    GROUNDING
    + """
Stage 3: Write clear, ordered instructions for an AI IDE using intake, analysis, and plan.
Return investigation_steps and verification_focus. Turn the plan into actionable repository
searches, tracing, comparisons, and hypothesis checks. Preserve relevant provided symbols,
reproduction conditions, depth, and constraints. Require file/line evidence from the coding
agent. Do not solve the issue or claim access to files. No file modifications during the
initial investigation. Include how to resolve unknowns and what to do if evidence remains
insufficient. Avoid generic boilerplate; focus on this particular issue.
The application adds original evidence, hypotheses, constraints, and required output sections,
so do not repeat those sections in your response.
"""
)
