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

from .bank import POPULATIONS
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
    arm_order: list[str] = []
    providers: set[str] = set()
    models: set[str] = set()
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
            hashes[arm].add(row["prompt_sha256"])
            cell = cells[(arm, row["population"], row["run_index"])]
            cell[1] += 1
            if declined(row["outcome"]):
                cell[0] += 1
            if row["outcome"] == "off_format":
                cell[2] += 1

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
        arms_out.append(
            {
                "arm_id": arm,
                "prompt_sha256": sorted(hashes[arm]),
                "populations": per_population,
            }
        )

    collisions = _hash_collisions(hashes)
    lost = unparseable + truncated
    unparseable_pct = _rate(lost, total_rows)
    return {
        "providers": sorted(providers),
        "models": sorted(models),
        "arms": arms_out,
        "hash_collisions": collisions,
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
        f"{'arm':<22} {'population':<10} {'runs':>4}  {'declined band':>16}  "
        f"{'floor':>6}  {'off-format':>14}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for arm in summary["arms"]:
        for population, stats in arm["populations"].items():
            band = f"{stats['low']:.1f}% - {stats['high']:.1f}%"
            off = f"{stats['off_format_low']:.1f}% - {stats['off_format_high']:.1f}%"
            lines.append(
                f"{arm['arm_id']:<22} {population:<10} {stats['runs']:>4}  "
                f"{band:>16}  {stats['floor']:>5.1f}  {off:>14}"
            )
    lines.append("")
    lines.append(
        "off-format is NOT counted as declining. Read it beside the declined\n"
        "band: an arm with a high off-format rate is declining in ways this\n"
        "instrument did not record."
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
