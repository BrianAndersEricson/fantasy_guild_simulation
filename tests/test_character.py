import pytest
import random
from models.character import Character, CharacterRole
from models.spell import get_default_spells_for_role

# Disable randomness for test consistency
random.seed(42)

# === HELPERS ===

def make_char(role=CharacterRole.STRIKER, **kwargs):
    return Character(name="Test", role=role, guild_id=1, **kwargs)


# === INIT AND ATTRIBUTES ===

def test_character_initialization_hp_and_spells():
    char = make_char(grit=9, wit=9)
    assert char.max_hp >= 10  # base grit + 1dX
    assert char.current_hp == char.max_hp
    assert not char.can_cast_spells()

    caster = make_char(role=CharacterRole.SUPPORT, wit=9)
    assert caster.can_cast_spells()
    assert set(get_default_spells_for_role("support")) <= set(caster.known_spells)


def test_stat_modifiers():
    char = make_char(might=9, grit=6, wit=3, luck=12)
    assert char.get_might_modifier() == 3
    assert char.get_grit_modifier() == 2
    assert char.get_wit_modifier() == 1
    assert char.get_luck_modifier() == 4

    assert char.get_stat_modifier("might") == 3
    assert char.get_stat_modifier("unknown") == 0
    assert char.get_stat("grit") == 6


# === DAMAGE AND HEALING ===

def test_take_damage_and_death_test(monkeypatch):
    char = make_char(grit=5)
    char.current_hp = 10

    monkeypatch.setattr("random.randint", lambda a, b: 5)  # always fail

    was_downed = char.take_damage(15)
    assert was_downed
    assert not char.is_alive


def test_take_damage_down_but_survive(monkeypatch):
    char = make_char(grit=5)
    char.current_hp = 10

    monkeypatch.setattr("random.randint", lambda a, b: 15)  # always pass

    was_downed = char.take_damage(15)
    assert was_downed
    assert char.is_alive
    assert not char.is_conscious


def test_heal_logic_resurrects_conscious():
    char = make_char(grit=5)
    char.current_hp = 0
    char.is_conscious = False
    char.is_alive = True
    healed = char.heal(5)
    assert healed == 5
    assert char.is_conscious


def test_heal_does_not_revive_dead():
    char = make_char(grit=5)
    char.is_alive = False
    healed = char.heal(10)
    assert healed == 0


def test_cannot_overheal():
    char = make_char(grit=10)
    char.current_hp = char.max_hp - 2
    healed = char.heal(5)
    assert healed == 2
    assert char.current_hp == char.max_hp


# === SPELLS AND STATUS ===

def test_disable_spell_and_reset():
    char = make_char(role=CharacterRole.SUPPORT, wit=9)
    test_spell = char.known_spells[0]
    char.disable_spell(test_spell)
    assert test_spell in char.disabled_spells

    char.reset_for_expedition()
    assert char.is_conscious
    assert char.current_hp == char.max_hp
    assert test_spell in char.disabled_spells  # not recovered


def test_get_available_spells():
    char = make_char(role=CharacterRole.CONTROLLER, wit=9)
    assert char.can_cast_spells()
    available_spells = char.get_available_spells()
    assert all(spell not in char.disabled_spells for spell in available_spells)

    if available_spells:
        char.disable_spell(available_spells[0])
        new_available = char.get_available_spells()
        assert available_spells[0] not in new_available


def test_spell_summary_string():
    char = make_char(role=CharacterRole.SUPPORT, wit=9)
    summary = char.get_spell_summary()
    assert f"{len(char.known_spells)}" in summary

    noncaster = make_char(role=CharacterRole.BURGLAR)
    assert noncaster.get_spell_summary() == "No spells"


# === AC AND STRING ===

def test_get_ac_and_str_display():
    char = make_char(grit=9)
    ac = char.get_ac()
    assert ac == 13  # 10 + grit modifier
    s = str(char)
    assert char.name in s
    assert f"HP:{char.current_hp}" in s

