"""Command line entry point.

    python -m abstention_eval run --provider stub --arms all --runs 3 \
        --bank items/throwaway.jsonl --out results/stub.csv
    python -m abstention_eval report --csv results/stub.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .arms import get_arms
from .bank import composition, load_bank
from .providers import ProviderAuthError, ProviderRequestError, build_provider
from .report import render, summarise
from .runner import CallBudgetExceeded, plan_calls, run

#: Deliberately low. The full planned study is 4 arms x 3 runs x 60 items =
#: 720 calls; anything materially larger than that should be a decision
#: somebody typed, not a default somebody inherited.
DEFAULT_MAX_CALLS = 800


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="abstention_eval")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="execute arms against the bank")
    run_cmd.add_argument("--provider", choices=("stub", "anthropic"), default="stub")
    run_cmd.add_argument(
        "--model",
        default=None,
        help="required for --provider anthropic; there is no default on purpose",
    )
    run_cmd.add_argument("--arms", default="all")
    run_cmd.add_argument("--runs", type=int, default=3)
    run_cmd.add_argument("--bank", type=Path, required=True)
    # Not required: a --dry-run writes nothing, so demanding a path for it is
    # a long command line for no reason -- and a long command line is how a
    # pasted recipe wraps and silently runs the wrong thing.
    run_cmd.add_argument("--out", type=Path, default=None)
    run_cmd.add_argument("--run-label", default=None)
    run_cmd.add_argument("--max-calls", type=int, default=DEFAULT_MAX_CALLS)
    run_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="print the call count and the arm hashes, then stop",
    )

    # A bounded smoke test against the real API, as one short line. It exists
    # because the equivalent `run` invocation is 156 characters, and a command
    # that wraps when pasted runs something other than what was written.
    pilot_cmd = sub.add_parser(
        "pilot", help="20-call smoke test against the real API on throwaway items"
    )
    pilot_cmd.add_argument("--model", required=True)

    review_cmd = sub.add_parser(
        "review", help="print the bank for human review, compactly"
    )
    review_cmd.add_argument("--bank", type=Path, required=True)
    review_cmd.add_argument(
        "--only",
        choices=("all", "sound", "flawed"),
        default="all",
        help="flawed first is usually the right review order: a mislabelled "
        "flaw is worse than a mislabelled key",
    )

    # The full study as one short line. The equivalent `run` invocation is
    # 158 characters, which wrapped when pasted and lost its --out argument.
    # Three long command lines have now wrapped in this project; a command
    # short enough to paste is a correctness property, not a convenience.
    study_cmd = sub.add_parser(
        "study", help="the full pre-registered run: 4 arms x 3 runs x 60 items"
    )
    study_cmd.add_argument("--model", required=True)

    report_cmd = sub.add_parser("report", help="band and floor from a results csv")
    report_cmd.add_argument("--csv", type=Path, required=True)

    return parser


#: The full pre-registered study. Only the model is a free parameter.
STUDY = {
    "provider": "anthropic",
    "arms": "all",
    "runs": 3,
    "bank": Path("items/bank.jsonl"),
    "out": Path("results/full.csv"),
    "max_calls": 800,
    "run_label": None,
    "dry_run": False,
}

#: Everything the pilot fixes, so the only free parameter is the model.
PILOT = {
    "provider": "anthropic",
    "arms": "all",
    "runs": 1,
    "bank": Path("items/throwaway.jsonl"),
    "out": Path("results/pilot.csv"),
    "max_calls": 25,
    "run_label": None,
    "dry_run": False,
}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "review":
        items = load_bank(args.bank)
        shown = [
            i
            for i in items
            if args.only == "all" or i.population == args.only
        ]
        for item in shown:
            claim = (
                f"KEY {item.key}"
                if item.population == "sound"
                else f"FLAW {item.flaw_type}"
            )
            print(f"[{item.item_id}] {item.population.upper():<6} {claim}")
            print(f"  {item.stem}")
            for letter in sorted(item.options):
                mark = "*" if letter == item.key else " "
                print(f"   {mark}{letter}. {item.options[letter]}")
            print(f"  WHY: {item.rationale or '(none)'}")
            print()
        print(f"{len(shown)} item(s) shown of {len(items)} in the bank.")
        print("Check: does the stated KEY hold, and is the stated FLAW the real flaw?")
        return 0

    if args.command == "report":
        print(render(summarise(args.csv)), end="")
        return 0

    if args.command == "study":
        model = args.model
        args = argparse.Namespace(command="run", model=model, **STUDY)
        print("study: 4 arms x 3 runs x 60 items, ceiling 800 calls\n")

    if args.command == "pilot":
        model = args.model
        args = argparse.Namespace(command="run", model=model, **PILOT)
        print("pilot: 4 arms x 1 run x 5 throwaway items, ceiling 25 calls")
        print("pilot output is a PLUMBING CHECK -- throwaway items, not the bank\n")

    arms = get_arms(args.arms)
    items = load_bank(args.bank)
    counts = composition(items)
    planned = plan_calls(len(arms), args.runs, len(items))

    print(f"bank:    {args.bank} ({len(items)} items: {counts})")
    print(f"arms:    {len(arms)} -> {', '.join(a.arm_id for a in arms)}")
    print(f"runs:    {args.runs}")
    print(f"calls:   {planned} (ceiling {args.max_calls})")
    for arm in arms:
        print(f"  {arm.arm_id:<22} {arm.prompt_sha256[:16]}  {arm.label}")

    if args.dry_run:
        print("\ndry run -- nothing called, nothing written")
        return 0

    if args.out is None:
        print("\nREFUSED: --out is required unless --dry-run is set", file=sys.stderr)
        return 2

    provider = build_provider(args.provider, args.model)
    label = args.run_label or f"{provider.name}-{provider.model}"

    try:
        result = run(
            provider=provider,
            arms=arms,
            items=items,
            runs=args.runs,
            run_label=label,
            out_path=args.out,
            max_calls=args.max_calls,
        )
    except CallBudgetExceeded as exc:
        print(f"\nREFUSED: {exc}", file=sys.stderr)
        return 2
    except ProviderAuthError as exc:
        print(f"\nREFUSED: {exc}", file=sys.stderr)
        return 3
    except ProviderRequestError as exc:
        print(f"\nREFUSED: {exc}", file=sys.stderr)
        return 4

    print(f"\nwrote {result['recorded_rows']} rows to {args.out}")
    print(f"outcomes: {result['tally']}")
    print(
        f"tokens:   in={result['input_tokens']} out={result['output_tokens']}"
        + ("  (stub: no spend)" if provider.is_stub else "")
    )
    print()
    print(render(summarise(args.out)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
