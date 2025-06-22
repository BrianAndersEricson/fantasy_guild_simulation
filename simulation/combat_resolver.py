"""
Combat Resolver for Fantasy Guild Manager simulation.

This module handles turn-based combat between parties and enemies.
Phase 1 focuses on core mechanics: attacks, basic spells, and death tests.
Future phases will add enemy variety, debuffs, and special abilities.
"""

import random
import sys
import os
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple

# Add the project root to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.character import Character, CharacterRole
from models.party import Party
from models.events import EventEmitter, EventType
from simulation.dungeon_generator import Room, RoomType


@dataclass
class Enemy:
    """
    Represents an enemy in combat.
    
    Phase 1: Basic enemy with HP, AC, and attack capabilities.
    Future phases will add special abilities and enemy types.
    """
    name: str
    max_hp: int
    current_hp: int
    ac: int              # Armor Class (defense)
    might: int           # Attack bonus
    damage_die: int      # d4, d6, d8, etc.
    is_boss: bool = False
    
    def is_alive(self) -> bool:
        """Check if enemy is still alive"""
        return self.current_hp > 0
    
    def take_damage(self, damage: int) -> bool:
        """
        Apply damage to enemy.
        
        Returns True if enemy was killed by this damage.
        """
        self.current_hp = max(0, self.current_hp - damage)
        return self.current_hp == 0
    
    def __str__(self):
        status = "Alive" if self.is_alive() else "Dead"
        boss_marker = " [BOSS]" if self.is_boss else ""
        return f"{self.name}{boss_marker} HP: {self.current_hp}/{self.max_hp} [{status}]"


class CombatResolver:
    """
    Handles all combat mechanics for the simulation.
    
    This includes enemy creation, turn order, attack resolution,
    spell casting, and integration with the character/party systems.
    """
    
    def __init__(self, event_emitter: EventEmitter, rng: random.Random):
        """
        Initialize combat resolver.
        
        Args:
            event_emitter: For broadcasting combat events
            rng: Seeded random number generator for fair combat
        """
        self.event_emitter = event_emitter
        self.rng = rng
        
        # Basic spell effects (placeholder for full spell system)
        self.basic_spells = {
            'heal': {'target': 'ally', 'effect': 'heal', 'power': 8},
            'harm': {'target': 'enemy', 'effect': 'damage', 'power': 6},
            'shield': {'target': 'ally', 'effect': 'ac_boost', 'power': 2},
            'weaken': {'target': 'enemy', 'effect': 'might_penalty', 'power': 2}
        }
    
    def create_enemies_for_room(self, room: Room) -> List[Enemy]:
        """
        Create enemies based on room parameters.
    
        For boss rooms: First enemy is the boss, rest are minions.
    
        Args:
            room: Room containing enemy parameters
        
        Returns:
            List of Enemy objects for this encounter
        """
        enemies = []
        floor_level = room.difficulty_level
    
        for i in range(room.enemy_count):
            # In boss rooms, only the first enemy is the actual boss
            is_this_enemy_boss = room.is_boss_room and i == 0
            enemy = self._create_single_enemy(floor_level, is_this_enemy_boss, i + 1)
            enemies.append(enemy)
    
        return enemies

    def _create_single_enemy(self, floor_level: int, is_boss: bool, enemy_number: int) -> Enemy:
        """
        Create a single enemy with stats based on floor level.
        
        Base Enemy Stats from design doc:
        HP = Floor Level × 5 + 1d4
        AC = 10 + Floor Level
        MIGHT = Floor Level
        Damage = 1d4 + Floor Level (increases die type every 2 levels)
        
        Boss Modifiers:
        HP × 2, All stats + 2
        """
        # Base stats
        base_hp = floor_level * 5 + self.rng.randint(1, 4)
        base_ac = 10 + floor_level
        base_might = floor_level
        
        # Damage die progression: d4 -> d6 -> d8 -> d10 -> d12
        damage_die = min(12, 4 + ((floor_level - 1) // 2) * 2)
        
        # Apply boss modifiers
        if is_boss:
            base_hp *= 2
            base_ac += 2
            base_might += 2
            name = f"Boss {enemy_number}"
        else:
            name = f"Enemy {enemy_number}"
        
        return Enemy(
            name=name,
            max_hp=base_hp,
            current_hp=base_hp,
            ac=base_ac,
            might=base_might,
            damage_die=damage_die,
            is_boss=is_boss
        )
    
    def resolve_combat(self, party: Party, room: Room) -> bool:
        """
        Resolve a complete combat encounter.
        
        Runs turn-based combat until either all enemies are dead
        or the party is wiped/retreats.
        
        Args:
            party: Party engaging in combat
            room: Room containing the combat encounter
            
        Returns:
            True if party survives, False if party is wiped
        """
        # Create enemies for this encounter
        enemies = self.create_enemies_for_room(room)
        
        # Announce combat start
        self.event_emitter.combat_start(
            party.guild_id, party.guild_name, 
            len(enemies), room.is_boss_room
        )
        
        combat_round = 0
        max_rounds = 20  # Prevent infinite combat
        
        while enemies and party.alive_members() and combat_round < max_rounds:
            combat_round += 1
            
            # Party members act first (player advantage)
            self._party_combat_turn(party, enemies)
            
            # Remove dead enemies
            enemies = [e for e in enemies if e.is_alive()]
            
            # Enemies counterattack if any survive
            if enemies:
                self._enemy_combat_turn(party, enemies)
        
        # Combat resolution
        if not enemies:
            # Victory!
            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.COMBAT_END,
                f"Victory! All enemies defeated in {combat_round} rounds!",
                details={'rounds': combat_round, 'victory': True}
            )
            party.defeat_monsters(room.enemy_count)
            return True
        elif not party.alive_members():
            # Party wiped
            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.COMBAT_END,
                f"The party has been wiped out after {combat_round} rounds!",
                details={'rounds': combat_round, 'victory': False}
            )
            return False
        else:
            # Timeout (rare)
            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.COMBAT_END,
                f"Combat ends in stalemate after {max_rounds} rounds",
                details={'rounds': combat_round, 'timeout': True}
            )
            return True
    
    def _party_combat_turn(self, party: Party, enemies: List[Enemy]):
        """Handle all party member actions in combat"""
        for member in party.alive_members():
            if not enemies:  # All enemies dead
                break
            
            # Choose action based on role and situation
            if member.role in [CharacterRole.STRIKER, CharacterRole.BURGLAR]:
                self._character_attack(party, member, enemies)
            else:  # SUPPORT or CONTROLLER
                self._character_cast_spell(party, member, enemies)
    
    def _character_attack(self, party: Party, attacker: Character, enemies: List[Enemy]):
        """Resolve a character's attack action"""
        if not enemies:
            return
        
        # Choose random enemy target
        target = self.rng.choice(enemies)
        
        # Roll attack: d20 + might vs enemy AC
        attack_roll = self.rng.randint(1, 20)
        total_attack = attack_roll + attacker.might
        
        if attack_roll == 20:
            # Critical hit!
            damage = self._calculate_critical_damage(attacker)
            target.take_damage(damage)
            
            self.event_emitter.character_attack(
                party.guild_id, party.guild_name, attacker.name, damage, critical=True
            )
            
            if not target.is_alive():
                self.event_emitter.emit(
                    party.guild_id, party.guild_name, EventType.COMBAT_END,
                    f"{target.name} is slain by {attacker.name}'s critical hit!",
                    details={'killer': attacker.name, 'victim': target.name}
                )
        
        elif attack_roll == 1:
            # Critical miss!
            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.ATTACK_MISS,
                f"{attacker.name} critically fumbles their attack!",
                details={'character': attacker.name, 'critical_miss': True}
            )
        
        elif total_attack >= target.ac:
            # Normal hit
            damage = self._calculate_normal_damage(attacker)
            target.take_damage(damage)
            
            self.event_emitter.character_attack(
                party.guild_id, party.guild_name, attacker.name, damage, critical=False
            )
            
            if not target.is_alive():
                self.event_emitter.emit(
                    party.guild_id, party.guild_name, EventType.COMBAT_END,
                    f"{target.name} falls to {attacker.name}'s attack!",
                    details={'killer': attacker.name, 'victim': target.name}
                )
        
        else:
            # Miss
            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.ATTACK_MISS,
                f"{attacker.name} misses {target.name} (rolled {total_attack} vs AC {target.ac})",
                details={'character': attacker.name, 'roll': total_attack, 'target_ac': target.ac}
            )
    
    def _character_cast_spell(self, party: Party, caster: Character, enemies: List[Enemy]):
        """Resolve a character's spell casting action"""
        if caster.spell_slots == 0:
            # No spell slots, fall back to basic attack
            self._character_attack(party, caster, enemies)
            return
        
        # Check if caster has any available spells
        available_spells = caster.spell_slots - len(caster.disabled_spells)
        if available_spells <= 0:
            # All spells disabled, fall back to basic attack
            self._character_attack(party, caster, enemies)
            return
        
        # Choose spell based on situation (simple AI for now)
        spell_name = self._choose_spell_for_situation(party, enemies)
        spell = self.basic_spells.get(spell_name)
        
        if not spell:
            # No appropriate spell, attack instead
            self._character_attack(party, caster, enemies)
            return
        
        # Roll spell: d20 + wit vs DC (10 + floor level)
        spell_roll = self.rng.randint(1, 20)
        total_roll = spell_roll + caster.wit
        spell_dc = 10 + max(1, len(enemies))  # Simple DC based on enemy count
        
        if spell_roll == 1:
            # Critical failure - spell disabled for rest of expedition
            caster.disable_spell(spell_name)
            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.SPELL_FAIL,
                f"{caster.name} critically fails casting {spell_name}! Spell disabled for expedition!",
                details={'character': caster.name, 'spell': spell_name, 'disabled': True},
                priority='high'
            )
        
        elif spell_roll == 20 or total_roll >= spell_dc:
            # Spell succeeds
            success_type = "critical" if spell_roll == 20 else "normal"
            self._apply_spell_effect(party, caster, spell, spell_name, enemies, success_type)
        
        else:
            # Spell fails (but not critically)
            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.SPELL_FAIL,
                f"{caster.name} fails to cast {spell_name} (rolled {total_roll} vs DC {spell_dc})",
                details={'character': caster.name, 'spell': spell_name, 'roll': total_roll, 'dc': spell_dc}
            )
    
    def _enemy_combat_turn(self, party: Party, enemies: List[Enemy]):
        """Handle all enemy attacks"""
        for enemy in enemies:
            if not party.alive_members():  # All party members down
                break
            
            # Enemy attacks random party member
            target = self.rng.choice(party.alive_members())
            
            # Roll attack: d20 + enemy might vs character AC
            attack_roll = self.rng.randint(1, 20)
            total_attack = attack_roll + enemy.might
            character_ac = target.get_ac()  # Use character's AC method
            
            if total_attack >= character_ac:
                # Hit!
                damage = self.rng.randint(1, enemy.damage_die) + enemy.might
                was_downed = target.take_damage(damage)
                
                self.event_emitter.emit(
                    party.guild_id, party.guild_name, EventType.ATTACK_HIT,
                    f"{enemy.name} hits {target.name} for {damage} damage!",
                    details={'attacker': enemy.name, 'target': target.name, 'damage': damage}
                )
                
                if was_downed:
                    if target.is_alive:
                        # Character unconscious but survived death test
                        self.event_emitter.character_unconscious(
                            party.guild_id, party.guild_name, target.name
                        )
                    else:
                        # Character died in death test
                        self.event_emitter.character_dies(
                            party.guild_id, party.guild_name, target.name
                        )
            else:
                # Miss
                self.event_emitter.emit(
                    party.guild_id, party.guild_name, EventType.ATTACK_MISS,
                    f"{enemy.name} misses {target.name}",
                    details={'attacker': enemy.name, 'target': target.name}
                )
    
    # === Helper Methods ===
    
    def _calculate_normal_damage(self, character: Character) -> int:
        """Calculate normal attack damage for a character"""
        if character.role == CharacterRole.STRIKER:
            return self.rng.randint(1, 8) + character.might  # d8 + might
        else:
            return self.rng.randint(1, 6) + character.might  # d6 + might
    
    def _calculate_critical_damage(self, character: Character) -> int:
        """Calculate critical hit damage for a character"""
        if character.role == CharacterRole.STRIKER:
            return 8 + self.rng.randint(1, 8) + character.might  # max + d8 + might
        else:
            return 6 + self.rng.randint(1, 6) + character.might  # max + d6 + might
    
    def _choose_spell_for_situation(self, party: Party, enemies: List[Enemy]) -> str:
        """Simple AI to choose appropriate spell"""
        # Check if anyone needs healing
        injured_members = [m for m in party.alive_members() if m.current_hp < m.max_hp * 0.7]
        
        if injured_members:
            return 'heal'
        elif len(enemies) > 2:
            return 'harm'  # Damage when outnumbered
        else:
            return 'harm'  # Default to damage
    
    def _apply_spell_effect(self, party: Party, caster: Character, spell: Dict, spell_name: str, enemies: List[Enemy], success_type: str = "normal"):
        """Apply the effect of a successfully cast spell"""
        effect = spell['effect']
        power = spell['power']
        
        # Critical successes are more powerful
        if success_type == "critical":
            power = int(power * 1.5)
        
        if effect == 'heal':
            # Heal injured party member
            injured = [m for m in party.alive_members() if m.current_hp < m.max_hp]
            if injured:
                target = self.rng.choice(injured)
                healed = target.heal(power)
                crit_text = " (CRITICAL!)" if success_type == "critical" else ""
                self.event_emitter.emit(
                    party.guild_id, party.guild_name, EventType.CHARACTER_HEALED,
                    f"{caster.name} heals {target.name} for {healed} HP{crit_text}!",
                    details={'caster': caster.name, 'target': target.name, 'healing': healed, 'critical': success_type == "critical"}
                )
        
        elif effect == 'damage':
            # Damage random enemy
            if enemies:
                target = self.rng.choice(enemies)
                target.take_damage(power)
                crit_text = " (CRITICAL!)" if success_type == "critical" else ""
                self.event_emitter.emit(
                    party.guild_id, party.guild_name, EventType.SPELL_CAST,
                    f"{caster.name} casts {spell_name} on {target.name} for {power} damage{crit_text}!",
                    details={'caster': caster.name, 'spell': spell_name, 'target': target.name, 'damage': power, 'critical': success_type == "critical"}
                )


# === Test the combat system ===
if __name__ == "__main__":
    print("Testing Combat Resolver...")
    print("=" * 60)
    
    # Import test utilities
    from models.party import create_test_party
    from simulation.dungeon_generator import DungeonGenerator, RoomType
    
    # Create test setup
    event_emitter = EventEmitter()
    rng = random.Random(12345)
    combat_resolver = CombatResolver(event_emitter, rng)
    
    # Create test party
    party = create_test_party(1, "Test Heroes")
    
    # Create test combat room
    test_room = Room(
        floor_number=2,
        room_number=3,
        room_type=RoomType.COMBAT,
        difficulty_level=2,
        enemy_count=3,
        is_boss_room=False
    )
    
    print("=== COMBAT TEST ===")
    print(f"Party: {party.guild_name}")
    for member in party.members:
        print(f"  {member}")
    
    print(f"\nRoom: {test_room}")
    
    # Run combat
    print(f"\n=== COMBAT BEGINS ===")
    party_survived = combat_resolver.resolve_combat(party, test_room)
    
    print(f"\n=== COMBAT RESULTS ===")
    print(f"Party survived: {party_survived}")
    print(f"Survivors: {len(party.alive_members())}/4")
    for member in party.members:
        print(f"  {member}")
    
    print(f"\nTotal events generated: {len(event_emitter.events)}")
    print("\n✓ Combat resolver is working!")
