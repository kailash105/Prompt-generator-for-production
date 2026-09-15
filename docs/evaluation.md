# V1 quality evaluation

Choose 10 real, previously solved bugs with retained issue descriptions and evidence. Do not include the known solution in the generator inputs.

For each bug, use the same repository revision, coding agent/model, and available evidence:

1. Baseline: give a fresh agent session the issue and evidence with a direct investigation request.
2. Generated prompt: use this app's Standard depth, then paste its prompt into another fresh session.
3. Keep the known root cause hidden until both investigations finish. Stop before applying changes.
4. Record time, repository evidence quality, and whether each investigation found the known cause.
5. Inspect analysis for unsupported facts and the final prompt for premature fix instructions.

| Bug | Right files (0–2) | Correct flow (0–2) | Evidence-grounded (0–2) | Avoids premature fixes (0–2) | Correct cause (0–2) | Baseline minutes | Generated minutes | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | | |
| 2 | | | | | | | | |
| 3 | | | | | | | | |
| 4 | | | | | | | | |
| 5 | | | | | | | | |
| 6 | | | | | | | | |
| 7 | | | | | | | | |
| 8 | | | | | | | | |
| 9 | | | | | | | | |
| 10 | | | | | | | | |

Score both approaches separately using a copy of the table. Use 0 = absent/incorrect, 1 = partial, 2 = complete/correct. Include generation time in the generated-prompt timing. Record model, depth, date, and API usage alongside each run.

Review score differences and time saved. Flag invented identifiers, claims of verified causes without evidence, missed constraints, and unsupported facts even when the final cause happens to be correct. Include at least one sparse-evidence case and one misleading-evidence case. Automated tests alone do not establish investigation quality.
