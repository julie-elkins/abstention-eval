# abstention-eval

**An evaluation that reports how often a model declined to answer is partly
reporting its own prompt.**

> ⚠️ **PRE-REGISTERED, NOT YET MEASURED.** The design, the arms and the
> analysis below were written and committed *before* any model was called, so
> the conclusion could not be chosen after seeing the data. Every number in
> this file currently reads `TK`. **A `TK` is not a small number — it is the
> absence of one.** If you are reading a `TK` in a published version of this
> file, the run has not happened and nothing here is a result.

---

## The question

Published evaluations routinely report an abstention or refusal rate: *the
model declined on 12% of cases*, *it correctly refused 90% of unanswerable
questions*. Those figures get read as properties of the model.

They are measured, though, through a prompt that had to tell the model that
declining was permitted at all — and had to decide how to say so. This study
asks a narrow question about that:

**If the only thing that changes is how the option to decline is offered, how
much does the measured decline rate move?**

That is a question about construct validity: whether the instrument measures
the thing it names. If the answer is "a lot", then an abstention rate quoted
without its prompt is not interpretable, and two papers reporting different
refusal rates for the same model may be reporting their own wording.

## The design

Four arms. Each adds exactly one thing to the one before it. **Nothing else
differs** — not the preamble, not the item rendering, not the instruction to
answer.

| Arm | What it adds |
|---|---|
| `a0_no_affordance` | nothing — the option to decline is never mentioned |
| `a1_bare_escape` | "If you cannot answer, respond UNANSWERABLE" |
| `a2_reason_menu` | a closed menu of five reasons it might be unanswerable |
| `a3_category_menu` | three extra lettered options (none correct / more than one correct / cannot be answered) |

`tests/test_arms.py` strips each arm's affordance text and asserts the
remaining prompt skeleton is byte-identical across all four. The whole study
rests on that, so it is a test rather than an intention. Each arm also carries
a SHA-256 over its own affordance and its sorted menu, recorded on every row,
and the report refuses to stay quiet if two arms ever share one.

### The measured quantity is "declined", not "said UNANSWERABLE"

Arm 3 never offers the word UNANSWERABLE; it offers extra letters instead.
Comparing arm 3's UNANSWERABLE rate against arm 0's would compare something
that cannot happen with something that can, and would read as *the menu had no
effect*. The quantity that exists in every arm is whether the model refused to
pick among the four real options. That is what is compared. The narrower
breakdown is recorded alongside it in the CSV.

### Two item populations, and both are load-bearing

| Population | n | Declining is… |
|---|---|---|
| `sound` | TK | a **false** abstention — an answer the prompt cost us |
| `flawed` | TK | **correct** — the prompt earned it |

A `flawed` item is defective in a stated way: no correct option, more than one
defensibly correct option, or a stem that omits what is needed to choose.

Reporting only the `flawed` rate is how an abstention study flatters itself: a
prompt that declines on everything scores perfectly on that population alone.
An escape hatch has a price and a benefit, and a single number cannot show
both at once.

## Results

> `TK` — the run has not been executed. Fill from
> `results/published/` and name the model, the date and the measured spend.

Model: `TK` · date: `TK` · runs per arm: 3 · items: TK · calls: TK · spend: `TK`

| Arm | `sound` declined | floor | `flawed` declined | floor |
|---|---|---|---|---|
| `a0_no_affordance` | TK | TK | TK | TK |
| `a1_bare_escape` | TK | TK | TK | TK |
| `a2_reason_menu` | TK | TK | TK | TK |
| `a3_category_menu` | TK | TK | TK | TK |

**Rates are bands across three runs, never point estimates.** The `floor` is
`max - min` across those runs: how much of the band is run-to-run movement
rather than anything about the arm. **A floor wider than the gap between two
arms means those two arms have not been shown to differ.** Read the floors
before reading the gaps.

## What this does not show

- **Nothing about any other model.** One model, named above. The claim is
  about the instrument, and a second model could behave differently.
- **Nothing about any other item bank.** The bank here is 60 hand-written
  items in one domain. A bank of harder or more ambiguous items would move
  every rate.
- **Nothing about which wording is *correct*.** The four arms are not ranked.
  A prompt that declines more is not thereby better; that depends entirely on
  what a false abstention costs you.
- **Nothing about why.** This measures that the rate moved, not what the model
  was doing. No interpretability claim is made or implied.
- **It is not a generalisation to free-text tasks.** Multiple choice makes
  "declined" cleanly observable, which is the reason this design is tractable
  and also the reason it is narrow.
- **Three runs is a small number of runs.** The floor is an estimate of
  run-to-run movement from three draws, which is enough to show movement
  exists and not enough to characterise it.

## Reproducing it

Everything except the final run works with no API key and no spend, because a
repository whose claims cannot be checked without a credit card is not
checkable.

```
uv venv --python 3.11
uv pip install -e ".[dev]"
.venv/bin/python -m pytest -q
```

Dry run — prints the call count and every arm's prompt hash, calls nothing:

```
.venv/bin/abstention-eval run --dry-run --bank items/bank.jsonl
```

Offline pipeline check against a deterministic stub provider:

```
.venv/bin/abstention-eval run --bank items/bank.jsonl --out results/stub.csv
```

**Stub output is a plumbing check and never a result.** Its behaviour is
hand-written to be arm-sensitive so the pipeline tests are not vacuous, every
row it writes is stamped `provider=stub`, and the report prints a banner
saying so. Its floors all read `0.0` because it is deterministic — which is
the clearest example in this repository of a zero that means *nothing was
measured* rather than *nothing moved*.

The real run needs `ANTHROPIC_API_KEY` in the environment and an explicitly
named model. There is no default model on purpose: a recorded number must name
the thing that produced it.

```
.venv/bin/abstention-eval run --provider anthropic --model MODEL \
    --bank items/bank.jsonl --runs 3 --out results/full.csv
```

A run that exceeds `--max-calls` is refused before it spends anything, and a
run that dies partway deletes its own output rather than leaving a short CSV
that `report` would read as a complete run.

## The item bank

60 items, four options each, written from scratch for this study. **They are
not drawn from, derived from, or adapted from any certification exam, item
bank, practice test or proprietary question set.**

`items/bank.template.jsonl` documents the composition, the three flaw types
and the authoring rules. The loader enforces the structural ones: a `sound`
item must carry a key and no flaw type, a `flawed` item must carry a flaw type
and no key, and every item must have exactly four options.

## Licences

Code is MIT (`LICENSE`). The item bank — every stem, option, key, rationale
and flaw annotation — is CC BY 4.0 (`items/LICENSE`), so it can be reused,
including in work that disagrees with this one.

## Related

[`nl2sql-eval`](https://github.com/julie-elkins/nl2sql-eval) measured a
text-to-SQL model and found the mirror image of this question: one case where
it invented an answer it could not support, and one where it refused a
question it could have answered. The conclusion there was that a single
accuracy number cannot show both failures at once. This repository is the
narrower follow-up — not *how often does the model get it wrong*, but *how
much of the rate is the instrument*.
