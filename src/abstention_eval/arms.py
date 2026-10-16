"""The four prompt arms.

The arms differ in EXACTLY ONE respect: what the model is told it may do
instead of picking one of the four options. Everything else -- the preamble,
the item rendering, and the response instruction -- is byte-identical across
arms. `test_arms.py` asserts that, because the whole finding rests on it.

Each arm carries a SHA-256 over its own affordance text and its sorted menu,
so two arms cannot silently share an instrument and a recorded row can always
be traced to the exact wording that produced it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

PREAMBLE = (
    "You are answering a single multiple-choice question.\n"
    "Read the question and the four options.\n"
)

#: Deliberately blunt, and it is a measurement control rather than a style
#: preference.
#:
#: The 2026-10-16 pilot recorded a model expressing an abstention IN PROSE on
#: a flawed item -- "None of the options is correct; 2 + 2 = 4, which isn't
#: listed" -- which the classifier scored `unparseable`, counting it as
#: neither declined nor answered. Prose abstentions are not equally likely
#: across arms, because the arms differ in how easy it is to decline in the
#: sanctioned format, so an unconstrained output format biases the comparison
#: BY ARM. That is the one thing this study cannot tolerate.
#:
#: An assistant-turn prefill would be the robust fix and was tried first.
#: `claude-haiku-5-5` rejects it outright: "This model does not support
#: assistant message prefill. The conversation must end with a user message."
#: So the format is constrained by instruction instead, and whether that
#: worked is decided by the unreadable-output ceiling in `report.py` rather
#: than by assumption.
RESPONSE_INSTRUCTION = (
    "\nReply with ONLY your answer and nothing else: either a single letter, "
    "or the single word shown above for declining. No sentence, no "
    "explanation, no punctuation, no restating the option text.\n"
)

#: The literal token a model must emit to abstain. Arm 0 never mentions it;
#: the runner still scans for it, so an unprompted abstention is recorded
#: rather than silently counted as an unparseable answer.
ABSTAIN_TOKEN = "UNANSWERABLE"


@dataclass(frozen=True)
class Arm:
    arm_id: str
    #: One-line description for the report. Not part of the prompt.
    label: str
    #: The only text that varies between arms.
    affordance: str
    #: Options offered inside the affordance, if any. Hashed sorted so that
    #: reordering the menu does not read as a different instrument.
    menu: tuple[str, ...] = field(default_factory=tuple)
    #: Tokens that mean "I decline" in THIS arm's own sanctioned vocabulary,
    #: beyond the shared abstain token.
    #:
    #: Measured 2026-10-16 on the full run: arm 2 replied with a bare reason
    #: from its own menu -- `NO_CORRECT_OPTION`, 11 times -- without the
    #: UNANSWERABLE prefix the classifier keyed on. Those are abstentions in
    #: the vocabulary the arm itself handed the model, and scoring them as
    #: unreadable undercounted arm 2 and ONLY arm 2, because only arm 2 has a
    #: reason menu. That is a per-arm bias, which is fatal to the comparison.
    #:
    #: This is declared per arm rather than inferred from `menu`, because arm
    #: 3's menu holds substantive answer options rather than reasons for
    #: declining, and conflating the two would be the same error inverted.
    abstain_vocabulary: tuple[str, ...] = field(default_factory=tuple)

    @property
    def prompt_sha256(self) -> str:
        # The whole shared skeleton is hashed, not just the affordance:
        # changing the preamble or the response instruction changes the
        # instrument, and results computed under two skeletons must not be
        # compared even though the arms still differ correctly from each other.
        parts = [
            self.arm_id,
            PREAMBLE,
            self.affordance,
            RESPONSE_INSTRUCTION,
            *sorted(self.menu),
        ]
        return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()

    def render(self, stem: str, options: dict[str, str]) -> str:
        rendered = "\n".join(f"{k}. {options[k]}" for k in sorted(options))
        return (
            f"{PREAMBLE}\n{stem}\n\n{rendered}\n"
            f"{self.affordance}"
            f"{RESPONSE_INSTRUCTION}"
        )


_REASON_MENU = (
    "AMBIGUOUS_STEM",
    "INSUFFICIENT_INFORMATION",
    "MULTIPLE_CORRECT_OPTIONS",
    "NO_CORRECT_OPTION",
    "OUTSIDE_MY_KNOWLEDGE",
)

_CATEGORY_MENU = (
    "E. None of the options above is correct.",
    "F. More than one of the options above is correct.",
    "G. The question cannot be answered as written.",
)

ARMS: tuple[Arm, ...] = (
    Arm(
        arm_id="a0_no_affordance",
        label="No abstention option offered",
        affordance="",
    ),
    Arm(
        arm_id="a1_bare_escape",
        label="Bare escape hatch",
        affordance=(
            f"\nIf you cannot answer, respond {ABSTAIN_TOKEN} instead of a letter.\n"
        ),
    ),
    Arm(
        arm_id="a2_reason_menu",
        label="Escape hatch plus a menu of reasons",
        affordance=(
            f"\nIf you cannot answer, respond {ABSTAIN_TOKEN} followed by one "
            "reason from this list:\n"
            + "\n".join(f"- {r}" for r in _REASON_MENU)
            + "\n"
        ),
        menu=_REASON_MENU,
        abstain_vocabulary=_REASON_MENU,
    ),
    Arm(
        arm_id="a3_category_menu",
        label="Additional substantive options offered",
        affordance=(
            "\nYou may also choose one of these:\n"
            + "\n".join(_CATEGORY_MENU)
            + "\n"
        ),
        menu=_CATEGORY_MENU,
    ),
)

ARMS_BY_ID = {a.arm_id: a for a in ARMS}


def get_arms(selector: str) -> list[Arm]:
    """`selector` is "all" or a comma-separated list of arm ids."""
    if selector == "all":
        return list(ARMS)
    out = []
    for raw in selector.split(","):
        arm_id = raw.strip()
        if arm_id not in ARMS_BY_ID:
            known = ", ".join(ARMS_BY_ID)
            raise KeyError(f"unknown arm {arm_id!r}; known arms: {known}")
        out.append(ARMS_BY_ID[arm_id])
    return out
