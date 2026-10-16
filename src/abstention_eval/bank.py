"""Loading and validating the item bank.

Two populations, and the distinction is the point of the study:

  sound   -- exactly one option is correct. An abstention here is a FALSE
             abstention: an answer the instrument cost us.
  flawed  -- the item is defective in a stated way (no correct option, more
             than one correct option, or an unanswerable stem). An abstention
             here is CORRECT: the instrument earned it.

Reporting only one of those two rates is how an abstention study flatters
itself. A prompt that abstains on everything looks perfect on `flawed` alone.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

POPULATIONS = ("sound", "flawed")

FLAW_TYPES = (
    "no_correct_option",
    "multiple_correct_options",
    "unanswerable_stem",
)

REQUIRED_OPTION_KEYS = {"A", "B", "C", "D"}


@dataclass(frozen=True)
class Item:
    item_id: str
    stem: str
    options: dict[str, str]
    population: str
    #: Set on `sound` items only.
    key: str | None = None
    #: Set on `flawed` items only.
    flaw_type: str | None = None
    #: Never shown to the model. The record of why the key or the flaw holds.
    rationale: str | None = None


def _validate(raw: dict, line_no: int) -> Item:
    def fail(msg: str) -> None:
        raise ValueError(f"item bank line {line_no}: {msg}")

    for required in ("item_id", "stem", "options", "population"):
        if required not in raw:
            fail(f"missing {required!r}")

    population = raw["population"]
    if population not in POPULATIONS:
        fail(f"population must be one of {POPULATIONS}, got {population!r}")

    options = raw["options"]
    if not isinstance(options, dict) or set(options) != REQUIRED_OPTION_KEYS:
        fail(f"options must have exactly keys {sorted(REQUIRED_OPTION_KEYS)}")

    key = raw.get("key")
    flaw_type = raw.get("flaw_type")

    if population == "sound":
        if key not in REQUIRED_OPTION_KEYS:
            fail("a sound item needs `key` set to one of A-D")
        if flaw_type is not None:
            fail("a sound item must not carry `flaw_type`")
    else:
        if flaw_type not in FLAW_TYPES:
            fail(f"a flawed item needs `flaw_type` in {FLAW_TYPES}")
        if key is not None:
            fail("a flawed item must not carry `key` -- there is no single key")

    return Item(
        item_id=raw["item_id"],
        stem=raw["stem"],
        options=options,
        population=population,
        key=key,
        flaw_type=flaw_type,
        rationale=raw.get("rationale"),
    )


def load_bank(path: Path) -> list[Item]:
    items: list[Item] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            item = _validate(json.loads(line), line_no)
            if item.item_id in seen:
                raise ValueError(
                    f"item bank line {line_no}: duplicate item_id {item.item_id!r}"
                )
            seen.add(item.item_id)
            items.append(item)
    if not items:
        raise ValueError(f"item bank {path} contains no items")
    return items


def composition(items: list[Item]) -> dict[str, int]:
    counts = {p: 0 for p in POPULATIONS}
    for item in items:
        counts[item.population] += 1
    return counts
