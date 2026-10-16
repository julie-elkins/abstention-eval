"""Turn recorded rows into a band and a floor.

Never a point estimate. A single run's rate is one draw; the band across
repeated runs is what the instrument actually supports, and the floor
(max - min) is how much of the band is run-to-run movement rather than
anything about the arm. A floor wider than the gap between two arms means
those two arms have not been shown to differ.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from .bank import FLAW_TYPES, POPULATIONS
from .runner import declined

STUB_BANNER = (
    "!! provider=stub -- these numbers are a PIPELINE CHECK, not a finding.\n"
    "!! The stub's behaviour is hand-written to be arm-sensitive. It cannot\n"
    "!! be evidence about any model. Re-run with --provider anthropic.\n"
)

#: Above this share of unreadable replies, `render` prints a refusal instead
#: of rates.
#:
#: An `unparseable` row is counted as neither declined nor answered, so it
#: leaves both numerators silently. Worse, prose replies are not equally
#: likely across arms, so the loss is not uniform and can manufacture or
#: erase the effect being measured. The 2026-10-16 pilot ran at 15%. The raw
#: csv is always kept -- it is the evidence that the instrument misfired --
#: but the summary must not render, because a rate with an unexamined hole in
#: it reads exactly like a rate without one.
MAX_UNPARSEABLE_PCT = 2.0


def _rate(declined_count: int, total: int) -> float:
    return 0.0 if total == 0 else 100.0 * declined_count / total


def summarise(csv_path: Path) -> dict:
    # (arm_id, population, run_index) -> [declined, total, off_format]
    #
    # off_format is tracked PER ARM, not just globally. Measured 2026-10-16:
    # arm 0 reported 0% declined on flawed items while its one off-format
    # reply WAS a flawed item it had declined in prose. A global off-format
    # total cannot show that concentration, and the concentration is the
    # point: the arm with no sanctioned way to decline is the arm whose
    # declining goes unrecorded.
    cells: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    # (arm_id, flaw_type, run_index) -> [declined, total, off_format]
    #
    # The flawed population is NOT one population. Measured 2026-10-16 on
    # claude-haiku-5-5: arm a1 (a bare escape hatch) declined 57-71% of
    # `no_correct_option` items and a flat 0.0% of `multiple_correct_options`
    # in the same runs. Its pooled 30-40% is the average of a class it
    # detects and a class it cannot express, and the average is the only
    # number a reader would otherwise see. An item with two correct options
    # is still answerable -- the model picks one and is right -- so a bare
    # "say so if you cannot answer" gives that defect no sanctioned form.
    # The split is therefore always rendered, never a flag: a caveat that
    # lives behind an option is a caveat somebody turns off.
    flaw_cells: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    arm_order: list[str] = []
    providers: set[str] = set()
    models: set[str] = set()
    scorers: set[str] = set()
    hashes: dict[str, set[str]] = defaultdict(set)
    total_rows = 0
    unparseable = 0
    truncated = 0
    off_format = 0

    with csv_path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            total_rows += 1
            # Both are lost observations, so both count against the ceiling,
            # but they are reported separately because the remedies differ.
            if row["outcome"] == "unparseable":
                unparseable += 1
            elif row["outcome"] == "truncated":
                truncated += 1
            elif row["outcome"] == "off_format":
                off_format += 1
            arm = row["arm_id"]
            if arm not in arm_order:
                arm_order.append(arm)
            providers.add(row["provider"])
            models.add(row["model"])
            scorers.add(row.get("scorer_version") or "unrecorded")
            hashes[arm].add(row["prompt_sha256"])
            cell = cells[(arm, row["population"], row["run_index"])]
            cell[1] += 1
            if declined(row["outcome"]):
                cell[0] += 1
            if row["outcome"] == "off_format":
                cell[2] += 1

            # Sound rows carry flaw_type "" by construction (bank.py refuses a
            # sound item that names one), so this only ever keys flawed rows.
            if row["population"] == "flawed" and row["flaw_type"]:
                flaw_cell = flaw_cells[(arm, row["flaw_type"], row["run_index"])]
                flaw_cell[1] += 1
                if declined(row["outcome"]):
                    flaw_cell[0] += 1
                if row["outcome"] == "off_format":
                    flaw_cell[2] += 1

    arms_out = []
    for arm in arm_order:
        per_population = {}
        for population in POPULATIONS:
            matching = [
                cells[(arm, population, run_index)]
                for (a, p, run_index) in cells
                if a == arm and p == population
            ]
            if not matching:
                continue
            rates = [_rate(c[0], c[1]) for c in matching]
            off_rates = [_rate(c[2], c[1]) for c in matching]
            low, high = min(rates), max(rates)
            per_population[population] = {
                "runs": len(rates),
                "low": low,
                "high": high,
                "floor": high - low,
                "off_format_low": min(off_rates),
                "off_format_high": max(off_rates),
            }
        per_flaw_type = {}
        for flaw_type in FLAW_TYPES:
            matching = [
                flaw_cells[(a, f, run_index)]
                for (a, f, run_index) in flaw_cells
                if a == arm and f == flaw_type
            ]
            if not matching:
                continue
            rates = [_rate(c[0], c[1]) for c in matching]
            off_rates = [_rate(c[2], c[1]) for c in matching]
            low, high = min(rates), max(rates)
            per_flaw_type[flaw_type] = {
                "runs": len(rates),
                # Carried so a reader can size the granularity without
                # arithmetic: at 7 items one flip is 14.3 points, which is
                # wider than several of the between-arm gaps being compared.
                "items_per_run": max(c[1] for c in matching),
                "low": low,
                "high": high,
                "floor": high - low,
                "off_format_low": min(off_rates),
                "off_format_high": max(off_rates),
            }

        arms_out.append(
            {
                "arm_id": arm,
                "prompt_sha256": sorted(hashes[arm]),
                "populations": per_population,
                "flaw_types": per_flaw_type,
            }
        )

    collisions = _hash_collisions(hashes)
    blind_spots = _blind_spots(arms_out)
    lost = unparseable + truncated
    unparseable_pct = _rate(lost, total_rows)
    return {
        "providers": sorted(providers),
        "models": sorted(models),
        "scorers": sorted(scorers),
        "arms": arms_out,
        "hash_collisions": collisions,
        "blind_spots": blind_spots,
        "is_stub": "stub" in providers,
        "total_rows": total_rows,
        "unparseable": unparseable,
        "truncated": truncated,
        "off_format": off_format,
        "off_format_pct": _rate(off_format, total_rows),
        "lost": lost,
        "unparseable_pct": unparseable_pct,
        "renderable": unparseable_pct <= MAX_UNPARSEABLE_PCT,
    }


def _blind_spots(arms_out: list[dict]) -> list[dict]:
    """Flaw classes an arm never declined, in an arm that declines something.

    This is the finding the pooled rate hides, so it is computed rather than
    left to a reader's eye. The guard is `arm_flawed_high > 0`: an arm that
    never declines anything has no blind spot, it has no affordance -- that
    is the control arm doing its job, not a defect in the instrument.

    A blind spot is a claim about EXPRESSIBILITY, not about the model's
    ability. The model may well detect the flaw and have no sanctioned way to
    report it, which is exactly why the off-format column sits beside this.
    """
    spots: list[dict] = []
    for arm in arms_out:
        flawed = arm["populations"].get("flawed")
        if not flawed or flawed["high"] == 0.0:
            continue
        for flaw_type, stats in arm["flaw_types"].items():
            if stats["high"] == 0.0:
                spots.append(
                    {
                        "arm_id": arm["arm_id"],
                        "flaw_type": flaw_type,
                        "items_per_run": stats["items_per_run"],
                        "arm_flawed_low": flawed["low"],
                        "arm_flawed_high": flawed["high"],
                    }
                )
    return spots


def _hash_collisions(hashes: dict[str, set[str]]) -> list[list[str]]:
    """Two arms sharing a prompt hash means they are not two arms."""
    by_hash: dict[str, list[str]] = defaultdict(list)
    for arm, digests in hashes.items():
        for digest in digests:
            by_hash[digest].append(arm)
    return [sorted(arms) for arms in by_hash.values() if len(arms) > 1]


def render(summary: dict) -> str:
    lines: list[str] = []
    if summary["is_stub"]:
        lines.append(STUB_BANNER)

    lines.append(f"provider(s): {', '.join(summary['providers'])}")
    lines.append(f"model(s):    {', '.join(summary['models'])}")
    lines.append(f"scorer:      {', '.join(summary['scorers'])}")
    lines.append(
        f"lost rows:   {summary['lost']}/{summary['total_rows']} "
        f"({summary['unparseable_pct']:.1f}%)  "
        f"[unparseable {summary['unparseable']}, truncated {summary['truncated']}]"
    )
    lines.append(
        f"off-format:  {summary['off_format']}/{summary['total_rows']} "
        f"({summary['off_format_pct']:.1f}%) -- replied in neither format; "
        "NOT counted as declining"
    )
    lines.append("")

    if not summary["renderable"]:
        lines.append(
            f"!! REFUSING TO REPORT RATES: {summary['unparseable_pct']:.1f}% of replies\n"
            f"!! were unreadable, over the {MAX_UNPARSEABLE_PCT:.1f}% ceiling.\n"
            "!!\n"
            "!! An unreadable reply counts as neither declined nor answered, so it\n"
            "!! leaves both numerators. Prose replies are not equally likely across\n"
            "!! arms, so the loss is not uniform and can create or hide the effect.\n"
            "!!\n"
            "!! The raw csv is intact -- inspect the `raw_text` column on the\n"
            "!! unparseable rows, fix the instrument, and re-run.\n"
        )
        return "\n".join(lines) + "\n"

    lines.append("Declined = the model did not pick one of A-D.")
    lines.append("Rates are a BAND across runs; floor = max - min.")
    lines.append("")

    header = (
        f"{'arm':<22} {'population':<34} {'runs':>4}  {'declined band':>16}  "
        f"{'floor':>6}  {'off-format':>14}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for arm in summary["arms"]:
        first = True
        for population, stats in arm["populations"].items():
            band = f"{stats['low']:.1f}% - {stats['high']:.1f}%"
            off = f"{stats['off_format_low']:.1f}% - {stats['off_format_high']:.1f}%"
            label = population
            if population == "flawed" and arm["flaw_types"]:
                # Never let the pooled figure stand unqualified in the one
                # column a reader scans. The caveat is welded into the row
                # label rather than left to the prose underneath.
                label = "flawed (POOLED - see split)"
            lines.append(
                f"{arm['arm_id'] if first else '':<22} {label:<34} {stats['runs']:>4}  "
                f"{band:>16}  {stats['floor']:>5.1f}  {off:>14}"
            )
            first = False
            if population != "flawed":
                continue
            for flaw_type, flaw_stats in arm["flaw_types"].items():
                flaw_band = f"{flaw_stats['low']:.1f}% - {flaw_stats['high']:.1f}%"
                flaw_off = (
                    f"{flaw_stats['off_format_low']:.1f}% - "
                    f"{flaw_stats['off_format_high']:.1f}%"
                )
                sub = f"  - {flaw_type} [n={flaw_stats['items_per_run']}]"
                lines.append(
                    f"{'':<22} {sub:<34} {flaw_stats['runs']:>4}  "
                    f"{flaw_band:>16}  {flaw_stats['floor']:>5.1f}  {flaw_off:>14}"
                )
    lines.append("")
    lines.append(
        "off-format is NOT counted as declining. Read it beside the declined\n"
        "band: an arm with a high off-format rate is declining in ways this\n"
        "instrument did not record."
    )
    lines.append("")
    lines.append(
        "The pooled `flawed` row averages flaw classes that behave differently,\n"
        "so it is reported only beside its split. Per-class cells hold 6-7 items\n"
        "per run, where one item is 14-17 points -- wider than several of the\n"
        "between-arm gaps, so compare a class against its own floor before\n"
        "claiming two arms differ on it."
    )

    if summary["blind_spots"]:
        lines.append("")
        lines.append(
            "!! BLIND SPOT -- an arm that declines other classes never declined these:"
        )
        for spot in summary["blind_spots"]:
            lines.append(
                f"!!   {spot['arm_id']}: {spot['flaw_type']} "
                f"0.0% in every run [n={spot['items_per_run']}], while the same arm "
                f"declined {spot['arm_flawed_low']:.1f}-{spot['arm_flawed_high']:.1f}% "
                "of flawed items overall."
            )
        lines.append(
            "!! This is a claim about what the response format can EXPRESS, not\n"
            "!! about what the model can detect. Quoting that arm's pooled rate\n"
            "!! as its abstention ability states an average over a class it has\n"
            "!! no words for."
        )

    if summary["hash_collisions"]:
        lines.append("")
        lines.append("!! PROMPT HASH COLLISION -- these arms share an instrument:")
        for group in summary["hash_collisions"]:
            lines.append(f"!!   {', '.join(group)}")
    else:
        lines.append("")
        lines.append("prompt hashes distinct across arms: yes")

    return "\n".join(lines) + "\n"
