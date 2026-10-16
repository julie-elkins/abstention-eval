# abstention-eval

**An evaluation that reports how often a model declined to answer is partly
reporting its own prompt.**

> **PRE-REGISTERED, THEN MEASURED.** The design, the arms and the analysis plan
> were written before any model was called, so the conclusion could not be
> chosen after seeing the data.
>
> **What backs that ordering, precisely:** this repository was put under version
> control *after* the first run, so no commit predates the data and git cannot
> be the evidence. What exists is a file ordering — the design text and the arm
> definitions were last written at 13:46 and 13:51 on 2026-10-16, the pilot ran
> at 14:08 and the full study at 14:24 — plus the fact that the pre-run text is
> committed here as its own first commit, separate from the commit that added
> the results. Read the pre-registration claim as exactly that strong and no
> stronger. A study about instruments overstating themselves should not overstate
> its own provenance.

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
| `sound` | 40 | a **false** abstention — an answer the prompt cost us |
| `flawed` | 20 | **correct** — the prompt earned it |

A `flawed` item is defective in a stated way, and the 20 are split across three
named flaw types: `no_correct_option` (7), `multiple_correct_options` (7), and
`unanswerable_stem` (6). **The flaw type is not a label, it is a third
population** — see *The flawed population is not one population* below, which
is the finding that changed how this study reports itself.

Reporting only the `flawed` rate is how an abstention study flatters itself: a
prompt that declines on everything scores perfectly on that population alone.
An escape hatch has a price and a benefit, and a single number cannot show
both at once.

## Results

Model: `claude-haiku-5-5` · date: 2026-10-16 · runs per arm: 3 · items: 60 ·
calls: 720 (ceiling 800) · tokens: 166,968 in / 62,181 out · spend: **≈$0.05**
(estimated from published list prices at $0.10/$0.50 per MTok, not read off a
bill) · lost rows: 0/720 · backing data: `results/published/full.csv`

| Arm | `sound` declined | floor | `flawed` declined | floor | off-format (flawed) |
|---|---|---|---|---|---|
| `a0_no_affordance` | 0.0% – 0.0% | 0.0 | 0.0% – 0.0% | 0.0 | 5.0% – 15.0% |
| `a1_bare_escape` | 0.0% – 0.0% | 0.0 | 30.0% – 40.0% | 10.0 | 0.0% – 0.0% |
| `a2_reason_menu` | 0.0% – 0.0% | 0.0 | 55.0% – 60.0% | 5.0 | 15.0% – 25.0% |
| `a3_category_menu` | 0.0% – 0.0% | 0.0 | 85.0% – 95.0% | 10.0 | 0.0% – 0.0% |

**The headline.** Changing only how the option to decline is offered moved the
measured decline rate on flawed items from 0% to 85–95%. The same model, the
same items, the same instruction to answer. An abstention rate quoted without
its prompt is not a property of the model.

**The control did its job.** Across 40 sound items × 3 runs × 4 arms — 480
observations — the decline rate was 0.0% in every single cell. No arm bought its
flawed-item gain with false abstentions. That is what makes the headline a
measurement finding rather than a demonstration that nagging a model makes it
hedge.

**Arm 0's zero is an undercount, and the off-format column is how you can tell.**
With no sanctioned way to decline, arm 0 replied in neither format on 5–15% of
flawed items — and *all* of that is concentrated in one flaw type (see below).
It was declining; the instrument had nowhere to record it. Arm 2's 15–25%
off-format means its 55–60% is an undercount too. Neither number is corrected
here, because guessing at what an off-format reply meant is how a result becomes
an opinion.

**Rates are bands across three runs, never point estimates.** The `floor` is
`max - min` across those runs: how much of the band is run-to-run movement
rather than anything about the arm. **A floor wider than the gap between two
arms means those two arms have not been shown to differ.** Read the floors
before reading the gaps.

## The flawed population is not one population

The pooled `flawed` rate above is an average over three flaw types that do not
behave alike. Split out, the single monotonic curve becomes three curves:

| flaw type (n per run) | `a0` | `a1` bare escape | `a2` reason menu | `a3` category menu |
|---|---|---|---|---|
| `no_correct_option` (7) | 0.0% | **57.1% – 71.4%** | 57.1% – 71.4% | 100% |
| `multiple_correct_options` (7) | 0.0% | **0.0% – 0.0%** | 42.9% – 57.1% | 71.4% – 85.7% |
| `unanswerable_stem` (6) | 0.0% | 33.3% – 50.0% | 50.0% – 66.7% | 83.3% – 100% |

**A bare escape hatch is blind to an entire flaw class.** Arm 1 declined
57–71% of `no_correct_option` items and a flat **0.0%** of
`multiple_correct_options` items — in the same runs, on the same model. Not a
weaker effect: no effect at all.

The mechanism is visible in the arm text rather than inferred. Arm 1's
affordance is *"If you cannot answer, respond UNANSWERABLE"*. An item with two
defensibly correct options **can** be answered — the model picks one and is
scored correct. "Cannot answer" gives that defect no form to take. Arm 3 offers
*"more than one correct"* as a lettered option, and the defect appears.

So the sharper claim is not that scaffolding makes a model more willing to
decline. It is that **an abstention instrument can only detect the flaw classes
its response format has words for.** A study that offers a bare escape hatch and
reports an abstention rate has silently scoped its own finding to the defects
that hatch can express.

**Two comparisons do not survive the split.** Per-class cells hold 6–7 items, so
one item moving is 14–17 points — wider than several of the gaps being compared:

- `a1` → `a2` on `no_correct_option` does **not** separate. Both are
  57.1%–71.4%. The entire pooled `a1`→`a2` gain comes from the other two
  classes, not from uniform improvement.
- `a2` → `a3` on `multiple_correct_options` separates by about 14 points against
  a 14-point floor. That one is marginal and nothing here leans on it.

What clearly survives: `a0`→`a1` on two of three classes, arm 1's zero, and arm
3 at or near ceiling on `no_correct_option`.

**The reporting changed because of this.** `abstention-eval report` now always
prints the per-class split beneath the pooled row, labels the pooled row
`flawed (POOLED - see split)`, and computes blind spots rather than leaving them
to a reader's eye. It is not behind a flag: a caveat that lives behind an option
is a caveat somebody turns off.

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
- **A perfect specificity result is weaker than 0.0% makes it look.** No arm
  ever declined a sound item, which is the control working — but it shows no
  false abstention on *clearly* sound items. The 40 were written to be
  unambiguous, so none of them sits near the sound/flawed boundary. A bank with
  genuinely borderline items is where an escape hatch would start costing
  answers, and this study does not contain that bank.
- **Per-class rates rest on 6–7 items.** The three-way split is the honest way
  to report the flawed population and it is not a precise one. Treat the class
  curves as showing which classes behave differently, not as estimates of how
  much.

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
