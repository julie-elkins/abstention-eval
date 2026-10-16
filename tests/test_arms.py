"""The control the whole finding rests on.

If the arms differ in anything except the abstention affordance, the study
measures that other difference too and the headline claim is unsupported.
These tests are the only thing standing between the repository and that.
"""

import pytest

from abstention_eval.arms import ARMS, Arm, get_arms

STEM = "What is 2 + 2?"
OPTIONS = {"A": "3", "B": "4", "C": "5", "D": "6"}


def _skeleton(arm: Arm) -> str:
    """The prompt with this arm's affordance removed."""
    prompt = arm.render(STEM, OPTIONS)
    if arm.affordance == "":
        return prompt
    assert arm.affordance in prompt, f"{arm.arm_id} did not render its affordance"
    return prompt.replace(arm.affordance, "")


def test_arms_differ_only_in_the_affordance():
    skeletons = {arm.arm_id: _skeleton(arm) for arm in ARMS}
    distinct = set(skeletons.values())
    assert len(distinct) == 1, (
        "arms differ somewhere other than the affordance block: "
        f"{sorted(skeletons)} produced {len(distinct)} different skeletons"
    )


def test_every_arm_has_a_distinct_prompt_hash():
    digests = [arm.prompt_sha256 for arm in ARMS]
    assert len(set(digests)) == len(ARMS), "two arms share a prompt hash"


def test_hash_is_stable_under_menu_reordering():
    base = next(a for a in ARMS if a.menu)
    shuffled = Arm(
        arm_id=base.arm_id,
        label=base.label,
        affordance=base.affordance,
        menu=tuple(reversed(base.menu)),
    )
    assert shuffled.prompt_sha256 == base.prompt_sha256


def test_hash_changes_when_the_menu_changes():
    base = next(a for a in ARMS if a.menu)
    altered = Arm(
        arm_id=base.arm_id,
        label=base.label,
        affordance=base.affordance,
        menu=base.menu + ("A_NEW_REASON",),
    )
    assert altered.prompt_sha256 != base.prompt_sha256


def test_arm_zero_never_names_the_abstain_token():
    arm0 = ARMS[0]
    assert "UNANSWERABLE" not in arm0.render(STEM, OPTIONS)


def test_get_arms_rejects_an_unknown_id():
    with pytest.raises(KeyError):
        get_arms("a9_does_not_exist")


def test_get_arms_all_returns_every_arm():
    assert len(get_arms("all")) == len(ARMS)


def test_the_shared_skeleton_is_part_of_every_arm_identity():
    """Changing the preamble or the response instruction changes the
    instrument, so results from two skeletons must not be comparable -- even
    though the arms still differ correctly from one another."""
    import abstention_eval.arms as mod

    before = [a.prompt_sha256 for a in mod.ARMS]
    original = mod.RESPONSE_INSTRUCTION
    try:
        mod.RESPONSE_INSTRUCTION = "\nAnswer however you like.\n"
        after = [a.prompt_sha256 for a in mod.ARMS]
    finally:
        mod.RESPONSE_INSTRUCTION = original

    assert before != after, "the response instruction is not hashed into arm identity"
    assert len(set(after)) == len(mod.ARMS), "arms must stay distinct"
