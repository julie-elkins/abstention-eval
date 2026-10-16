"""Execute arms against the bank and record one row per call.

The headline metric is `declined` -- the model did not pick one of A-D --
and NOT the narrower "said UNANSWERABLE".

That choice is forced rather than stylistic. Arm 3 never offers the word
UNANSWERABLE; it offers extra lettered options instead. Comparing arm 3's
UNANSWERABLE rate against arm 0's would compare a thing that cannot happen
with a thing that can, and would read as "the menu had no effect". The
quantity that exists in every arm is whether the model declined to choose
among the four real options, so that is what is compared. The breakdown is
recorded alongside it so the narrow rate is still available.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .arms import ABSTAIN_TOKEN, Arm
from .bank import Item

FIELDNAMES = (
    "run_label",
    "run_index",
    "arm_id",
    "prompt_sha256",
    "provider",
    "model",
    "temperature",
    "item_id",
    "population",
    "flaw_type",
    "key",
    "outcome",
    "answer_letter",
    "correct",
    "raw_text",
    "stop_reason",
    "scorer_version",
    "input_tokens",
    "output_tokens",
    "recorded_at",
)

#: A bare letter on its own, optionally followed by punctuation.
_LETTER = re.compile(r"\b([A-G])\b")

#: Bumped whenever classification SEMANTICS change, and recorded on every
#: row. The prompt hash covers what the model was shown; it says nothing
#: about how the reply was scored, so two runs can share a prompt hash and
#: disagree because the scorer moved underneath them.
#:
#: v2, 2026-10-16: a bare token from an arm's own abstain vocabulary counts
#: as an abstention. v1 scored those `off_format`, which undercounted arm 2
#: and only arm 2.
SCORER_VERSION = "v2-2026-10-16"

OUTCOMES = (
    "answered",
    "abstained",
    "extra_category",
    "off_format",
    "unparseable",
    "truncated",
)


@dataclass(frozen=True)
class Classified:
    outcome: str
    answer_letter: str | None


def classify(
    text: str,
    stop_reason: str = "",
    abstain_vocabulary: tuple[str, ...] = (),
) -> Classified:
    """`truncated` is kept separate from `unparseable` on purpose: both are
    lost observations, but one is fixed by raising the token ceiling and the
    other by constraining the output format. An empty reply looks identical
    either way, so the cause has to come from `stop_reason` rather than from
    inference."""
    if not text and stop_reason == "max_tokens":
        return Classified("truncated", None)
    if not text:
        return Classified("unparseable", None)
    upper = text.upper()
    if ABSTAIN_TOKEN in upper:
        return Classified("abstained", None)
    # A bare token from the arm's own declared vocabulary. Mechanical, not
    # interpretive: the arm handed the model this exact word list.
    if upper.strip() in {v.upper() for v in abstain_vocabulary}:
        return Classified("abstained", None)
    match = _LETTER.search(upper)
    if match is None:
        # Substantive text in neither sanctioned format. Measured 2026-10-16:
        # on arm 0, where no way to decline is offered at all, the model
        # replied "None" -- it declined anyway, in its own words, after 205
        # tokens of deliberation.
        #
        # This is NOT scored as a decline. Doing so would give arm 0 a
        # different classification rule from every other arm, which is the
        # confound this study exists to avoid. It is recorded and reported as
        # its own quantity instead, because an eval offering no escape hatch
        # does not measure zero abstention -- it measures abstention its
        # parser cannot see, and that is worth showing rather than absorbing.
        return Classified("off_format", None)
    letter = match.group(1)
    if letter in {"E", "F", "G"}:
        return Classified("extra_category", letter)
    return Classified("answered", letter)


def declined(outcome: str) -> bool:
    """The comparable quantity across every arm."""
    return outcome in {"abstained", "extra_category"}


class CallBudgetExceeded(RuntimeError):
    pass


def plan_calls(n_arms: int, n_runs: int, n_items: int) -> int:
    return n_arms * n_runs * n_items


def run(
    *,
    provider,
    arms: list[Arm],
    items: list[Item],
    runs: int,
    run_label: str,
    out_path: Path,
    max_calls: int,
) -> dict:
    planned = plan_calls(len(arms), runs, len(items))
    if planned > max_calls:
        raise CallBudgetExceeded(
            f"this run would make {planned} calls, over the --max-calls ceiling "
            f"of {max_calls}. Raise the ceiling deliberately or shrink the run."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tally = {outcome: 0 for outcome in OUTCOMES}
    input_tokens = output_tokens = 0

    # Write to a scratch path and move it into place only on success. A run
    # that dies halfway would otherwise leave a short csv at `out_path` that
    # `report` reads as a complete run -- a partial result that looks whole,
    # and one that always reads as fewer calls rather than as a failure.
    partial = out_path.with_name(out_path.name + ".partial")

    try:
        with partial.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            for run_index in range(1, runs + 1):
                for arm in arms:
                    for item in items:
                        prompt = arm.render(item.stem, item.options)
                        completion = provider.complete(
                            arm, prompt, item.item_id, item.population
                        )
                        verdict = classify(
                            completion.text,
                            completion.stop_reason,
                            arm.abstain_vocabulary,
                        )
                        tally[verdict.outcome] += 1
                        input_tokens += completion.input_tokens
                        output_tokens += completion.output_tokens
                        writer.writerow(
                            {
                                "run_label": run_label,
                                "run_index": run_index,
                                "arm_id": arm.arm_id,
                                "prompt_sha256": arm.prompt_sha256,
                                "provider": provider.name,
                                "model": provider.model,
                                "temperature": "" if provider.is_stub else "1.0",
                                "item_id": item.item_id,
                                "population": item.population,
                                "flaw_type": item.flaw_type or "",
                                "key": item.key or "",
                                "outcome": verdict.outcome,
                                "answer_letter": verdict.answer_letter or "",
                                "correct": (
                                    ""
                                    if item.key is None
                                    or verdict.answer_letter is None
                                    else str(verdict.answer_letter == item.key).lower()
                                ),
                                "raw_text": completion.text,
                                "stop_reason": completion.stop_reason,
                                "scorer_version": SCORER_VERSION,
                                "input_tokens": completion.input_tokens,
                                "output_tokens": completion.output_tokens,
                                "recorded_at": datetime.now(timezone.utc).isoformat(),
                            }
                        )
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    recorded = sum(tally.values())
    if recorded != planned:
        partial.unlink(missing_ok=True)
        raise AssertionError(
            f"arithmetic did not close: planned {planned} calls, recorded {recorded}"
        )

    partial.replace(out_path)

    return {
        "planned_calls": planned,
        "recorded_rows": recorded,
        "tally": tally,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "prompt_hashes": {arm.arm_id: arm.prompt_sha256 for arm in arms},
    }
