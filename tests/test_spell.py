import pytest
import random
from models.spell import (
    ALL_SPELLS,
    SUPPORT_SPELLS,
    CONTROLLER_SPELLS,
    get_default_spells_for_role,
    generate_random_spells_for_role,
    SpellType,
    TargetType,
)


class DummyCharacter:
    """Simple mock object to simulate a character with stats."""
    def __init__(self, name, role, wit, grit, luck):
        self.name = name
        self.role = role
        self.wit = wit
        self.grit = grit
        self.luck = luck


@pytest.fixture
def rng():
    return random.Random(1234)


def test_get_default_spells_for_roles():
    assert get_default_spells_for_role("controller") == ["Psychic Lance"]
    assert get_default_spells_for_role("support") == ["Mend Wounds"]
    assert get_default_spells_for_role("striker") == []
    assert get_default_spells_for_role("BURGLAR") == []


def test_generate_random_spells_controller(rng):
    controller_spells = generate_random_spells_for_role("controller", 3, rng)
    assert len(controller_spells) == 3
    assert "Psychic Lance" not in controller_spells


def test_generate_random_spells_support(rng):
    support_spells = generate_random_spells_for_role("support", 3, rng)
    assert len(support_spells) == 3
    assert "Mend Wounds" not in support_spells


def test_spell_metadata_validity():
    for spell in ALL_SPELLS:
        assert isinstance(spell.name, str)
        assert isinstance(spell.base_dc, int)
        assert spell.base_dc >= 0
        assert isinstance(spell.target_type, TargetType)


def test_support_stat_dependencies():
    for spell in SUPPORT_SPELLS:
        assert spell.primary_stat == "wit"
        assert spell.secondary_stat == "grit"
        assert spell.spell_type in {
            SpellType.SUPPORT_HEAL,
            SpellType.SUPPORT_CURE,
            SpellType.SUPPORT_BUFF,
        }


def test_controller_stat_dependencies():
    for spell in CONTROLLER_SPELLS:
        assert spell.primary_stat == "wit"
        assert spell.secondary_stat == "luck"
        assert spell.spell_type in {
            SpellType.CONTROLLER_DAMAGE,
            SpellType.CONTROLLER_DEBUFF,
        }

