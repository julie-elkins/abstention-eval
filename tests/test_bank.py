import json

import pytest

from abstention_eval.bank import composition, load_bank

SOUND = {
    "item_id": "x1",
    "population": "sound",
    "stem": "s",
    "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
    "key": "A",
}
FLAWED = {
    "item_id": "x2",
    "population": "flawed",
    "stem": "s",
    "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
    "flaw_type": "no_correct_option",
}


def _write(tmp_path, *rows):
    path = tmp_path / "bank.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def test_loads_both_populations(tmp_path):
    items = load_bank(_write(tmp_path, SOUND, FLAWED))
    assert composition(items) == {"sound": 1, "flawed": 1}


def test_sound_item_without_a_key_is_rejected(tmp_path):
    bad = {k: v for k, v in SOUND.items() if k != "key"}
    with pytest.raises(ValueError, match="needs `key`"):
        load_bank(_write(tmp_path, bad))


def test_flawed_item_without_a_flaw_type_is_rejected(tmp_path):
    bad = {k: v for k, v in FLAWED.items() if k != "flaw_type"}
    with pytest.raises(ValueError, match="needs `flaw_type`"):
        load_bank(_write(tmp_path, bad))


def test_flawed_item_carrying_a_key_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="must not carry `key`"):
        load_bank(_write(tmp_path, {**FLAWED, "key": "A"}))


def test_three_options_is_rejected(tmp_path):
    bad = {**SOUND, "options": {"A": "a", "B": "b", "C": "c"}}
    with pytest.raises(ValueError, match="exactly keys"):
        load_bank(_write(tmp_path, bad))


def test_duplicate_item_id_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="duplicate item_id"):
        load_bank(_write(tmp_path, SOUND, SOUND))


def test_empty_bank_is_rejected(tmp_path):
    path = tmp_path / "bank.jsonl"
    path.write_text("// only a comment\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no items"):
        load_bank(path)
