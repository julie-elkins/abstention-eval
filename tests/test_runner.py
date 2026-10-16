import csv
from pathlib import Path

import pytest

from abstention_eval.arms import get_arms
from abstention_eval.bank import load_bank
from abstention_eval.providers import StubProvider
from abstention_eval.runner import (
    CallBudgetExceeded,
    classify,
    declined,
    run,
)

BANK = Path(__file__).resolve().parents[1] / "items" / "throwaway.jsonl"


def test_classify_abstention():
    assert classify("UNANSWERABLE").outcome == "abstained"
    assert classify("unanswerable no_correct_option").outcome == "abstained"


def test_classify_answer():
    verdict = classify("B")
    assert verdict.outcome == "answered"
    assert verdict.answer_letter == "B"


def test_classify_extra_category():
    assert classify("G").outcome == "extra_category"


def test_classify_off_format():
    """Substantive text in neither sanctioned format. Measured on arm 0: the
    model replied "None" when offered no way to decline."""
    assert classify("I would rather not say.").outcome == "off_format"
    assert classify("None").outcome == "off_format"


def test_off_format_is_not_scored_as_declining():
    """Scoring it as a decline would give arm 0 a different classification
    rule from every other arm -- the exact confound this study avoids."""
    assert not declined("off_format")


def test_classify_unparseable_is_an_empty_reply_that_ended_normally():
    assert classify("", "end_turn").outcome == "unparseable"


def test_abstention_wins_over_a_stray_letter():
    """A reason menu makes a letter appear in an abstaining reply."""
    assert classify("UNANSWERABLE AMBIGUOUS_STEM").outcome == "abstained"


def test_declined_covers_both_ways_of_not_choosing():
    assert declined("abstained")
    assert declined("extra_category")
    assert not declined("answered")
    assert not declined("unparseable")


def test_run_closes_its_arithmetic_and_writes_every_row(tmp_path):
    items = load_bank(BANK)
    arms = get_arms("a0_no_affordance,a1_bare_escape")
    out = tmp_path / "r.csv"

    result = run(
        provider=StubProvider(),
        arms=arms,
        items=items,
        runs=1,
        run_label="t",
        out_path=out,
        max_calls=100,
    )

    assert result["planned_calls"] == 2 * 1 * len(items)
    assert result["recorded_rows"] == result["planned_calls"]
    assert sum(result["tally"].values()) == result["planned_calls"]

    with out.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == result["planned_calls"]
    assert {r["arm_id"] for r in rows} == {a.arm_id for a in arms}


def test_run_refuses_to_exceed_the_call_ceiling(tmp_path):
    items = load_bank(BANK)
    with pytest.raises(CallBudgetExceeded, match="over the --max-calls ceiling"):
        run(
            provider=StubProvider(),
            arms=get_arms("all"),
            items=items,
            runs=3,
            run_label="t",
            out_path=tmp_path / "r.csv",
            max_calls=5,
        )


def test_refused_run_writes_nothing(tmp_path):
    out = tmp_path / "r.csv"
    with pytest.raises(CallBudgetExceeded):
        run(
            provider=StubProvider(),
            arms=get_arms("all"),
            items=load_bank(BANK),
            runs=3,
            run_label="t",
            out_path=out,
            max_calls=1,
        )
    assert not out.exists(), "a refused run must not leave a partial csv"


def test_a_run_that_dies_partway_leaves_no_csv_at_all(tmp_path):
    """A short csv at out_path would be read by `report` as a complete run."""
    items = load_bank(BANK)
    out = tmp_path / "r.csv"

    class DiesOnThirdCall(StubProvider):
        def __init__(self):
            self.calls = 0

        def complete(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 3:
                raise RuntimeError("provider exploded")
            return super().complete(*args, **kwargs)

    with pytest.raises(RuntimeError, match="provider exploded"):
        run(
            provider=DiesOnThirdCall(),
            arms=get_arms("all"),
            items=items,
            runs=1,
            run_label="t",
            out_path=out,
            max_calls=100,
        )

    assert not out.exists(), "a dead run left a partial csv behind"
    assert not out.with_name(out.name + ".partial").exists(), "scratch file not cleaned up"


def test_a_successful_run_leaves_no_scratch_file(tmp_path):
    out = tmp_path / "r.csv"
    run(
        provider=StubProvider(),
        arms=get_arms("a0_no_affordance"),
        items=load_bank(BANK),
        runs=1,
        run_label="t",
        out_path=out,
        max_calls=100,
    )
    assert out.exists()
    assert not out.with_name(out.name + ".partial").exists()


def test_an_empty_reply_that_hit_the_ceiling_is_truncated_not_unparseable():
    """Measured 2026-10-16: three empty replies, output_tokens == max_tokens.
    Scoring those as `unparseable` sent the fix in the wrong direction twice."""
    assert classify("", "max_tokens").outcome == "truncated"


def test_an_empty_reply_that_ended_normally_is_unparseable():
    assert classify("", "end_turn").outcome == "unparseable"


def test_a_readable_reply_is_classified_on_its_text_not_its_stop_reason():
    assert classify("B", "max_tokens").outcome == "answered"
    assert classify("UNANSWERABLE", "max_tokens").outcome == "abstained"


def test_stop_reason_is_recorded_on_every_row(tmp_path):
    out = tmp_path / "r.csv"
    run(
        provider=StubProvider(),
        arms=get_arms("a0_no_affordance"),
        items=load_bank(BANK),
        runs=1,
        run_label="t",
        out_path=out,
        max_calls=50,
    )
    with out.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert all(r["stop_reason"] for r in rows), "a row with no stop_reason is undiagnosable"


def test_a_bare_reason_from_the_arms_own_menu_is_an_abstention():
    """Measured on the full run: arm 2 replied `NO_CORRECT_OPTION` 11 times
    with no UNANSWERABLE prefix. Scoring that unreadable undercounted arm 2
    and only arm 2, because only arm 2 has a reason menu."""
    vocab = ("NO_CORRECT_OPTION", "AMBIGUOUS_STEM")
    assert classify("NO_CORRECT_OPTION", "end_turn", vocab).outcome == "abstained"
    assert classify("ambiguous_stem", "end_turn", vocab).outcome == "abstained"


def test_an_improvised_refusal_is_not_in_any_vocabulary_so_stays_off_format():
    """Arm 0 replied 'declining' / 'NONE' / 'DECLINE'. Accepting those would
    give arm 0 a looser classification rule than every other arm."""
    for text in ("declining", "NONE", "DECLINE"):
        assert classify(text, "end_turn", ()).outcome == "off_format"
        assert classify(text, "end_turn", ("NO_CORRECT_OPTION",)).outcome == "off_format"


def test_arm_three_options_are_not_treated_as_an_abstain_vocabulary():
    from abstention_eval.arms import ARMS_BY_ID

    assert ARMS_BY_ID["a3_category_menu"].abstain_vocabulary == ()
    assert ARMS_BY_ID["a2_reason_menu"].abstain_vocabulary != ()
