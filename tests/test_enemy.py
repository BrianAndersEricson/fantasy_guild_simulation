import pytest
import random
from models.enemy import Enemy, create_encounter
from models.enemy_types import (
    EnemyType, EnemyTier, SpecialAbility, BossModifier, BOSS_MODIFIERS, get_enemies_for_floor
)

@pytest.fixture
def rng():
    return random.Random(42)

@pytest.fixture
def base_enemy_type():
    # A tier 1 dummy enemy type for basic tests
    return EnemyType(
        name="Test Slime",
        description="A blob of goo",
        tier=EnemyTier.TIER_1,
        hp_die=4,
        ac_modifier=0,
        damage_die=4,
        special_ability=SpecialAbility.NONE,
        special_trigger=5
    )

def test_create_enemy_basic(base_enemy_type, rng):
    enemy = Enemy.create_from_type(base_enemy_type, floor=1, enemy_number=1, rng=rng)
    assert enemy.name == "Test Slime 1"
    assert enemy.max_hp > 0
    assert enemy.ac >= 10
    assert enemy.is_boss is False
    assert enemy.enemy_type.name == "Test Slime"

def test_enemy_take_damage_and_heal(base_enemy_type, rng):
    enemy = Enemy.create_from_type(base_enemy_type, 1, 1, rng)
    full_hp = enemy.current_hp
    assert enemy.is_alive()

    killed = enemy.take_damage(full_hp - 1)
    assert killed is False
    assert enemy.is_alive()

    killed = enemy.take_damage(1)
    assert killed is True
    assert not enemy.is_alive()

    healed = enemy.heal(5)
    assert healed == 0  # Can't heal if dead

def test_enemy_healing_partial(base_enemy_type, rng):
    enemy = Enemy.create_from_type(base_enemy_type, 1, 1, rng)
    enemy.take_damage(3)
    healed = enemy.heal(2)
    assert healed == 2
    assert enemy.current_hp == enemy.max_hp - 1

def test_enemy_is_bloodied(base_enemy_type, rng):
    enemy = Enemy.create_from_type(base_enemy_type, 1, 1, rng)
    enemy.take_damage(enemy.max_hp // 2 + 1)
    assert enemy.is_bloodied()

def test_status_effects_add_and_tick(base_enemy_type, rng):
    enemy = Enemy.create_from_type(base_enemy_type, 1, 1, rng)
    enemy.add_status_effect(SpecialAbility.BLIND, 2)
    assert enemy.has_status_effect(SpecialAbility.BLIND)

    enemy.tick_status_effects()
    assert enemy.has_status_effect(SpecialAbility.BLIND)

    enemy.tick_status_effects()
    assert not enemy.has_status_effect(SpecialAbility.BLIND)

def test_effective_ac_and_might_modifiers(base_enemy_type, rng):
    enemy = Enemy.create_from_type(base_enemy_type, 1, 1, rng)
    base_ac = enemy.ac
    base_might = enemy.might

    # Apply blindness and weaken
    enemy.add_status_effect(SpecialAbility.BLIND, 2)
    enemy.add_status_effect(SpecialAbility.WEAKEN, 2)

    assert enemy.get_effective_ac() == base_ac - 2
    assert enemy.get_effective_might() == max(0, base_might - 2)

def test_boss_modifier_application(rng):
    floor = 3
    boss_mod = BOSS_MODIFIERS[0]  # Any valid modifier
    enemy_type = random.choice(get_enemies_for_floor(floor))

    boss = Enemy.create_from_type(
        enemy_type=enemy_type,
        floor=floor,
        enemy_number=1,
        rng=rng,
        is_boss=True,
        boss_modifier=boss_mod
    )

    assert boss.is_boss
    assert boss.boss_ability == boss_mod.boss_type
    assert boss.name.startswith(boss_mod.boss_type.value.title())

def test_create_encounter_regular(rng):
    encounter = create_encounter(floor=1, enemy_count=3, is_boss_room=False, rng=rng)
    assert len(encounter) == 3
    assert all(not e.is_boss for e in encounter)

def test_create_encounter_boss(rng):
    encounter = create_encounter(floor=5, enemy_count=3, is_boss_room=True, rng=rng)
    assert len(encounter) == 3
    boss = encounter[0]
    minions = encounter[1:]

    assert boss.is_boss
    assert boss.boss_ability is not None
    assert all(not m.is_boss for m in minions)

