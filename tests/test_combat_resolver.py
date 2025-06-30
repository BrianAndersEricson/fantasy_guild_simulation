import pytest
import random
from unittest.mock import Mock, patch

from models.character import Character, CharacterRole
from models.party import Party
from models.events import EventEmitter, EventType
from models.enemy import Enemy, create_encounter
from models.enemy_types import (
    GIANT_RAT, SKELETON, GHOUL, WRAITH,
    SpecialAbility, BossType, BOSS_MODIFIERS
)
from simulation.combat_resolver import CombatResolver
from simulation.dungeon_generator import Room, RoomType
from simulation.debuff_system import DebuffType, Debuff


@pytest.fixture
def event_emitter():
    return EventEmitter()


@pytest.fixture
def rng():
    return random.Random(12345)


@pytest.fixture
def combat_resolver(event_emitter, rng):
    return CombatResolver(event_emitter, rng)


@pytest.fixture
def test_party():
    members = [
        Character("Aldric", CharacterRole.STRIKER, 1, might=15, grit=12, wit=8, luck=10),
        Character("Lyra", CharacterRole.BURGLAR, 1, might=9, grit=10, wit=11, luck=15),
        Character("Elara", CharacterRole.SUPPORT, 1, might=8, grit=11, wit=15, luck=12),
        Character("Magnus", CharacterRole.CONTROLLER, 1, might=9, grit=10, wit=14, luck=13)
    ]
    return Party(guild_id=1, guild_name="Test Heroes", members=members)


@pytest.fixture
def combat_room():
    return Room(2, 3, RoomType.COMBAT, 2, 3, False)


@pytest.fixture
def boss_room():
    return Room(3, 5, RoomType.BOSS, 3, 3, True)


class TestBossAbilities:
    def test_rage_boss(self, combat_resolver, test_party, rng, event_emitter):
        rage_mod = next(m for m in BOSS_MODIFIERS if m.boss_type == BossType.RAGE)
        boss = Enemy.create_from_type(GHOUL, 3, 1, rng, True, rage_mod)
        boss.current_hp = boss.max_hp // 2 - 1
        event_emitter.clear_events()
        combat_resolver._process_boss_abilities(test_party, [boss])
        assert any(e.event_type == EventType.BOSS_ABILITY_TRIGGERED and 'rage' in e.details['ability'] for e in event_emitter.events)

    def test_regenerate_boss(self, combat_resolver, test_party, rng, event_emitter):
        regen_mod = next(m for m in BOSS_MODIFIERS if m.boss_type == BossType.REGENERATE)
        boss = Enemy.create_from_type(GHOUL, 3, 1, rng, True, regen_mod)
        boss.current_hp = boss.max_hp // 2
        original_hp = boss.current_hp
        event_emitter.clear_events()
        combat_resolver._process_boss_abilities(test_party, [boss])
        assert boss.current_hp > original_hp
        assert any(e.event_type == EventType.CHARACTER_HEALED for e in event_emitter.events)


class TestConfusionMechanic:
    def test_confused_attack_ally(self, combat_resolver, test_party, event_emitter):
        confused_char = test_party.members[0]
        confused_char.debuff_manager.apply_debuff(Debuff(DebuffType.CONFUSED, 2, "test"))
        mock_rng = Mock()
        mock_rng.random.return_value = 0.4
        mock_rng.randint = lambda a, b: 5
        mock_rng.choice = lambda x: x[0]
        combat_resolver.rng = mock_rng
        enemy = Mock()
        enemy.get_effective_ac.return_value = 10
        enemy.take_damage = Mock()
        enemy.name = "Dummy Enemy"
        enemies = [enemy]
        event_emitter.clear_events()
        combat_resolver._party_combat_turn(test_party, enemies, floor_level=1)
        assert any(e.event_type == EventType.ATTACK_HIT and e.details.get('confused') for e in event_emitter.events)


class TestDeathMechanics:
    def test_character_knocked_unconscious(self, combat_resolver, test_party, rng, event_emitter):
        victim = test_party.members[0]
        victim.current_hp = 5
        with patch.object(victim, '_death_test', return_value=True):
            enemy = Enemy.create_from_type(SKELETON, 2, 1, rng, False)
            mock_rng = Mock()
            mock_rng.randint.side_effect = [15, 6]
            mock_rng.choice = rng.choice
            combat_resolver.rng = mock_rng
            event_emitter.clear_events()
            combat_resolver._enemy_combat_turn(test_party, [enemy])
            assert not victim.is_conscious
            assert victim.is_alive
            assert any(e.event_type == EventType.CHARACTER_UNCONSCIOUS for e in event_emitter.events)

    def test_character_death(self, combat_resolver, test_party, rng, event_emitter):
        victim = test_party.members[0]
        victim.current_hp = 5
        with patch.object(victim, '_death_test', return_value=False):
            enemy = Enemy.create_from_type(SKELETON, 2, 1, rng, False)
            mock_rng = Mock()
            mock_rng.randint.side_effect = [15, 6]
            mock_rng.choice = rng.choice
            combat_resolver.rng = mock_rng
            event_emitter.clear_events()
            combat_resolver._enemy_combat_turn(test_party, [enemy])
            assert not victim.is_alive
            assert any(e.event_type == EventType.CHARACTER_DIES for e in event_emitter.events)


class TestIntegration:
    def test_full_combat_with_all_mechanics(self, combat_resolver, test_party, combat_room, event_emitter):
        event_emitter.clear_events()
        result = combat_resolver.resolve_combat(test_party, combat_room)
        event_types = {e.event_type for e in event_emitter.events}
        assert result is True
        assert EventType.COMBAT_START in event_types
        assert EventType.ENEMY_APPEARS in event_types
        assert EventType.COMBAT_END in event_types
        if hasattr(event_emitter, 'current_tick'):
            assert event_emitter.current_tick > 0

