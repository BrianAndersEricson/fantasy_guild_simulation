"""
Spell resolution system for the Fantasy Guild Manager simulation.

This handles all spellcasting during combat - from target selection
to effect application. Spells are cast automatically by AI logic
based on current battlefield conditions.
"""

import random
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum

# Import our spell and character systems
from models.spell import (
    Spell, SPELLS_BY_NAME, SpellType, TargetType, DebuffType,
    SPELLS_BY_TYPE
)
from models.character import Character, CharacterRole
from simulation.debuff_system import DebuffManager


class SpellResult(Enum):
    """Possible outcomes of casting a spell"""
    SUCCESS = "success"
    FAILURE = "failure" 
    CRITICAL_SUCCESS = "critical_success"
    CRITICAL_FAILURE = "critical_failure"
    NO_VALID_TARGET = "no_valid_target"
    SPELL_DISABLED = "spell_disabled"


@dataclass
class SpellCastResult:
    """Result of attempting to cast a spell"""
    result: SpellResult
    spell_name: str
    caster: str
    target: Optional[str] = None
    damage_dealt: int = 0
    healing_done: int = 0
    debuff_applied: Optional[str] = None
    debuff_duration: int = 0
    roll: int = 0
    dc: int = 0
    description: str = ""
    special_effects: List[str] = None
    
    def __post_init__(self):
        if self.special_effects is None:
            self.special_effects = []


class SpellResolver:
    """
    Handles all spell casting during combat.
    
    This system:
    1. Selects appropriate spells based on battlefield conditions
    2. Chooses valid targets for each spell
    3. Resolves spell effects with proper dice rolling
    4. Applies results to characters and enemies
    """
    
    def __init__(self, rng: random.Random):
        """
        Initialize spell resolver with random number generator.
        
        Args:
            rng: Seeded random generator for deterministic results
        """
        self.rng = rng
    
    def select_spell_for_character(self, caster: Character, party: List[Character], 
                                 enemies: List[Any], floor_level: int) -> Optional[str]:
        """
        Select the best spell for a character to cast based on current conditions.
        
        AI priority logic:
        1. Cure critical debuffs (confusion, poison)
        2. Heal critically injured allies (< 25% HP)
        3. Apply buffs to unbuffed allies
        4. Disable/damage enemies
        
        Args:
            caster: Character casting the spell
            party: All party members
            enemies: All enemies
            floor_level: Current floor for difficulty scaling
            
        Returns:
            Name of spell to cast, or None if no good options
        """
        available_spells = caster.get_available_spells()
        if not available_spells:
            return None
        
        # Analyze battlefield conditions
        alive_allies = [c for c in party if c.is_alive and c.is_conscious]
        wounded_allies = [c for c in alive_allies if c.current_hp < c.max_hp * 0.25]
        critically_wounded = [c for c in alive_allies if c.current_hp <= c.max_hp * 0.1]
        
        # Get allies with specific debuffs that can be cured
        confused_allies = [c for c in alive_allies if c.debuff_manager.has_debuff(DebuffType.CONFUSED)]
        poisoned_allies = [c for c in alive_allies if c.debuff_manager.has_debuff(DebuffType.POISONED)]
        
        # Check for spell priorities
        for spell_name in available_spells:
            spell = SPELLS_BY_NAME.get(spell_name)
            if not spell:
                continue
            
            # Priority 1: Emergency healing for critically wounded
            if spell.spell_type == SpellType.SUPPORT_HEAL and critically_wounded:
                if spell.name == "Mend Wounds" and len(critically_wounded) == 1:
                    return spell_name
                elif spell.name == "Sanctuary Pulse" and len(critically_wounded) > 1:
                    return spell_name
            
            # Priority 2: Cure dangerous debuffs
            if spell.spell_type == SpellType.SUPPORT_CURE:
                if (DebuffType.CONFUSED in spell.effect.cures_debuffs and confused_allies):
                    return spell_name
                if (DebuffType.POISONED in spell.effect.cures_debuffs and poisoned_allies):
                    return spell_name
            
            # Priority 3: Death protection for wounded allies
            if spell.name == "Echo of Hope" and wounded_allies:
                # Only use if someone is in real danger
                for ally in wounded_allies:
                    if ally.current_hp <= 3 and not ally.has_death_protection:
                        return spell_name
            
            # Priority 4: Healing for moderately wounded
            if spell.spell_type == SpellType.SUPPORT_HEAL and wounded_allies:
                return spell_name
            
            # Priority 5: Damage shields for healthy allies
            if spell.name == "Ward of Vitality":
                unshielded = [c for c in alive_allies if c.damage_shield == 0]
                if unshielded:
                    return spell_name
            
            # Priority 6: Disable enemies (controllers)
            if spell.spell_type == SpellType.CONTROLLER_DEBUFF and enemies:
                # Prefer stun/confusion for dangerous enemies
                if spell.name in ["Mindshatter", "Seren's Touch"] and len(enemies) > 2:
                    return spell_name
                return spell_name
            
            # Priority 7: Damage enemies (when nothing else to do)
            if spell.spell_type == SpellType.CONTROLLER_DAMAGE and enemies:
                return spell_name
        
        # Default: return first available spell
        return available_spells[0] if available_spells else None
    
    def select_target_for_spell(self, spell: Spell, caster: Character, 
                               party: List[Character], enemies: List[Any]) -> Optional[Any]:
        """
        Select the best target for a spell.
        
        Args:
            spell: The spell being cast
            caster: Character casting the spell
            party: All party members
            enemies: All enemies
            
        Returns:
            Target character/enemy, or None if no valid target
        """
        if spell.target_type == TargetType.SELF:
            return caster
        
        elif spell.target_type == TargetType.ALLY:
            valid_allies = [c for c in party if c.is_alive and c.is_conscious]
            
            if spell.spell_type == SpellType.SUPPORT_HEAL:
                # Target most wounded ally
                wounded = [c for c in valid_allies if c.current_hp < c.max_hp]
                if wounded:
                    return min(wounded, key=lambda c: c.current_hp)
                return None
            
            elif spell.spell_type == SpellType.SUPPORT_CURE:
                # Target ally with specific debuff this spell can cure
                for ally in valid_allies:
                    for debuff_type in spell.effect.cures_debuffs:
                        if ally.debuff_manager.has_debuff(debuff_type):
                            return ally
                return None
            
            elif spell.spell_type == SpellType.SUPPORT_BUFF:
                if spell.name == "Ward of Vitality":
                    # Target ally without shield
                    unshielded = [c for c in valid_allies if c.damage_shield == 0]
                    if unshielded:
                        # Prefer most vulnerable (lowest HP%)
                        return min(unshielded, key=lambda c: c.current_hp / c.max_hp)
                elif spell.name == "Echo of Hope":
                    # Target most wounded ally without protection
                    candidates = [c for c in valid_allies 
                                if not c.has_death_protection and c.current_hp <= c.max_hp * 0.3]
                    if candidates:
                        return min(candidates, key=lambda c: c.current_hp)
                
                # Default: target a random valid ally
                return self.rng.choice(valid_allies) if valid_allies else None
        
        elif spell.target_type == TargetType.ENEMY:
            if not enemies:
                return None
            
            # For debuff spells, prefer enemies without that debuff
            if spell.effect.debuff:
                unbuffed_enemies = []
                for enemy in enemies:
                    if hasattr(enemy, 'debuff_manager'):
                        if not enemy.debuff_manager.has_debuff(spell.effect.debuff):
                            unbuffed_enemies.append(enemy)
                if unbuffed_enemies:
                    # Prefer higher HP enemies for debuffs
                    return max(unbuffed_enemies, key=lambda e: getattr(e, 'current_hp', getattr(e, 'hp', 1)))
            
            # Default: target random enemy or highest HP enemy
            return max(enemies, key=lambda e: getattr(e, 'current_hp', getattr(e, 'hp', 1)))
        
        elif spell.target_type == TargetType.ALL_ALLIES:
            # Area spells don't need specific targeting
            valid_allies = [c for c in party if c.is_alive and c.is_conscious]
            return valid_allies if valid_allies else None
        
        elif spell.target_type == TargetType.ALL_ENEMIES:
            return enemies if enemies else None
        
        return None
    
    def cast_spell(self, caster: Character, spell_name: str, target: Any, 
                   floor_level: int, enemy_level: int = 0) -> SpellCastResult:
        """
        Resolve casting a specific spell.
        
        Args:
            caster: Character casting the spell
            spell_name: Name of spell to cast
            target: Target of the spell
            floor_level: Current floor level
            enemy_level: Target enemy level (if applicable)
            
        Returns:
            SpellCastResult with all effects and outcomes
        """
        spell = SPELLS_BY_NAME.get(spell_name)
        if not spell:
            return SpellCastResult(
                result=SpellResult.FAILURE,
                spell_name=spell_name,
                caster=caster.name,
                description=f"Unknown spell: {spell_name}"
            )
        
        # Check if spell is available
        if not caster.can_cast_spell(spell_name):
            return SpellCastResult(
                result=SpellResult.SPELL_DISABLED,
                spell_name=spell_name,
                caster=caster.name,
                description=f"{caster.name} cannot cast {spell_name} (disabled or unknown)"
            )
        
        # Calculate DC
        dc = spell.base_dc
        if spell.uses_floor_level:
            dc += floor_level
        if spell.uses_enemy_level and enemy_level > 0:
            dc += enemy_level
        
        # Roll for spell success
        roll = self.rng.randint(1, 20)
        spell_bonus = caster.get_wit_modifier()
        
        # Add secondary stat bonus
        if spell.secondary_stat:
            spell_bonus += caster.get_stat_modifier(spell.secondary_stat)
        
        total_roll = roll + spell_bonus
        
        # Determine result
        if roll == 1:
            # Critical failure - disable spell
            caster.disable_spell(spell_name)
            return SpellCastResult(
                result=SpellResult.CRITICAL_FAILURE,
                spell_name=spell_name,
                caster=caster.name,
                roll=roll,
                dc=dc,
                description=f"{caster.name} critically fails casting {spell_name}! Spell disabled."
            )
        
        elif roll == 20:
            # Critical success - enhanced effects
            result = self._apply_spell_effects(spell, caster, target, enhanced=True)
            result.result = SpellResult.CRITICAL_SUCCESS
            result.roll = roll
            result.dc = dc
            return result
        
        elif total_roll >= dc:
            # Success
            result = self._apply_spell_effects(spell, caster, target, enhanced=False)
            result.result = SpellResult.SUCCESS
            result.roll = total_roll
            result.dc = dc
            return result
        
        else:
            # Failure
            target_name = getattr(target, 'name', str(target)) if target else "unknown"
            return SpellCastResult(
                result=SpellResult.FAILURE,
                spell_name=spell_name,
                caster=caster.name,
                target=target_name,
                roll=total_roll,
                dc=dc,
                description=f"{caster.name} fails to cast {spell_name} (rolled {total_roll} vs DC {dc})"
            )
    
    def _apply_spell_effects(self, spell: Spell, caster: Character, target: Any, 
                           enhanced: bool = False) -> SpellCastResult:
        """
        Apply the effects of a successfully cast spell.
        
        Args:
            spell: The spell being cast
            caster: Character casting the spell
            target: Target of the spell
            enhanced: True for critical success (enhanced effects)
            
        Returns:
            SpellCastResult with applied effects
        """
        target_name = getattr(target, 'name', str(target)) if target else "area"
        result = SpellCastResult(
            result=SpellResult.SUCCESS,  # Will be updated by caller
            spell_name=spell.name,
            caster=caster.name,
            target=target_name
        )
        
        # Apply damage
        if spell.effect.damage > 0:
            base_damage = spell.effect.damage
            
            # Add secondary stat modifier
            if spell.secondary_stat:
                base_damage += caster.get_stat_modifier(spell.secondary_stat)
            
            # Roll damage dice (1d4 base becomes actual roll)
            if spell.effect.damage == 4:  # 1d4 base
                damage_roll = self.rng.randint(1, 4)
            else:
                damage_roll = spell.effect.damage
            
            total_damage = damage_roll + (caster.get_stat_modifier(spell.secondary_stat) if spell.secondary_stat else 0)
            
            if enhanced:
                total_damage = max(total_damage * 2, total_damage + 4)  # Double or +4, whichever is better
            
            # Apply damage to target
            if hasattr(target, 'take_damage'):
                target.take_damage(total_damage)
                result.damage_dealt = total_damage
                crit_text = " (CRITICAL!)" if enhanced else ""
                result.description = f"{caster.name} casts {spell.name} dealing {total_damage} damage to {target_name}{crit_text}!"
            
        # Apply healing
        elif spell.effect.healing > 0:
            base_healing = spell.effect.healing
            
            # Add secondary stat modifier (usually grit for support spells)
            if spell.secondary_stat:
                base_healing += caster.get_stat_modifier(spell.secondary_stat)
            
            # Roll healing dice if needed
            if spell.effect.healing == 4:  # 1d4 base
                healing_roll = self.rng.randint(1, 4)
                total_healing = healing_roll + (caster.get_stat_modifier(spell.secondary_stat) if spell.secondary_stat else 0)
            else:
                total_healing = base_healing
            
            if enhanced:
                total_healing = max(total_healing * 2, total_healing + 4)
            
            # Apply healing
            if spell.target_type == TargetType.ALL_ALLIES:
                # Area healing - heal all alive allies
                total_healed = 0
                healed_names = []
                for ally in target:  # target is list for area spells
                    if ally.is_alive and ally.is_conscious:
                        healed = ally.heal(total_healing)
                        if healed > 0:
                            total_healed += healed
                            healed_names.append(ally.name)
                
                result.healing_done = total_healed
                if healed_names:
                    crit_text = " (CRITICAL!)" if enhanced else ""
                    result.description = f"{caster.name} casts {spell.name} healing {total_healing} HP to: {', '.join(healed_names)}{crit_text}"
                else:
                    result.description = f"{caster.name} casts {spell.name} but no one needs healing"
            
            elif hasattr(target, 'heal'):
                healed = target.heal(total_healing)
                result.healing_done = healed
                if healed > 0:
                    crit_text = " (CRITICAL!)" if enhanced else ""
                    result.description = f"{caster.name} casts {spell.name} healing {healed} HP on {target_name}{crit_text}"
                else:
                    result.description = f"{caster.name} casts {spell.name} on {target_name} but they don't need healing"
        
        # Apply debuffs
        if spell.effect.debuff:
            duration = spell.effect.debuff_duration
            
            # Add secondary stat modifier to duration (usually luck for controllers)
            if spell.secondary_stat:
                duration += caster.get_stat_modifier(spell.secondary_stat)
            
            # Roll duration dice if needed
            if spell.effect.debuff_duration in [4, 6, 8]:  # 1d4, 1d6, 2d4 patterns
                if spell.effect.debuff_duration == 4:  # 1d4
                    duration_roll = self.rng.randint(1, 4)
                elif spell.effect.debuff_duration == 6:  # 1d6
                    duration_roll = self.rng.randint(1, 6)
                elif spell.effect.debuff_duration == 8:  # 2d4
                    duration_roll = self.rng.randint(1, 4) + self.rng.randint(1, 4)
                else:
                    duration_roll = spell.effect.debuff_duration
                    
                duration = duration_roll + (caster.get_stat_modifier(spell.secondary_stat) if spell.secondary_stat else 0)
            
            if enhanced:
                duration = max(duration + 2, int(duration * 1.5))  # +2 rounds or 50% longer
            
            # Apply debuff to target
            if hasattr(target, 'debuff_manager'):
                from simulation.debuff_system import Debuff
                debuff = Debuff(
                    debuff_type=spell.effect.debuff,
                    duration_remaining=duration,
                    source=f"{caster.name}'s {spell.name}"
                )
                target.debuff_manager.apply_debuff(debuff)  # Changed from add_debuff to apply_debuff
                
                result.debuff_applied = spell.effect.debuff.value
                result.debuff_duration = duration
                crit_text = " (CRITICAL!)" if enhanced else ""
                result.description = f"{caster.name} casts {spell.name} applying {spell.effect.debuff.value} to {target_name} for {duration} rounds{crit_text}"
        
        # Apply buffs and special effects
        special_effects = []
        
        # Damage shield
        if spell.effect.damage_shield > 0:
            shield_amount = spell.effect.damage_shield
            if spell.secondary_stat:
                shield_amount += caster.get_stat_modifier(spell.secondary_stat)
            
            if enhanced:
                shield_amount = max(shield_amount * 2, shield_amount + 4)
            
            if hasattr(target, 'apply_damage_shield'):
                target.apply_damage_shield(shield_amount)
                special_effects.append(f"{shield_amount} damage shield")
        
        # Death protection
        if spell.effect.prevents_death:
            if hasattr(target, 'apply_death_protection'):
                target.apply_death_protection()
                special_effects.append("death protection")
        
        # Regeneration
        if spell.name == "Lifebloom":
            regen_duration = spell.effect.debuff_duration  # Using duration field for regen
            if spell.secondary_stat:
                regen_duration += caster.get_stat_modifier(spell.secondary_stat)
            
            # Roll duration
            duration_roll = self.rng.randint(1, 6)
            total_duration = duration_roll + (caster.get_stat_modifier(spell.secondary_stat) if spell.secondary_stat else 0)
            
            if enhanced:
                total_duration += 3
            
            if hasattr(target, 'apply_regeneration'):
                target.apply_regeneration(total_duration)
                special_effects.append(f"regeneration for {total_duration} rounds")
        
        # Cure debuffs
        if spell.effect.cures_debuffs:
            cured_debuffs = []
            if hasattr(target, 'debuff_manager'):
                for debuff_type in spell.effect.cures_debuffs:
                    if target.debuff_manager.has_debuff(debuff_type):
                        target.debuff_manager.remove_debuff(debuff_type)
                        cured_debuffs.append(debuff_type.value)
            
            if cured_debuffs:
                special_effects.append(f"cured {', '.join(cured_debuffs)}")
                result.description = f"{caster.name} casts {spell.name} on {target_name}, curing: {', '.join(cured_debuffs)}"
            else:
                result.description = f"{caster.name} casts {spell.name} on {target_name} but no debuffs to cure"
        
        # Set special effects
        result.special_effects = special_effects
        
        # Set description if not already set
        if not result.description:
            if special_effects:
                crit_text = " (CRITICAL!)" if enhanced else ""
                result.description = f"{caster.name} casts {spell.name} on {target_name} granting: {', '.join(special_effects)}{crit_text}"
            else:
                crit_text = " (CRITICAL!)" if enhanced else ""
                result.description = f"{caster.name} casts {spell.name} on {target_name}{crit_text}"
        
        return result


