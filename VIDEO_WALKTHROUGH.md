# HackerRank video walkthrough

Target length: about four minutes. Read the spoken text naturally; the bracketed
notes are screen directions, not narration. Keep the browser or terminal zoom high
enough that the README and report are readable. Do not show a terminal containing an
API key.

## 0:00–0:25 — The question

**[Show the top of `README.md`, including the title and “The question”.]**

“This evaluation asks a narrow question: if the same model sees the same items, but
the prompt changes only in how it permits a decline, does the measured abstention rate
change? Abstention means declining to choose an answer.

That matters because an evaluation instrument—the procedure that turns a model response
into a reported score—can affect the number it produces. A refusal rate quoted without
the response format that enabled it may partly describe the instrument rather than the
model.”

## 0:25–1:00 — The domain and the test bank

**[Scroll to “Submission information”, then show the beginning of “The design”.]**

“My domain is technical assessment and language-model evaluation. I wrote this as a
synthetic multiple-choice study, not as a certification exam or a production safety
claim.

The bank contains 60 items: 40 sound items and 20 deliberately flawed items. The
flawed items cover three types: no correct option, multiple correct options, and an
unanswerable stem. The item bank and its license are included so the test is
inspectable and reusable.”

## 1:00–1:35 — The four arms

**[Open `src/abstention_eval/arms.py`. Scroll slowly through the four arm definitions.
If useful, show the arm table in the README first.]**

“The experiment has four arms. An arm is one controlled version of the prompt.

The first gives no decline affordance. The second says to respond
`UNANSWERABLE` if the model cannot answer. The third adds a menu of reasons. The
fourth adds explicit categories, including ‘more than one correct.’

Everything else stays fixed: the preamble, the item, the options, and the instruction
to answer. The tests remove each affordance and verify that the remaining prompt
skeleton is identical. Each row also records a prompt hash, which is a fingerprint
that lets us check which prompt version produced it.”

## 1:35–2:10 — Scoring and reproducibility

**[Open `src/abstention_eval/runner.py`, then `src/abstention_eval/report.py`. Show
the terminal with the commands below, but do not run a live API call.]**

```text
uv run pytest -q
uv run python -m abstention_eval report --csv results/published/full.csv
```

“The scorer measures whether the model selected one of the four real answer options.
It keeps answered, abstained, off-format, unparseable, and truncated responses
separate. That matters because a response that does not fit the declared vocabulary
should not silently become a success.

The published run used `claude-haiku-5-5` on October 16, 2026: three runs per arm,
60 items per run, and 720 calls. There were no lost rows. The repository also includes
67 automated tests, a deterministic stub for an offline pipeline check, the raw
published CSV, and the exact scorer version.”

## 2:10–3:05 — The result

**[Show the report output. Scroll to the pooled rows, then the per-flaw split and the
blind-spot warning.]**

“On sound items, every arm declined zero percent. That is the control: the added
decline options did not create false abstentions on the clearly answerable items in
this bank. A false abstention would mean the model refused an item that had a valid
answer.

Now look at the flawed items, where declining is the desired behavior. The recorded
decline rate moved from zero percent with no decline affordance, to 30–45 percent
with a bare escape word, 70–75 percent with a reason menu, and 90–95 percent with
the category menu. An affordance is simply an explicit response the prompt allows
the model to give.

There is an important qualification in the first zero. In the no-affordance arm,
5–15 percent of flawed responses were off-format: the model produced something that
was not one of A through D and was not one of that arm's declared decline responses.
The scorer keeps those separate instead of silently counting them as abstentions.
So the result is not “the model answered every flawed item.” It is “the instrument
recorded no sanctioned declines when the prompt supplied no way to express one.”

The most important result is the split by flaw type. The bare escape arm declined
57–86 percent of items with no correct option, but zero percent of items with
multiple correct options. An item with no correct option cannot be answered
correctly, so the word `UNANSWERABLE` gives that problem a usable output. An item
with multiple correct options can still be answered by choosing one option, so the
word `UNANSWERABLE` does not name that defect.

The category menu adds an explicit response for “more than one correct.” Once that
response exists, the same model declined 86 percent of those items. That change is
why the per-flaw split matters: the pooled flawed rate hides that one defect is
invisible to the bare escape arm.

That is not evidence that the model could not recognize multiple correct options.
The experiment cannot distinguish “the model did not notice the defect” from “the
model noticed it but had no permitted output for it.” It does show that the response
format gave that defect no sanctioned way to appear. The instrument can only detect
flaw classes that its vocabulary can express.”

## 3:05–3:35 — Prior work and limits

**[Show the README sections “Prior work and sources” and “What this does not show”.]**

“This repository existed before the hackathon, and I am disclosing that as prior work.
It is the narrower follow-up to my earlier evaluation work, including the related
`nl2sql-eval` repository. This submission does not claim that the work was created
during the event.

The limits are deliberate: one named model, one synthetic 60-item bank, three runs,
small per-class cells, and a multiple-choice task. The result does not generalize to
every model, every bank, or free-text evaluation. It also does not rank the four
wordings as universally correct.”

## 3:35–4:00 — Reproduce and close

**[Show the “Reproducing it” section and then the package command in the README.]**

“A reviewer can install the project with `uv`, run the tests without an API key,
run the deterministic stub, and reproduce the report against the published CSV.
Repeating the Anthropic run requires an API key and an explicitly named model, and
the runner enforces a call ceiling before it spends anything.

The point of this evaluation is not a larger refusal number. It is to make visible
when the measurement itself decides what the model is allowed to demonstrate.”

**[End on the README’s result table or the report’s blind-spot warning.]**
