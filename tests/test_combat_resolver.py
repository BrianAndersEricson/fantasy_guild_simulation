"""
Test suite for the enhanced Combat Resolver with enemy types and debuffs.

Tests all combat mechanics including:
- Enemy creation and tiered system
- Character attacks with modifiers
- Enemy special abilities and debuffs
- Boss mechanics
- Spell casting
- Status effect processing
- Death mechanics
"""

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
    """Create an event emitter for testing"""
    return EventEmitter()


@pytest.fixture
def rng():
    """Create a seeded RNG for predictable tests"""
    return random.Random(12345)


@pytest.fixture
def combat_resolver(event_emitter, rng):
    """Create a combat resolver instance"""
    return CombatResolver(event_emitter, rng)


@pytest.fixture
def test_party():
    """Create a test party with all roles"""
    members = [
        Character("Aldric", CharacterRole.STRIKER, 1, might=15, grit=12, wit=8, luck=10),
        Character("Lyra", CharacterRole.BURGLAR, 1, might=9, grit=10, wit=11, luck=15),
        Character("Elara", CharacterRole.SUPPORT, 1, might=8, grit=11, wit=15, luck=12),
        Character("Magnus", CharacterRole.CONTROLLER, 1, might=9, grit=10, wit=14, luck=13)
    ]
    
    return Party(
        guild_id=1,
        guild_name="Test Heroes",
        members=members
    )


@pytest.fixture
def combat_room():
    """Create a standard combat room"""
    return Room(
        floor_number=2,
        room_number=3,
        room_type=RoomType.COMBAT,
        difficulty_level=2,
        enemy_count=3,
        is_boss_room=False
    )


@pytest.fixture
def boss_room():
    """Create a boss room"""
    return Room(
        floor_number=3,
        room_number=5,
        room_type=RoomType.BOSS,
        difficulty_level=3,
        enemy_count=3,
        is_boss_room=True
    )


class TestEnemyCreation:
    """Test enemy creation and tiered system"""
    
    def test_basic_enemy_creation(self, rng):
        """Test creating enemies for different floors"""
        # Floor 1 - should get tier 1 enemies
        enemies = create_encounter(
            floor=1,
            enemy_count=3,
            is_boss_room=False,
            rng=rng
        )
        
        assert len(enemies) == 3
        assert all(e.enemy_type.tier.value == 1 for e in enemies)
        assert all(e.max_hp > 0 for e in enemies)
        assert all(e.ac > 0 for e in enemies)
    
    def test_boss_creation(self, rng):
        """Test boss enemy creation"""
        enemies = create_encounter(
            floor=3,
            enemy_count=3,
            is_boss_room=True,
            rng=rng
        )
        
        bosses = [e for e in enemies if e.is_boss]
        minions = [e for e in enemies if not e.is_boss]
        
        assert len(bosses) == 1
        assert len(minions) == 2
        assert bosses[0].boss_ability is not None
        assert bosses[0].max_hp > minions[0].max_hp if minions else True
    
    def test_enemy_tier_progression(self, rng):
        """Test that enemies get harder on deeper floors"""
        floor1_enemies = create_encounter(1, 1, False, rng)
        floor5_enemies = create_encounter(5, 1, False, rng)
        floor9_enemies = create_encounter(9, 1, False, rng)
        
        # Higher tier enemies on deeper floors
        assert floor1_enemies[0].enemy_type.tier.value < floor5_enemies[0].enemy_type.tier.value
        assert floor5_enemies[0].enemy_type.tier.value < floor9_enemies[0].enemy_type.tier.value
        
        # More HP and AC on deeper floors
        assert floor1_enemies[0].max_hp < floor5_enemies[0].max_hp
        assert floor5_enemies[0].max_hp < floor9_enemies[0].max_hp


class TestCombatFlow:
    """Test the overall combat flow"""
    
    def test_basic_combat_resolution(self, combat_resolver, test_party, combat_room, event_emitter):
        """Test a complete combat encounter"""
        # Clear events
        event_emitter.clear_events()
        
        # Run combat
        result = combat_resolver.resolve_combat(test_party, combat_room)
        
        # Check events were generated
        events = event_emitter.events
        assert any(e.event_type == EventType.COMBAT_START for e in events)
        assert any(e.event_type == EventType.ENEMY_APPEARS for e in events)
        assert any(e.event_type == EventType.COMBAT_END for e in events)
        
        # Check party survived (with seeded RNG they should win)
        assert result is True
        
        # Check enemies were defeated
        enemy_defeated_events = [e for e in events if e.event_type == EventType.ENEMY_DEFEATED]
        assert len(enemy_defeated_events) == combat_room.enemy_count
    
    def test_party_wipe(self, combat_resolver, test_party, boss_room, event_emitter):
        """Test party getting wiped out"""
        # Weaken the party severely
        for member in test_party.members:
            member.current_hp = 1
        
        # Clear events
        event_emitter.clear_events()
        
        # Run combat against boss
        result = combat_resolver.resolve_combat(test_party, boss_room)
        
        # Party should be wiped
        assert result is False
        
        # Check for wipe event
        events = event_emitter.events
        combat_end_events = [e for e in events if e.event_type == EventType.COMBAT_END]
        assert any('wiped out' in e.description for e in combat_end_events)


class TestCharacterAttacks:
    """Test character attack mechanics"""
    
    def test_normal_attack(self, combat_resolver, test_party, rng):
        """Test normal character attack"""
        attacker = test_party.members[0]  # Striker
        
        # Create a single enemy
        enemy = Enemy.create_from_type(
            enemy_type=GIANT_RAT,
            floor=1,
            enemy_number=1,
            rng=rng,
            is_boss=False
        )
        enemies = [enemy]
        
        # Clear events
        combat_resolver.event_emitter.clear_events()
        
        # Perform attack
        combat_resolver._character_attack(test_party, attacker, enemies)
        
        # Check that an attack event was generated
        events = combat_resolver.event_emitter.events
        assert len(events) == 1
        assert events[0].event_type in [EventType.ATTACK_HIT, EventType.ATTACK_MISS, EventType.ATTACK_CRITICAL]
    
    def test_critical_hit(self, combat_resolver, test_party):
        attacker = test_party.members[0]
        
        enemy = Mock()
        enemy.name = "Test Enemy"
        enemy.get_effective_ac.return_value = 10
        enemy.take_damage = Mock()
        enemies = [enemy]
        
        mock_rng = Mock()
        mock_rng.randint.return_value = 20
        mock_rng.choice.return_value = enemy
        combat_resolver.rng = mock_rng
        
        combat_resolver.event_emitter.clear_events()
        combat_resolver._character_attack(test_party, attacker, enemies)
        
        events = combat_resolver.event_emitter.events
        assert events[0].event_type == EventType.ATTACK_CRITICAL
        enemy.take_damage.assert_called_once()
        
    def test_attack_with_debuffs(self, combat_resolver, test_party, rng):
        """Test attacks with debuff modifiers"""
        attacker = test_party.members[0]
        
        # Apply weakness debuff
        weakness = Debuff(DebuffType.WEAKENED, 2, source="test")
        attacker.debuff_manager.apply_debuff(weakness)
        
        # Apply blindness debuff
        blindness = Debuff(DebuffType.BLINDED, 2, source="test")
        attacker.debuff_manager.apply_debuff(blindness)
        
        # Create enemy
        enemy = Enemy.create_from_type(GIANT_RAT, 1, 1, rng, False)
        enemies = [enemy]
        
        # Clear events
        combat_resolver.event_emitter.clear_events()
        
        # Perform attack - should have penalties
        combat_resolver._character_attack(test_party, attacker, enemies)
        
        # Attack should have reduced chance to hit due to blindness
        events = combat_resolver.event_emitter.events
        assert len(events) == 1


class TestEnemyAttacks:
    """Test enemy attack mechanics and special abilities"""
    
    def test_enemy_basic_attack(self, combat_resolver, test_party, rng):
        """Test basic enemy attack"""
        # Create enemy
        enemy = Enemy.create_from_type(SKELETON, 2, 1, rng, False)
        enemies = [enemy]
        
        # Clear events
        combat_resolver.event_emitter.clear_events()
        
        # Enemy attacks
        combat_resolver._enemy_combat_turn(test_party, enemies)
        
        # Check attack event
        events = combat_resolver.event_emitter.events
        assert len(events) >= 1
        assert events[0].event_type in [EventType.ATTACK_HIT, EventType.ATTACK_MISS]
    
    def test_enemy_special_ability_trigger(self, combat_resolver, test_party, rng):
        """Test enemy special ability application"""
        # Create enemy with poison ability
        poison_enemy = Enemy.create_from_type(GIANT_RAT, 1, 1, rng, False)
        
        # Get a target
        target = test_party.members[0]
        target.debuff_manager.clear_all_debuffs()
        
        # Mock RNG to force ability trigger
        mock_rng = Mock()
        mock_rng.randint.side_effect = [4, 3]  # First roll triggers ability, second sets duration
        combat_resolver.rng = mock_rng
        
        # Clear events
        combat_resolver.event_emitter.clear_events()
        
        # Apply ability
        combat_resolver._apply_enemy_special_ability(test_party, poison_enemy, target)
        
        # Check debuff was applied
        assert target.debuff_manager.has_debuff(DebuffType.POISONED)
        
        # Check event
        events = combat_resolver.event_emitter.events
        assert len(events) == 1
        assert events[0].event_type == EventType.DEBUFF_APPLIED
        assert 'poisoned' in events[0].description
    
    def test_boss_aura_bonus(self, combat_resolver, test_party, rng):
        """Test boss aura affects all enemies"""
        # Create boss with aura and minions
        boss_mod = next(m for m in BOSS_MODIFIERS if m.boss_type == BossType.AURA)
        boss = Enemy.create_from_type(GHOUL, 3, 1, rng, True, boss_mod)
        minion = Enemy.create_from_type(GHOUL, 3, 2, rng, False)
        enemies = [boss, minion]
        
        # Mock attacks to always hit
        mock_rng = Mock()
        mock_rng.randint.return_value = 15
        mock_rng.choice = rng.choice
        combat_resolver.rng = mock_rng
        
        # Clear events
        combat_resolver.event_emitter.clear_events()
        
        # Enemies attack
        combat_resolver._enemy_combat_turn(test_party, enemies)
        
        # Both enemies should have attacked
        attack_events = [e for e in combat_resolver.event_emitter.events 
                        if e.event_type == EventType.ATTACK_HIT]
        assert len(attack_events) == 2


class TestSpellCasting:
    """Test spell casting mechanics"""
    
    def test_basic_spell_cast(self, combat_resolver, test_party, rng):
        """Test successful spell cast"""
        caster = test_party.members[2]  # Support
        
        # Create enemy
        enemy = Enemy.create_from_type(GIANT_RAT, 1, 1, rng, False)
        enemies = [enemy]
        
        # Clear events
        combat_resolver.event_emitter.clear_events()
        
        # Cast spell
        combat_resolver._character_cast_spell(test_party, caster, enemies)
        
        # Should cast harm spell (no one injured)
        events = combat_resolver.event_emitter.events
        assert any(e.event_type in [EventType.SPELL_CAST, EventType.SPELL_FAIL] 
                  for e in events)
    
    def test_heal_spell_priority(self, combat_resolver, test_party, rng):
        """Test that heal is prioritized when allies are injured"""
        caster = test_party.members[2]  # Support
        
        # Injure an ally
        test_party.members[0].current_hp = 5
        
        # Create enemy
        enemy = Enemy.create_from_type(GIANT_RAT, 1, 1, rng, False)
        enemies = [enemy]
        
        # Mock successful spell
        mock_rng = Mock()
        mock_rng.randint.return_value = 15
        mock_rng.choice = rng.choice
        combat_resolver.rng = mock_rng
        
        # Clear events
        combat_resolver.event_emitter.clear_events()
        
        # Cast spell
        combat_resolver._character_cast_spell(test_party, caster, enemies)
        
        # Should have healed
        events = combat_resolver.event_emitter.events
        heal_events = [e for e in events if e.event_type == EventType.CHARACTER_HEALED]
        assert len(heal_events) > 0
    
    def test_critical_spell_failure(self, combat_resolver, test_party, rng):
        """Test critical spell failure disables spell"""
        caster = test_party.members[2]  # Support
        
        # Create enemy
        enemy = Enemy.create_from_type(GIANT_RAT, 1, 1, rng, False)
        enemies = [enemy]
        
        # Mock critical failure
        mock_rng = Mock()
        mock_rng.randint.return_value = 1
        mock_rng.choice = rng.choice
        combat_resolver.rng = mock_rng
        
        # Clear events and disabled spells
        combat_resolver.event_emitter.clear_events()
        caster.disabled_spells.clear()
        
        # Cast spell
        combat_resolver._character_cast_spell(test_party, caster, enemies)
        
        # Check spell was disabled
        assert len(caster.disabled_spells) == 1
        
        # Check event
        events = combat_resolver.event_emitter.events
        assert any(e.event_type == EventType.SPELL_FAIL and e.details.get('disabled') 
                  for e in events)


class TestStatusEffects:
    """Test status effect processing"""
    
    def test_poison_damage(self, combat_resolver, test_party, event_emitter):
        """Test poison damage over time"""
        victim = test_party.members[0]
        
        # Apply poison
        poison = Debuff(DebuffType.POISONED, 3, source="test")
        victim.debuff_manager.apply_debuff(poison)
        
        # Clear events
        event_emitter.clear_events()
        
        # Process status effects
        combat_resolver._process_status_effects(test_party, [])
        
        # Check poison damage event
        events = event_emitter.events
        poison_events = [e for e in events if e.event_type == EventType.STATUS_DAMAGE]
        assert len(poison_events) == 1
        assert poison_events[0].details['source'] == 'poison'
    
    def test_debuff_expiration(self, combat_resolver, test_party, event_emitter):
        """Test debuff expiration events"""
        victim = test_party.members[0]
        
        # Apply short duration debuff
        stun = Debuff(DebuffType.STUNNED, 1, source="test")
        victim.debuff_manager.apply_debuff(stun)
        
        # Clear events
        event_emitter.clear_events()
        
        # Process status effects - should expire
        combat_resolver._process_status_effects(test_party, [])
        
        # Check expiration event
        events = event_emitter.events
        expire_events = [e for e in events if e.event_type == EventType.DEBUFF_EXPIRED]
        assert len(expire_events) == 1
        assert 'stunned' in expire_events[0].description
    
    def test_stunned_character_cannot_act(self, combat_resolver, test_party, event_emitter):
        """Test stunned characters skip their turn"""
        stunned_char = test_party.members[0]
        
        # Apply stun
        stun = Debuff(DebuffType.STUNNED, 2, source="test")
        stunned_char.debuff_manager.apply_debuff(stun)
        
        # Create enemy
        enemy = Mock()
        enemies = [enemy]
        
        # Clear events
        event_emitter.clear_events()
        
        # Process party turn
        combat_resolver._party_combat_turn(test_party, enemies)
        
        # Check stun message
        stun_events = [e for e in event_emitter.events 
                      if 'stunned' in e.description and e.details.get('character') == stunned_char.name]
        assert len(stun_events) == 1


class TestBossAbilities:
    """Test boss special abilities"""
    
    def test_rage_boss(self, combat_resolver, test_party, rng, event_emitter):
        """Test rage boss gets damage bonus when bloodied"""
        # Create rage boss
        rage_mod = next(m for m in BOSS_MODIFIERS if m.boss_type == BossType.RAGE)
        boss = Enemy.create_from_type(GHOUL, 3, 1, rng, True, rage_mod)
        
        # Damage boss to bloodied
        boss.current_hp = boss.max_hp // 2 - 1
        
        # Clear events
        event_emitter.clear_events()
        
        # Process boss abilities
        combat_resolver._process_boss_abilities(test_party, [boss])
        
        # Check rage announcement
        events = event_emitter.events
        rage_events = [e for e in events if e.event_type == EventType.BOSS_ABILITY_TRIGGERED]
        assert len(rage_events) == 1
        assert 'rage' in rage_events[0].details['ability']
    
    def test_regenerate_boss(self, combat_resolver, test_party, rng, event_emitter):
        """Test regenerating boss heals each round"""
        # Create regenerate boss
        regen_mod = next(m for m in BOSS_MODIFIERS if m.boss_type == BossType.REGENERATE)
        boss = Enemy.create_from_type(GHOUL, 3, 1, rng, True, regen_mod)
        
        # Damage boss
        boss.current_hp = boss.max_hp // 2
        original_hp = boss.current_hp
        
        # Clear events
        event_emitter.clear_events()
        
        # Process boss abilities
        combat_resolver._process_boss_abilities(test_party, [boss])
        
        # Check healing
        assert boss.current_hp > original_hp
        
        # Check heal event
        events = event_emitter.events
        heal_events = [e for e in events if e.event_type == EventType.CHARACTER_HEALED]
        assert len(heal_events) == 1


class TestConfusionMechanic:
    """Test confusion causing friendly fire"""
    
    def test_confused_attack_ally(self, combat_resolver, test_party, event_emitter):
        confused_char = test_party.members[0]

        # Apply confusion
        confusion = Debuff(DebuffType.CONFUSED, 2, source="test")
        confused_char.debuff_manager.apply_debuff(confusion)

        # Mock RNG to force confusion trigger
        mock_rng = Mock()
        mock_rng.random.return_value = 0.4  # Triggers confusion
        mock_rng.randint = lambda a, b: 5   # Damage roll
        mock_rng.choice = lambda x: x[0]    # Pick first ally/enemy
        combat_resolver.rng = mock_rng

        # Create valid enemy mock
        enemy = Mock()
        enemy.get_effective_ac.return_value = 10
        enemy.take_damage = Mock()
        enemy.name = "Dummy Enemy"
        enemies = [enemy]

        event_emitter.clear_events()
        combat_resolver._party_combat_turn(test_party, enemies)

        # Check for confusion event
        events = event_emitter.events
        confusion_attacks = [e for e in events
                             if e.event_type == EventType.ATTACK_HIT and e.details.get('confused')]
        assert len(confusion_attacks) == 1
        assert 'CONFUSION!' in confusion_attacks[0].description
            
class TestDeathMechanics:
    """Test character death and unconsciousness"""
    
    def test_character_knocked_unconscious(self, combat_resolver, test_party, rng, event_emitter):
        """Test character being knocked unconscious"""
        victim = test_party.members[0]
        
        # Set up character to be downed but survive death test
        victim.current_hp = 5
        
        # Mock death test to succeed
        with patch.object(victim, '_death_test', return_value=True):
            # Create enemy
            enemy = Enemy.create_from_type(SKELETON, 2, 1, rng, False)
            
            # Mock attack to hit hard
            mock_rng = Mock()
            mock_rng.randint.side_effect = [15, 6]  # Hit roll, damage roll
            mock_rng.choice = rng.choice
            combat_resolver.rng = mock_rng
            
            # Clear events
            event_emitter.clear_events()
            
            # Enemy attacks
            combat_resolver._enemy_combat_turn(test_party, [enemy])
            
            # Check unconscious event
            events = event_emitter.events
            unconscious_events = [e for e in events if e.event_type == EventType.CHARACTER_UNCONSCIOUS]
            assert len(unconscious_events) == 1
            assert victim.is_conscious is False
            assert victim.is_alive is True
    
    def test_character_death(self, combat_resolver, test_party, rng, event_emitter):
        """Test character permanent death"""
        victim = test_party.members[0]
        
        # Set up character to be downed and fail death test
        victim.current_hp = 5
        
        # Mock death test to fail
        with patch.object(victim, '_death_test', return_value=False):
            # Create enemy
            enemy = Enemy.create_from_type(SKELETON, 2, 1, rng, False)
            
            # Mock attack to hit hard
            mock_rng = Mock()
            mock_rng.randint.side_effect = [15, 6]  # Hit roll, damage roll
            mock_rng.choice = rng.choice
            combat_resolver.rng = mock_rng
            
            # Clear events
            event_emitter.clear_events()
            
            # Enemy attacks
            combat_resolver._enemy_combat_turn(test_party, [enemy])
            
            # Check death event
            events = event_emitter.events
            death_events = [e for e in events if e.event_type == EventType.CHARACTER_DIES]
            assert len(death_events) == 1
            assert victim.is_alive is False


class TestIntegration:
    """Integration tests for full combat scenarios"""
    
    def test_full_combat_with_all_mechanics(self, combat_resolver, test_party, combat_room, event_emitter):
        """Test a complete combat with various mechanics"""
        # Clear events
        event_emitter.clear_events()
        
        # Run combat
        result = combat_resolver.resolve_combat(test_party, combat_room)
        
        # Collect event types
        event_types = {e.event_type for e in event_emitter.events}
        
        # Should have various event types
        assert EventType.COMBAT_START in event_types
        assert EventType.ENEMY_APPEARS in event_types
        assert EventType.ATTACK_HIT in event_types or EventType.ATTACK_MISS in event_types
        assert EventType.COMBAT_END in event_types
        
        # Check tick increments (if tick support is enabled)
        if hasattr(event_emitter, 'current_tick'):
            assert event_emitter.current_tick > 0
