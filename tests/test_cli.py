"""CLI argument handling.

The `--out`-optional-under-dry-run behaviour is here because a long command
line wraps when pasted into a terminal, and a wrapped command runs something
other than what was written. Shorter commands are a correctness property, not
a convenience.
"""

from pathlib import Path

import pytest

from abstention_eval.cli import main

BANK = str(Path(__file__).resolve().parents[1] / "items" / "throwaway.jsonl")


def test_dry_run_needs_no_out_path(capsys):
    code = main(["run", "--dry-run", "--bank", BANK])
    assert code == 0
    assert "nothing called, nothing written" in capsys.readouterr().out


def test_dry_run_prints_the_call_count_and_every_arm_hash(capsys):
    main(["run", "--dry-run", "--bank", BANK, "--arms", "all", "--runs", "3"])
    out = capsys.readouterr().out
    assert "calls:   60" in out
    for arm_id in (
        "a0_no_affordance",
        "a1_bare_escape",
        "a2_reason_menu",
        "a3_category_menu",
    ):
        assert arm_id in out


def test_a_real_run_without_out_is_refused(capsys):
    code = main(["run", "--bank", BANK])
    assert code == 2
    assert "--out is required" in capsys.readouterr().err


def test_a_real_run_writes_when_given_out(tmp_path, capsys):
    out = tmp_path / "r.csv"
    code = main(["run", "--bank", BANK, "--runs", "1", "--out", str(out)])
    assert code == 0
    assert out.exists()


def test_over_ceiling_is_refused_with_exit_2(tmp_path, capsys):
    code = main(
        [
            "run",
            "--bank",
            BANK,
            "--runs",
            "3",
            "--max-calls",
            "5",
            "--out",
            str(tmp_path / "r.csv"),
        ]
    )
    assert code == 2
    assert "over the --max-calls ceiling" in capsys.readouterr().err


def test_unknown_arm_is_an_error():
    with pytest.raises(KeyError):
        main(["run", "--dry-run", "--bank", BANK, "--arms", "nope"])


def test_pilot_is_bounded_and_fixes_everything_but_the_model(capsys, monkeypatch):
    """The pilot must refuse without a key rather than silently do nothing."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not set"):
        main(["pilot", "--model", "some-model"])
    out = capsys.readouterr().out
    assert "ceiling 25 calls" in out
    assert "PLUMBING CHECK" in out


def test_pilot_requires_a_model():
    with pytest.raises(SystemExit):
        main(["pilot"])


def test_study_fixes_everything_but_the_model(capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not set"):
        main(["study", "--model", "some-model"])
    assert "ceiling 800 calls" in capsys.readouterr().out


def test_study_requires_a_model():
    with pytest.raises(SystemExit):
        main(["study"])
