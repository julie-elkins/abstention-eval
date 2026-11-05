# Design decisions

This study is about the validity of an evaluation instrument, so its own design choices
are part of the result. These records explain what was held constant, what was measured,
and where the claims stop.

The format follows the
[decision-reasoning template](https://github.com/julie-elkins/agent-systems-design-guide/blob/main/DESIGN_DECISION_TEMPLATE.md).

## 1. Change only the affordance to decline

- **Problem:** A refusal-rate comparison is uninterpretable if prompt wording changes
  other behaviours at the same time.
- **Decision:** Use four arms that add one affordance at a time while keeping the prompt
  skeleton, item rendering, and answer instruction identical.
- **Instead of:** Comparing unrelated prompts and attributing every difference to the
  option to abstain.
- **Why:** The study asks what the affordance itself moves.
- **Implementation:** `tests/test_arms.py` strips the affordance and asserts byte-
  identical prompt skeletons; each arm carries a hash of its declared affordance.
- **Verification:** The test suite and report refuse shared or mismatched arm metadata.
- **Costs if wrong:** The measured difference could be a prompt-format or instruction
  effect rather than an abstention effect.
- **What this does not prove:** It does not establish how other prompt changes behave.

## 2. Measure refusal as a semantic outcome

- **Problem:** One arm does not use the literal word `UNANSWERABLE`, so counting that
  token would make the comparison mechanically unfair.
- **Decision:** Measure whether the model declined to choose among the real options, then
  report the narrower output-format breakdown separately.
- **Instead of:** Treating one response string as the universal definition of refusal.
- **Why:** The quantity must exist in every arm before it can be compared.
- **Implementation:** The scorer distinguishes semantic decline from off-format output
  and preserves the scorer version with the results.
- **Verification:** Report tests cover arm-specific vocabulary and off-format rows.
- **Costs if wrong:** A prompt could appear not to affect abstention simply because it
  expressed the refusal differently.
- **What this does not prove:** Classification is still bounded by the declared item
  populations and scorer rules.

## 3. Keep sound and flawed populations separate

- **Problem:** A prompt that declines on everything can look excellent if only
  unanswerable items are reported.
- **Decision:** Report false abstention on sound items and correct abstention on flawed
  items, with flaw type retained as a separate population.
- **Instead of:** Publishing one overall refusal rate.
- **Why:** The escape hatch has both a benefit and a cost.
- **Implementation:** The item bank labels the populations and the report includes each
  stratum.
- **Verification:** Bank tests and report tests fail when the populations or flaw types
  collapse.
- **Costs if wrong:** The headline can reward a prompt that avoids answering useful
  questions.
- **What this does not prove:** The fixture is not a representative sample of every
  task or model.

## 4. State provenance at exactly the strength the evidence supports

- **Problem:** Calling a study pre-registered because it was committed after the first
  run would overstate the evidence.
- **Decision:** Describe the file-ordering and commit separation, and explicitly say
  that git cannot prove the claim retrospectively.
- **Instead of:** Treating version control as proof that no design choice changed after
  seeing results.
- **Why:** An evaluation about instrument overstatement must not overstate its own
  provenance.
- **Implementation:** The README states the dates, the limitation, and the exact
  strength of the claim.
- **Verification:** A reviewer can inspect the repository history and the recorded
  result files.
- **Costs if wrong:** Readers may infer a stronger preregistration guarantee than exists.
- **What this does not prove:** File ordering is weaker than an external timestamped
  preregistration.

