"""Validated contracts between intake and the three model stages."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Text = Annotated[str, Field(max_length=20_000)]
Depth = Literal["Quick", "Standard", "Deep"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(StrictModel):
    logs: Text = ""
    stack_trace: Text = ""
    code: Text = ""
    git_diff: Text = ""
    other: Text = ""


class InvestigationInput(StrictModel):
    project: Text = ""
    technology: Text = ""
    issue: Text
    expected: Text
    actual: Text
    reproduction_steps: Text = ""
    constraints: Text = ""
    depth: Depth = "Standard"
    evidence: Evidence = Field(default_factory=Evidence)

    @model_validator(mode="after")
    def validate_intake(self):
        for name in ("issue", "expected", "actual"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name.replace('_', ' ').capitalize()} is required.")
        total = sum(len(value) for value in self.model_dump(exclude={"evidence"}).values()) + sum(
            len(value) for value in self.evidence.model_dump().values()
        )
        if total > 60_000:
            raise ValueError(
                "Input exceeds 60,000 characters. Narrow the evidence to the relevant excerpts."
            )
        return self


class EvidenceAnalysis(StrictModel):
    facts: list[NonEmpty]
    assumptions: list[NonEmpty]
    unknowns: list[NonEmpty]
    signals: list[NonEmpty]


class Hypothesis(StrictModel):
    title: NonEmpty
    description: NonEmpty
    evidence_to_check: list[NonEmpty] = Field(min_length=1)


class InvestigationPlan(StrictModel):
    areas_to_inspect: list[NonEmpty] = Field(min_length=1)
    execution_flow: list[NonEmpty] = Field(min_length=1)
    hypotheses: list[Hypothesis] = Field(min_length=1)
    verification_steps: list[NonEmpty] = Field(min_length=1)


class PromptDraft(StrictModel):
    """Model-written instructions, wrapped with original inputs by the renderer."""

    investigation_steps: list[NonEmpty] = Field(min_length=1)
    verification_focus: list[NonEmpty] = Field(min_length=1)


class InvestigationResult(StrictModel):
    analysis: EvidenceAnalysis
    plan: InvestigationPlan
    prompt: str
