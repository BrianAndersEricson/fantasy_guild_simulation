"""
Combat Resolver for Fantasy Guild Manager simulation.

This module handles turn-based combat between parties and enemies.
Now uses the full enemy type system with special abilities and boss mechanics.
Updated to use the complete spell system with intelligent AI casting.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple

from models.character import Character, CharacterRole
from models.party import Party, create_test_party
from models.events import EventEmitter, EventType
from models.enemy import Enemy, create_encounter
from models.enemy_types import SpecialAbility, BossType
from simulation.dungeon_generator import Room, RoomType
from simulation.debuff_system import DebuffType, Debuff, DebuffManager

# Import the new spell system
from simulation.spell_resolver import SpellResolver, SpellResult
from models.spell import SPELLS_BY_NAME


class CombatResolver:
    """
    Handles all combat mechanics for the simulation.

    This includes enemy creation, turn order, attack resolution,
    intelligent spell casting, special abilities, and boss mechanics.
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

        # Initialize the new spell resolver
        self.spell_resolver = SpellResolver(rng)

        # Map special abilities to debuff types
        self.ability_to_debuff = {
            SpecialAbility.POISON: DebuffType.POISONED,
            SpecialAbility.SLOW: DebuffType.SLOWED,
            SpecialAbility.WEAKEN: DebuffType.WEAKENED,
            SpecialAbility.BLIND: DebuffType.BLINDED,
            SpecialAbility.STUN: DebuffType.STUNNED,
            SpecialAbility.FRIGHTEN: DebuffType.FRIGHTENED,
            SpecialAbility.CURSE: DebuffType.CURSED,
            SpecialAbility.BURN: DebuffType.POISONED  # Treat burn as poison
        }

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
        enemies = create_encounter(
            floor=room.floor_number,
            enemy_count=room.enemy_count,
            is_boss_room=room.is_boss_room,
            rng=self.rng
        )

        # Announce combat start
        self.event_emitter.combat_start(
            party.guild_id, party.guild_name,
            len(enemies), room.is_boss_room
        )

        # Emit individual enemy appearance events using the new event type
        for enemy in enemies:
            self.event_emitter.enemy_appears(
                party.guild_id, party.guild_name,
                enemy.name, enemy.enemy_type.description, enemy.is_boss
            )

        combat_round = 0
        max_rounds = 20  # Prevent infinite combat

        while enemies and party.alive_members() and combat_round < max_rounds:
            combat_round += 1
            self.event_emitter.increment_tick()

            # Process regeneration and status effects at start of round
            self._process_round_start_effects(party, enemies)

            # Party members act first (player advantage)
            self._party_combat_turn(party, enemies, room.floor_number)

            # Remove dead enemies
            dead_enemies = [e for e in enemies if not e.is_alive()]
            enemies = [e for e in enemies if e.is_alive()]

            # Announce defeated enemies using the new event type
            for enemy in dead_enemies:
                self.event_emitter.enemy_defeated(
                    party.guild_id, party.guild_name, enemy.name
                )

            # Boss abilities trigger
            self._process_boss_abilities(party, enemies)

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

    def _process_round_start_effects(self, party: Party, enemies: List[Enemy]):
        """Process regeneration and status effects at start of round"""
        # Process party member effects
        for member in party.members:
            if member.is_alive and member.is_conscious:
                # Process spell regeneration (Lifebloom effect)
                regen_healed = member.process_regeneration()
                if regen_healed > 0:
                    self.event_emitter.emit(
                        party.guild_id, party.guild_name, EventType.CHARACTER_HEALED,
                        f"{member.name} regenerates {regen_healed} HP!",
                        details={'character': member.name, 'healing': regen_healed, 'regeneration': True}
                    )

                # Apply poison damage
                poison_damage = member.debuff_manager.get_poison_damage()
                if poison_damage > 0:
                    was_downed = member.take_damage(poison_damage)
                    # Use the new status_damage event
                    self.event_emitter.status_damage(
                        party.guild_id, party.guild_name,
                        member.name, poison_damage, 'poison'
                    )

                    if was_downed:
                        if member.is_alive:
                            self.event_emitter.character_unconscious(
                                party.guild_id, party.guild_name, member.name
                            )
                        else:
                            self.event_emitter.character_dies(
                                party.guild_id, party.guild_name, member.name
                            )

                # Tick debuffs
                expired = member.debuff_manager.tick_all_debuffs()
                for debuff in expired:
                    # Use the new debuff_expired event
                    self.event_emitter.debuff_expired(
                        party.guild_id, party.guild_name,
                        member.name, debuff.debuff_type.value
                    )

    def _process_boss_abilities(self, party: Party, enemies: List[Enemy]):
        """Process boss special abilities"""
        for enemy in enemies:
            if enemy.is_boss and enemy.boss_ability:
                # Rage: +2 damage when bloodied
                if enemy.boss_ability == BossType.RAGE and enemy.is_bloodied():
                    # Check if this is the first time entering rage
                    if not hasattr(enemy, '_rage_announced'):
                        enemy._rage_announced = True
                        self.event_emitter.boss_ability_triggered(
                            party.guild_id, party.guild_name,
                            enemy.name, 'rage', 'becomes enraged as its health drops!'
                        )

                # Summon: Call minions when first bloodied
                elif enemy.boss_ability == BossType.SUMMON and enemy.is_bloodied() and not enemy.boss_triggered:
                    enemy.boss_triggered = True
                    minion_count = self.rng.randint(1, 4)
                    self.event_emitter.boss_ability_triggered(
                        party.guild_id, party.guild_name,
                        enemy.name, 'summon', f'summons {minion_count} minions to aid in battle!'
                    )
                    # In full implementation, would actually create minions

                # Aura: Announce once at start of combat
                elif enemy.boss_ability == BossType.AURA:
                    if not hasattr(enemy, '_aura_announced'):
                        enemy._aura_announced = True
                        self.event_emitter.boss_ability_triggered(
                            party.guild_id, party.guild_name,
                            enemy.name, 'aura', 'empowers nearby allies with dark energy!'
                        )

                # Regenerate: Heal each round
                elif enemy.boss_ability == BossType.REGENERATE and enemy.current_hp < enemy.max_hp:
                    heal_amount = self.rng.randint(1, 4)
                    actual_heal = enemy.heal(heal_amount)
                    if actual_heal > 0:
                        self.event_emitter.emit(
                            party.guild_id, party.guild_name, EventType.CHARACTER_HEALED,
                            f"{enemy.name} regenerates {actual_heal} HP!",
                            details={'enemy': enemy.name, 'healing': actual_heal}
                        )

    def _party_combat_turn(self, party: Party, enemies: List[Enemy], floor_level: int):
        """Handle all party member actions in combat"""
        for member in party.alive_members():
            if not enemies:  # All enemies dead
                break

            # Check if stunned
            if member.debuff_manager.is_stunned():
                self.event_emitter.emit(
                    party.guild_id, party.guild_name, EventType.ATTACK_MISS,
                    f"{member.name} is stunned and cannot act!",
                    details={'character': member.name, 'stunned': True}
                )
                continue

            # Check if confused (might hit ally)
            if member.debuff_manager.is_confused():
                if self.rng.random() < member.debuff_manager.get_confusion_chance():
                    # Hit random ally instead
                    self._confused_attack(party, member)
                    continue

            # Choose action based on role and spellcasting ability
            if member.can_cast_spells() and member.get_available_spells():
                self._character_cast_spell(party, member, enemies, floor_level)
            else:
                self._character_attack(party, member, enemies)

    def _character_attack(self, party: Party, attacker: Character, enemies: List[Enemy]):
        """Resolve a character's attack action"""
        if not enemies:
            return

        # Choose random enemy target
        target = self.rng.choice(enemies)

        # Calculate modifiers
        attack_modifier = attacker.get_might_modifier()
        attack_modifier += attacker.debuff_manager.get_stat_modifier('might')
        attack_modifier += attacker.debuff_manager.get_attack_modifier()

        # Roll attack: d20 + modifiers vs enemy AC
        attack_roll = self.rng.randint(1, 20)
        total_attack = attack_roll + attack_modifier

        if attack_roll == 20:
            # Critical hit!
            damage = self._calculate_critical_damage(attacker)
            target.take_damage(damage)

            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.ATTACK_CRITICAL,
                f"{attacker.name} lands a CRITICAL HIT on {target.name} for {damage} damage!",
                details={'attacker': attacker.name, 'target': target.name, 'damage': damage, 'critical': True},
                priority="high"
            )

        elif attack_roll == 1:
            # Critical miss!
            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.ATTACK_MISS,
                f"{attacker.name} critically fumbles their attack!",
                details={'character': attacker.name, 'critical_miss': True}
            )

        elif total_attack >= target.get_effective_ac():
            # Normal hit
            damage = self._calculate_normal_damage(attacker)
            target.take_damage(damage)

            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.ATTACK_HIT,
                f"{attacker.name} attacks {target.name} for {damage} damage",
                details={'attacker': attacker.name, 'target': target.name, 'damage': damage}
            )

        else:
            # Miss
            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.ATTACK_MISS,
                f"{attacker.name} misses {target.name} (rolled {total_attack} vs AC {target.get_effective_ac()})",
                details={'character': attacker.name, 'roll': total_attack, 'target_ac': target.get_effective_ac()}
            )

    def _character_cast_spell(self, party: Party, caster: Character, enemies: List[Enemy], floor_level: int):
        """Resolve a character's spell casting action using the new spell system"""
        # Select best spell for current situation
        spell_choice = self.spell_resolver.select_spell_for_character(
            caster, party.members, enemies, floor_level
        )
        
        if not spell_choice:
            # No suitable spell, fall back to attack
            self._character_attack(party, caster, enemies)
            return

        # Get the spell definition
        spell = SPELLS_BY_NAME.get(spell_choice)
        if not spell:
            # Unknown spell, fall back to attack
            self._character_attack(party, caster, enemies)
            return

        # Select target for the spell
        target = self.spell_resolver.select_target_for_spell(
            spell, caster, party.members, enemies
        )
        
        if not target:
            # No valid target, fall back to attack
            self._character_attack(party, caster, enemies)
            return

        # Calculate enemy level for DC (use floor level as fallback)
        enemy_level = floor_level
        if enemies:
            # Try to get average enemy level, fall back to floor level
            total_level = 0
            for enemy in enemies:
                level = getattr(enemy, 'level', floor_level)
                # Handle Mock objects or non-integer values
                if isinstance(level, int):
                    total_level += level
                else:
                    total_level += floor_level
            enemy_level = total_level // len(enemies)

        # Cast the spell
        result = self.spell_resolver.cast_spell(
            caster, spell_choice, target, floor_level, enemy_level
        )

        # Emit appropriate event based on result
        if result.result == SpellResult.CRITICAL_SUCCESS:
            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.SPELL_CAST,
                f"CRITICAL! {result.description}",
                details={
                    'caster': caster.name,
                    'spell': spell_choice,
                    'target': result.target,
                    'result': result.result.value,
                    'roll': result.roll,
                    'dc': result.dc,
                    'damage': result.damage_dealt,
                    'healing': result.healing_done,
                    'debuff': result.debuff_applied,
                    'critical': True
                },
                priority='high'
            )
        
        elif result.result == SpellResult.SUCCESS:
            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.SPELL_CAST,
                result.description,
                details={
                    'caster': caster.name,
                    'spell': spell_choice,
                    'target': result.target,
                    'result': result.result.value,
                    'roll': result.roll,
                    'dc': result.dc,
                    'damage': result.damage_dealt,
                    'healing': result.healing_done,
                    'debuff': result.debuff_applied
                }
            )
        
        elif result.result == SpellResult.CRITICAL_FAILURE:
            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.SPELL_FAIL,
                result.description,
                details={
                    'character': caster.name,
                    'spell': spell_choice,
                    'disabled': True,
                    'critical_failure': True
                },
                priority='high'
            )
        
        elif result.result == SpellResult.FAILURE:
            self.event_emitter.emit(
                party.guild_id, party.guild_name, EventType.SPELL_FAIL,
                result.description,
                details={
                    'character': caster.name,
                    'spell': spell_choice,
                    'roll': result.roll,
                    'dc': result.dc
                }
            )
        
        elif result.result == SpellResult.NO_VALID_TARGET:
            # Fall back to attack if no valid target found
            self._character_attack(party, caster, enemies)
        
        elif result.result == SpellResult.SPELL_DISABLED:
            # Spell is disabled, fall back to attack
            self._character_attack(party, caster, enemies)

        # Apply any additional effects from spell results
        if result.debuff_applied and hasattr(target, 'debuff_manager'):
            self.event_emitter.debuff_applied(
                party.guild_id, party.guild_name,
                result.target, result.debuff_applied, caster.name, result.debuff_duration
            )

    def _enemy_combat_turn(self, party: Party, enemies: List[Enemy]):
        """Handle all enemy attacks"""
        # Check for boss aura
        aura_bonus = 0
        for enemy in enemies:
            if enemy.is_boss and enemy.boss_ability == BossType.AURA:
                aura_bonus = 1
                break

        for enemy in enemies:
            if not party.alive_members():  # All party members down
                break

            # Enemy attacks random party member
            target = self.rng.choice(party.alive_members())

            # Roll attack: d20 + enemy might vs character AC
            attack_roll = self.rng.randint(1, 20)
            enemy_might = enemy.get_effective_might() + aura_bonus

            # Boss rage bonus
            if enemy.is_boss and enemy.boss_ability == BossType.RAGE and enemy.is_bloodied():
                enemy_might += 2

            total_attack = attack_roll + enemy_might
            character_ac = target.get_ac()

            if total_attack >= character_ac:
                # Hit!
                damage = self.rng.randint(1, enemy.damage_die) + enemy_might
                was_downed = target.take_damage(damage)

                self.event_emitter.emit(
                    party.guild_id, party.guild_name, EventType.ATTACK_HIT,
                    f"{enemy.name} hits {target.name} for {damage} damage!",
                    details={'attacker': enemy.name, 'target': target.name, 'damage': damage, 'enemy': True}
                )

                # Apply special ability on hit
                if enemy.enemy_type.special_ability != SpecialAbility.NONE:
                    self._apply_enemy_special_ability(party, enemy, target)

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

    def _apply_enemy_special_ability(self, party: Party, enemy: Enemy, target: Character):
        """Apply special ability effect when enemy hits"""
        # Roll to see if ability triggers
        trigger_roll = self.rng.randint(1, 4)
        if trigger_roll >= enemy.enemy_type.special_trigger:
            # Apply the debuff
            debuff_type = self.ability_to_debuff.get(enemy.enemy_type.special_ability)
            if debuff_type:
                duration = self.rng.randint(1, 4)  # 1d4 rounds
                debuff = Debuff(
                    debuff_type=debuff_type,
                    duration_remaining=duration,
                    source=enemy.name
                )

                target.debuff_manager.apply_debuff(debuff)

                # Use the new debuff_applied event
                self.event_emitter.debuff_applied(
                    party.guild_id, party.guild_name,
                    target.name, debuff_type.value, enemy.name, duration
                )

    def _confused_attack(self, party: Party, attacker: Character):
        """Handle confused character hitting ally"""
        allies = [m for m in party.alive_members() if m != attacker]
        if not allies:
            return

        target = self.rng.choice(allies)
        damage = self._calculate_normal_damage(attacker)
        was_downed = target.take_damage(damage)

        self.event_emitter.emit(
            party.guild_id, party.guild_name, EventType.ATTACK_HIT,
            f"CONFUSION! {attacker.name} attacks ally {target.name} for {damage} damage!",
            details={'attacker': attacker.name, 'target': target.name, 'damage': damage, 'confused': True},
            priority="high"
        )

        if was_downed:
            if target.is_alive:
                self.event_emitter.character_unconscious(
                    party.guild_id, party.guild_name, target.name
                )
            else:
                self.event_emitter.character_dies(
                    party.guild_id, party.guild_name, target.name
                )

    # === Helper Methods ===

    def _calculate_normal_damage(self, character: Character) -> int:
        """Calculate normal attack damage for a character"""
        base_damage = 0
        if character.role == CharacterRole.STRIKER:
            base_damage = self.rng.randint(1, 8) + character.get_might_modifier()  # d8 + might modifier
        else:
            base_damage = self.rng.randint(1, 6) + character.get_might_modifier()  # d6 + might modifier

        # Apply debuff modifiers
        base_damage += character.debuff_manager.get_stat_modifier('might')

        return max(1, base_damage)  # Minimum 1 damage

    def _calculate_critical_damage(self, character: Character) -> int:
        """Calculate critical hit damage for a character"""
        if character.role == CharacterRole.STRIKER:
            base_damage = 8 + self.rng.randint(1, 8) + character.get_might_modifier()  # max + d8 + might modifier
        else:
            base_damage = 6 + self.rng.randint(1, 6) + character.get_might_modifier()  # max + d6 + might modifier

        # Apply debuff modifiers
        base_damage += character.debuff_manager.get_stat_modifier('might')

        return max(1, base_damage)


