import pytest

from models.investigation import (
    Evidence,
    EvidenceAnalysis,
    Hypothesis,
    InvestigationInput,
    InvestigationPlan,
    PromptDraft,
)


@pytest.fixture
def intake():
    return InvestigationInput(
        project="rail-ui",
        technology="TypeScript",
        issue="Route disappears",
        expected="Route remains",
        actual="Route is missing",
        reproduction_steps="Upload, draw, then redraw",
        constraints="Preserve public APIs",
        evidence=Evidence(
            logs="before: 2\nafter: 0",
            code="  const route = `A`;\n```\n",
            git_diff="- keep(route)\n+ prune(route)",
        ),
    )


@pytest.fixture
def outputs():
    return [
        EvidenceAnalysis(
            facts=["[logs] before: 2, after: 0"],
            assumptions=["Redraw may remove routes"],
            unknowns=["Which stage removes routes?"],
            signals=["[git_diff] prune(route)"],
        ),
        InvestigationPlan(
            areas_to_inspect=["Discover redraw implementation"],
            execution_flow=["Redraw entry", "Entity pruning", "UI update"],
            hypotheses=[
                Hypothesis(
                    title="Pruning removes routes",
                    description="Route entities may be excluded.",
                    evidence_to_check=[
                        "Support: routes absent after pruning; reject: routes survive pruning."
                    ],
                )
            ],
            verification_steps=["Reproduce and compare route counts across each stage"],
        ),
        PromptDraft(
            investigation_steps=["Locate prune and trace route objects through redraw"],
            verification_focus=["Check route counts before and after pruning"],
        ),
    ]


class FakeLLM:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def generate(self, instructions, payload, schema):
        self.calls.append((instructions, payload, schema))
        result = self.outputs.pop(0)
        if isinstance(result, Exception):
            raise result
        return schema.model_validate(result)


@pytest.fixture
def fake_llm(outputs):
    return FakeLLM(outputs)
