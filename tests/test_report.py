import csv
from pathlib import Path

from abstention_eval.report import render, summarise
from abstention_eval.runner import FIELDNAMES

BASE = {name: "" for name in FIELDNAMES}


def _row(**kwargs):
    return {**BASE, **kwargs}


def _write(tmp_path, rows):
    path = tmp_path / "r.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_band_and_floor_are_computed_across_runs(tmp_path):
    # run 1: 1 of 2 declined (50%). run 2: 2 of 2 declined (100%).
    rows = [
        _row(arm_id="a", population="sound", run_index="1", outcome="abstained",
             provider="stub", model="m", prompt_sha256="h1", item_id="i1"),
        _row(arm_id="a", population="sound", run_index="1", outcome="answered",
             provider="stub", model="m", prompt_sha256="h1", item_id="i2"),
        _row(arm_id="a", population="sound", run_index="2", outcome="abstained",
             provider="stub", model="m", prompt_sha256="h1", item_id="i1"),
        _row(arm_id="a", population="sound", run_index="2", outcome="extra_category",
             provider="stub", model="m", prompt_sha256="h1", item_id="i2"),
    ]
    stats = summarise(_write(tmp_path, rows))["arms"][0]["populations"]["sound"]
    assert stats["runs"] == 2
    assert stats["low"] == 50.0
    assert stats["high"] == 100.0
    assert stats["floor"] == 50.0


def test_a_shared_prompt_hash_is_reported_as_a_collision(tmp_path):
    rows = [
        _row(arm_id="a", population="sound", run_index="1", outcome="answered",
             provider="p", model="m", prompt_sha256="SAME", item_id="i1"),
        _row(arm_id="b", population="sound", run_index="1", outcome="answered",
             provider="p", model="m", prompt_sha256="SAME", item_id="i1"),
    ]
    summary = summarise(_write(tmp_path, rows))
    assert summary["hash_collisions"] == [["a", "b"]]
    assert "PROMPT HASH COLLISION" in render(summary)


def test_distinct_hashes_report_no_collision(tmp_path):
    rows = [
        _row(arm_id="a", population="sound", run_index="1", outcome="answered",
             provider="p", model="m", prompt_sha256="H1", item_id="i1"),
        _row(arm_id="b", population="sound", run_index="1", outcome="answered",
             provider="p", model="m", prompt_sha256="H2", item_id="i1"),
    ]
    summary = summarise(_write(tmp_path, rows))
    assert summary["hash_collisions"] == []
    assert "prompt hashes distinct across arms: yes" in render(summary)


def test_stub_output_is_banner_marked_and_never_reads_as_a_finding(tmp_path):
    rows = [
        _row(arm_id="a", population="sound", run_index="1", outcome="answered",
             provider="stub", model="stub-deterministic-v1", prompt_sha256="H1",
             item_id="i1"),
    ]
    rendered = render(summarise(_write(tmp_path, rows)))
    assert "PIPELINE CHECK, not a finding" in rendered


def test_real_provider_gets_no_stub_banner(tmp_path):
    rows = [
        _row(arm_id="a", population="sound", run_index="1", outcome="answered",
             provider="anthropic", model="some-model", prompt_sha256="H1",
             item_id="i1"),
    ]
    rendered = render(summarise(_write(tmp_path, rows)))
    assert "PIPELINE CHECK" not in rendered


def test_report_refuses_rates_when_too_much_output_was_unreadable(tmp_path):
    """15% unreadable was the real pilot rate. It must not render as a finding."""
    rows = []
    for i in range(20):
        outcome = "unparseable" if i < 3 else "answered"
        rows.append(
            _row(arm_id="a", population="sound", run_index="1", outcome=outcome,
                 provider="anthropic", model="m", prompt_sha256="H1", item_id=f"i{i}")
        )
    summary = summarise(_write(tmp_path, rows))
    assert summary["unparseable"] == 3
    assert summary["unparseable_pct"] == 15.0
    assert summary["renderable"] is False

    rendered = render(summary)
    assert "REFUSING TO REPORT RATES" in rendered
    assert "declined band" not in rendered, "a refused report must not print rates"


def test_report_renders_when_output_is_clean(tmp_path):
    rows = [
        _row(arm_id="a", population="sound", run_index="1", outcome="answered",
             provider="anthropic", model="m", prompt_sha256="H1", item_id="i1"),
    ]
    summary = summarise(_write(tmp_path, rows))
    assert summary["renderable"] is True
    assert "declined band" in render(summary)
    assert "REFUSING" not in render(summary)


def test_one_unreadable_in_fifty_is_under_the_ceiling(tmp_path):
    rows = [
        _row(arm_id="a", population="sound", run_index="1",
             outcome="unparseable" if i == 0 else "answered",
             provider="anthropic", model="m", prompt_sha256="H1", item_id=f"i{i}")
        for i in range(50)
    ]
    summary = summarise(_write(tmp_path, rows))
    assert summary["unparseable_pct"] == 2.0
    assert summary["renderable"] is True


def test_truncated_rows_count_against_the_ceiling_but_report_separately(tmp_path):
    rows = [
        _row(arm_id="a", population="sound", run_index="1",
             outcome="truncated" if i < 3 else "answered",
             provider="anthropic", model="m", prompt_sha256="H1", item_id=f"i{i}")
        for i in range(20)
    ]
    summary = summarise(_write(tmp_path, rows))
    assert summary["truncated"] == 3
    assert summary["unparseable"] == 0
    assert summary["lost"] == 3
    assert summary["renderable"] is False

    rendered = render(summary)
    assert "truncated 3" in rendered
    assert "unparseable 0" in rendered
    assert "REFUSING TO REPORT RATES" in rendered


def test_off_format_is_reported_per_arm_not_only_globally(tmp_path):
    """Arm 0 read 0% declined while its one off-format reply WAS a decline it
    expressed in prose. A global total cannot surface that concentration."""
    rows = [
        _row(arm_id="a0", population="flawed", run_index="1", outcome="off_format",
             provider="anthropic", model="m", prompt_sha256="H0", item_id="i1"),
        _row(arm_id="a0", population="flawed", run_index="1", outcome="answered",
             provider="anthropic", model="m", prompt_sha256="H0", item_id="i2"),
        _row(arm_id="a1", population="flawed", run_index="1", outcome="abstained",
             provider="anthropic", model="m", prompt_sha256="H1", item_id="i1"),
        _row(arm_id="a1", population="flawed", run_index="1", outcome="answered",
             provider="anthropic", model="m", prompt_sha256="H1", item_id="i2"),
    ]
    summary = summarise(_write(tmp_path, rows))
    by_arm = {a["arm_id"]: a["populations"]["flawed"] for a in summary["arms"]}

    assert by_arm["a0"]["off_format_high"] == 50.0
    assert by_arm["a0"]["low"] == 0.0, "off-format must not count as declining"
    assert by_arm["a1"]["off_format_high"] == 0.0
    assert by_arm["a1"]["low"] == 50.0

    rendered = render(summary)
    assert "off-format" in rendered
    assert "did not record" in rendered
