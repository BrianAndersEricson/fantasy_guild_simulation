import pytest
from models.enemy_types import (
    get_enemies_for_floor,
    get_tier_for_floor,
    EnemyTier,
    EnemyType,
    BossModifier,
    BossType,
    TIER_1_ENEMIES,
    TIER_2_ENEMIES,
    TIER_3_ENEMIES,
    TIER_4_ENEMIES,
    TIER_5_ENEMIES,
    ENEMIES_BY_TIER
)


# === get_enemies_for_floor ===

@pytest.mark.parametrize("floor,expected", [
    (1, TIER_1_ENEMIES),
    (2, TIER_1_ENEMIES),
    (3, TIER_2_ENEMIES),
    (4, TIER_2_ENEMIES),
    (5, TIER_3_ENEMIES),
    (6, TIER_3_ENEMIES),
    (7, TIER_4_ENEMIES),
    (8, TIER_4_ENEMIES),
    (9, TIER_5_ENEMIES),
    (10, TIER_5_ENEMIES),
])
def test_get_enemies_for_floor(floor, expected):
    assert get_enemies_for_floor(floor) == expected


# === get_tier_for_floor ===

@pytest.mark.parametrize("floor,expected", [
    (1, EnemyTier.TIER_1),
    (3, EnemyTier.TIER_2),
    (6, EnemyTier.TIER_3),
    (8, EnemyTier.TIER_4),
    (9, EnemyTier.TIER_5),
])
def test_get_tier_for_floor(floor, expected):
    assert get_tier_for_floor(floor) == expected


# === EnemyType formula logic ===

def test_hp_formula_tier_3():
    etype = EnemyType(name="Test", tier=EnemyTier.TIER_3, hp_die=6)
    assert etype.get_hp_formula(5) == "5 × 5 + 1d6"

def test_hp_formula_tier_4_2d4():
    etype = EnemyType(name="Test", tier=EnemyTier.TIER_4, hp_die=4)
    assert etype.get_hp_formula(7) == "7 × 5 + 2d4"

def test_ac_formula_positive_modifier():
    etype = EnemyType(name="Test", tier=EnemyTier.TIER_2, hp_die=4, ac_modifier=2)
    assert etype.get_ac_formula(4) == "10 + 4 + 2"

def test_ac_formula_negative_modifier():
    etype = EnemyType(name="Test", tier=EnemyTier.TIER_4, hp_die=4, ac_modifier=-1)
    assert etype.get_ac_formula(6) == "10 + 3 - 1"

def test_ac_formula_no_modifier():
    etype = EnemyType(name="Test", tier=EnemyTier.TIER_1, hp_die=4, ac_modifier=0)
    assert etype.get_ac_formula(2) == "10 + 2"

def test_damage_formula_regular():
    etype = EnemyType(name="Test", tier=EnemyTier.TIER_3, damage_die=8)
    assert etype.get_damage_formula(5) == "1d8 + 5"

def test_damage_formula_tier_4_special_2d4():
    etype = EnemyType(name="Test", tier=EnemyTier.TIER_4, damage_die=4)
    assert etype.get_damage_formula(8) == "2d4 + 4"

def test_damage_formula_tier_5_non_special():
    etype = EnemyType(name="Test", tier=EnemyTier.TIER_5, damage_die=10)
    assert etype.get_damage_formula(10) == "1d10 + 5"


# === BossModifier application ===

def test_boss_modifier_application():
    etype = EnemyType(name="Goblin", tier=EnemyTier.TIER_2)
    modifier = BossModifier(BossType.RAGE, "gets angry when bloodied")
    mods = modifier.apply_to_enemy(etype)

    assert mods["hp_multiplier"] == 2
    assert mods["ac_bonus"] == 2
    assert mods["might_bonus"] == 2
    assert mods["boss_ability"] == BossType.RAGE
    assert mods["boss_description"] == "gets angry when bloodied"


# === Meta checks for constants ===

def test_enemies_by_tier_valid():
    for tier, enemy_list in ENEMIES_BY_TIER.items():
        assert isinstance(tier, EnemyTier)
        assert isinstance(enemy_list, list)
        assert all(isinstance(e, EnemyType) for e in enemy_list)
        assert len(enemy_list) == 4

