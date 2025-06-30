import pytest
import random
from simulation.debuff_system import (
    Debuff,
    DebuffType,
    DebuffManager,
    create_trap_debuff
)

def test_debuff_tick_duration():
    debuff = Debuff(DebuffType.POISONED, duration_remaining=2)
    assert not debuff.tick_duration()  # 1 round left
    assert debuff.duration_remaining == 1
    assert debuff.tick_duration()  # expires
    assert debuff.duration_remaining == 0

def test_stat_modifiers():
    poisoned = Debuff(DebuffType.POISONED, 2)
    cursed = Debuff(DebuffType.CURSED, 2)
    weakened = Debuff(DebuffType.WEAKENED, 2)

    assert poisoned.get_stat_modifier("might") == -2
    assert cursed.get_stat_modifier("luck") == -2
    assert weakened.get_stat_modifier("might") == -2
    assert weakened.get_stat_modifier("luck") == 0

def test_attack_modifiers():
    blinded = Debuff(DebuffType.BLINDED, 2)
    slowed = Debuff(DebuffType.SLOWED, 2)
    assert blinded.get_attack_modifier() == -4
    assert slowed.get_attack_modifier() == -2

def test_confusion_and_stun_flags():
    confused = Debuff(DebuffType.CONFUSED, 1)
    stunned = Debuff(DebuffType.STUNNED, 1)
    assert confused.causes_confusion()
    assert stunned.blocks_actions()

def test_apply_debuff_and_overwrite():
    manager = DebuffManager()
    debuff1 = Debuff(DebuffType.WEAKENED, 2, severity=1)
    debuff2 = Debuff(DebuffType.WEAKENED, 3, severity=2)

    assert manager.apply_debuff(debuff1) is True
    assert manager.has_debuff(DebuffType.WEAKENED)
    assert manager.get_active_debuffs()[0].duration_remaining == 2

    assert manager.apply_debuff(debuff2) is False  # Replacing same type
    assert manager.get_active_debuffs()[0].duration_remaining == 3

def test_tick_all_debuffs_removal():
    manager = DebuffManager()
    manager.apply_debuff(Debuff(DebuffType.STUNNED, 1))
    manager.apply_debuff(Debuff(DebuffType.SLOWED, 2))

    expired = manager.tick_all_debuffs()
    assert len(expired) == 1
    assert expired[0].debuff_type == DebuffType.STUNNED
    assert manager.has_debuff(DebuffType.SLOWED)
    assert not manager.has_debuff(DebuffType.STUNNED)

def test_stat_modifier_total():
    manager = DebuffManager()
    manager.apply_debuff(Debuff(DebuffType.POISONED, 2))  # -2 all
    manager.apply_debuff(Debuff(DebuffType.CURSED, 2))    # -2 luck

    assert manager.get_stat_modifier("might") == -2
    assert manager.get_stat_modifier("luck") == -4  # poison + cursed

def test_attack_modifier_total():
    manager = DebuffManager()
    manager.apply_debuff(Debuff(DebuffType.SLOWED, 2))
    manager.apply_debuff(Debuff(DebuffType.BLINDED, 2))
    assert manager.get_attack_modifier() == -6

def test_poison_damage_tick():
    manager = DebuffManager()
    assert manager.get_poison_damage() == 0
    manager.apply_debuff(Debuff(DebuffType.POISONED, 2, severity=2))
    assert manager.get_poison_damage() == 2
    manager.tick_all_debuffs()
    assert manager.get_poison_damage() == 2
    manager.tick_all_debuffs()
    assert manager.get_poison_damage() == 0

def test_confusion_chance():
    manager = DebuffManager()
    assert manager.get_confusion_chance() == 0.0
    manager.apply_debuff(Debuff(DebuffType.CONFUSED, 2))
    assert manager.get_confusion_chance() == 0.5

def test_clear_all_debuffs():
    manager = DebuffManager()
    manager.apply_debuff(Debuff(DebuffType.SLOWED, 3))
    manager.clear_all_debuffs()
    assert not manager.get_active_debuffs()
    assert manager.get_poison_damage() == 0

def test_frightened_only_applies_vs_enemies():
    manager = DebuffManager()
    manager.apply_debuff(Debuff(DebuffType.FRIGHTENED, 3))
    assert manager.get_stat_modifier("luck", vs_enemies=True) == -2
    assert manager.get_stat_modifier("luck", vs_enemies=False) == 0

def test_create_trap_debuff_deterministic():
    rng = random.Random(42)
    debuff = create_trap_debuff(rng)
    assert isinstance(debuff, Debuff)
    assert debuff.duration_remaining in [1, 2, 3, 4]
    assert debuff.debuff_type in DebuffType
    assert debuff.source == "trap"

