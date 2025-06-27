import pytest
from models.events import EventEmitter, EventType

@pytest.fixture
def emitter():
    return EventEmitter()

def test_basic_event_creation(emitter):
    emitter.expedition_start(1, "Brave Companions", {'party_size': 4, 'seed': 12345})
    assert any(e.event_type == EventType.EXPEDITION_START for e in emitter.events)

def test_enemy_specific_events(emitter):
    emitter.combat_start(1, "Brave Companions", 3, is_boss=False)
    emitter.enemy_appears(1, "Brave Companions", "Giant Rat 1", "A rat the size of a small dog")
    emitter.enemy_appears(1, "Brave Companions", "Giant Rat 2", "A rat the size of a small dog")
    emitter.enemy_appears(1, "Brave Companions", "Slime 1", "A translucent blob of acidic goo")

    events = emitter.get_enemy_events()
    assert len(events) == 3

def test_combat_with_debuffs(emitter):
    emitter.increment_tick()
    emitter.character_attack(1, "Brave Companions", "Aldric", 8, critical=False)
    emitter.enemy_defeated(1, "Brave Companions", "Giant Rat 1")
    emitter.increment_tick()
    emitter.emit(1, "Brave Companions", EventType.ATTACK_HIT,
                 "Slime 1 hits Aldric for 5 damage!",
                 details={'attacker': 'Slime 1', 'target': 'Aldric', 'damage': 5, 'enemy': True})
    emitter.debuff_applied(1, "Brave Companions", "Aldric", "slowed", "Slime 1", 3)

    assert any(e.event_type == EventType.DEBUFF_APPLIED for e in emitter.events)

def test_boss_abilities(emitter):
    emitter.increment_tick()
    emitter.combat_start(1, "Brave Companions", 3, is_boss=True)
    emitter.enemy_appears(1, "Brave Companions", "Rage Giant Rat", "Boss: A massive rat with glowing eyes", is_boss=True)
    emitter.boss_ability_triggered(1, "Brave Companions", "Rage Giant Rat", "rage", "becomes enraged as its health drops!")

    boss_events = [e for e in emitter.events if e.event_type == EventType.BOSS_ABILITY_TRIGGERED]
    assert len(boss_events) == 1

def test_status_effects(emitter):
    emitter.increment_tick()
    emitter.status_damage(1, "Brave Companions", "Aldric", 1, "poison")
    emitter.debuff_expired(1, "Brave Companions", "Aldric", "slowed")

    events = emitter.get_status_effect_events()
    assert any(e.event_type == EventType.STATUS_DAMAGE for e in events)
    assert any(e.event_type == EventType.DEBUFF_EXPIRED for e in events)

def test_character_death(emitter):
    emitter.increment_tick()
    emitter.character_unconscious(1, "Brave Companions", "Theron")
    emitter.character_death_test(1, "Brave Companions", "Theron", [8, 15, 12], True)

    types = [e.event_type for e in emitter.events]
    assert EventType.CHARACTER_UNCONSCIOUS in types
    assert EventType.CHARACTER_DEATH_TEST in types

def test_event_filtering(emitter):
    emitter.enemy_appears(1, "Brave Companions", "Slime", "gooey")
    emitter.status_damage(1, "Brave Companions", "Aldric", 3, "poison")

    assert len(emitter.get_enemy_events()) == 1
    assert len(emitter.get_status_effect_events()) == 1

def test_event_summary(emitter):
    emitter.combat_start(1, "Brave Companions", 2, is_boss=False)
    emitter.character_attack(1, "Brave Companions", "Aldric", 7)
    emitter.enemy_defeated(1, "Brave Companions", "Slime")

    summary = emitter.get_event_summary()
    assert summary.get("combat_start") == 1
    assert summary.get("attack_hit") == 1
    assert summary.get("enemy_defeated") == 1

