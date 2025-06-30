"""
Character model for the Fantasy Guild Manager simulation.

Characters are members of guilds who go on automated expeditions.
This is the foundation of our simulation - every action revolves around
these characters and their stats.

Now includes full spell system integration with debuff system.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from simulation.debuff_system import DebuffManager, DebuffType, Debuff


class CharacterRole(Enum):
    """
    The four roles that make up a balanced party.

    Each role has different strengths in the automated simulation:
    - STRIKER: High damage output, good survivability
    - BURGLAR: Detects/disarms traps, finds treasure
    - SUPPORT: Heals and buffs allies during combat
    - CONTROLLER: Disables and debuffs enemies
    """
    STRIKER = "striker"
    BURGLAR = "burglar"
    SUPPORT = "support"
    CONTROLLER = "controller"


@dataclass
class Character:
    """
    Represents a single character in a guild.

    Characters have four core stats that determine their effectiveness:
    - might: Physical power for attacks and damage
    - grit: Toughness, defense, and hit points
    - wit: Magical power for spells and mental challenges
    - luck: Trap detection, treasure finding, and critical hits

    During expeditions, characters can take damage, be healed,
    cast spells, or have their spells disabled by critical failures.
    """

    # === Identity ===
    name: str
    role: CharacterRole
    guild_id: int

    # === Base Stats (don't change during expedition) ===
    might: int = 10
    grit: int = 10
    wit: int = 10
    luck: int = 10

    # === Current Status (changes during expedition) ===
    current_hp: int = 0  # Will be set to max_hp in __post_init__
    max_hp: int = 0      # Calculated from role + grit + die roll
    is_alive: bool = True           # False if character is permanently dead
    is_conscious: bool = True       # False if knocked unconscious (can be revived)
    is_available: bool = True       # False if recovering from previous expedition

    # === Death Testing ===
    death_test_failures: int = 0    # How many death tests have been failed

    # === Spell System ===
    known_spells: List[str] = field(default_factory=list)  # Spell names character knows
    disabled_spells: List[str] = field(default_factory=list)  # Spells disabled by critical failures

    # === Equipment System (for future expansion) ===
    equipped_weapon: Optional[str] = None
    equipped_armor: Optional[str] = None
    equipped_accessory1: Optional[str] = None
    equipped_accessory2: Optional[str] = None

    # === Spell Effects (temporary buffs during expedition) ===
    damage_shield: int = 0          # Absorbs damage from Ward of Vitality
    has_death_protection: bool = False  # Echo of Hope effect
    regeneration_rounds: int = 0    # Lifebloom effect

    # === Expedition Tracking ===
    times_downed: int = 0  # How many times character has been downed (affects morale)

    def __post_init__(self):
        """Initialize calculated values and spell knowledge"""
        # Calculate max HP based on role and grit
        self.max_hp = self._calculate_max_hp()
        self.current_hp = self.max_hp
        
        # Initialize debuff manager for tracking status effects
        self.debuff_manager = DebuffManager()

        # Generate spell knowledge if not provided
        if not self.known_spells:
            self.known_spells = self._generate_starting_spells()

    def _calculate_max_hp(self) -> int:
        """Calculate maximum HP based on role and grit stat"""
        base_hp = self.grit

        if self.role == CharacterRole.STRIKER:
            # Tough fighters: grit + 1d10
            hp_roll = random.randint(1, 10)
        elif self.role == CharacterRole.BURGLAR:
            # Nimble but fragile: grit + 1d8
            hp_roll = random.randint(1, 8)
        else:  # SUPPORT or CONTROLLER
            # Squishy casters: grit + 1d6
            hp_roll = random.randint(1, 6)

        return base_hp + hp_roll

    def _generate_starting_spells(self) -> List[str]:
        """Generate starting spells for caster characters"""
        # Only casters get spells
        if self.role not in [CharacterRole.SUPPORT, CharacterRole.CONTROLLER]:
            return []

        # Create consistent random generator based on character identity
        # This ensures same character always gets same spells
        seed = hash(self.name + self.role.value + str(self.guild_id)) % (2**31)
        rng = random.Random(seed)

        # Import spell functions (lazy import to avoid circular dependencies)
        try:
            from models.spell import get_default_spells_for_role, generate_random_spells_for_role
            
            # Get default spell for role
            default_spells = get_default_spells_for_role(self.role.value)
            
            # Generate 1d4 additional random spells
            additional_count = rng.randint(1, 4)
            random_spells = generate_random_spells_for_role(self.role.value, additional_count, rng)
            
            return default_spells + random_spells
        except ImportError:
            # Fallback if spell system not available
            return []

    # === STAT MODIFIERS ===
    # Universal 3:1 scaling - every 3 points of stat = +1 modifier

    def get_might_modifier(self) -> int:
        """Calculate might modifier for attack rolls and damage."""
        return self.might // 3

    def get_grit_modifier(self) -> int:
        """Calculate grit modifier for AC, initiative, and defensive rolls."""
        return self.grit // 3

    def get_wit_modifier(self) -> int:
        """Calculate wit modifier for spell attack rolls and spell DCs."""
        return self.wit // 3

    def get_luck_modifier(self) -> int:
        """Calculate luck modifier for trap detection, treasure finding, and crits."""
        return self.luck // 3

    def get_stat_modifier(self, stat_name: str) -> int:
        """Get modifier for any stat by name."""
        if stat_name == 'might':
            return self.get_might_modifier()
        elif stat_name == 'grit':
            return self.get_grit_modifier()
        elif stat_name == 'wit':
            return self.get_wit_modifier()
        elif stat_name == 'luck':
            return self.get_luck_modifier()
        else:
            return 0

    # === SPELL SYSTEM ===

    def can_cast_spells(self) -> bool:
        """Check if this character can cast spells"""
        return self.role in [CharacterRole.SUPPORT, CharacterRole.CONTROLLER]

    def get_available_spells(self) -> List[str]:
        """Get spells that can currently be cast (not disabled)"""
        if not self.can_cast_spells() or not self.is_alive or not self.is_conscious:
            return []
        
        return [spell for spell in self.known_spells if spell not in self.disabled_spells]

    def has_spell(self, spell_name: str) -> bool:
        """Check if character knows a specific spell"""
        return spell_name in self.known_spells

    def can_cast_spell(self, spell_name: str) -> bool:
        """Check if character can currently cast a specific spell"""
        return (self.is_alive and 
                self.is_conscious and 
                spell_name in self.known_spells and 
                spell_name not in self.disabled_spells)

    def disable_spell(self, spell_name: str):
        """Disable a spell for the rest of the expedition (critical failure)"""
        if spell_name in self.known_spells and spell_name not in self.disabled_spells:
            self.disabled_spells.append(spell_name)

    def get_spell_count(self) -> tuple[int, int]:
        """Get (available, total) spell count"""
        if not self.can_cast_spells():
            return (0, 0)
        
        total = len(self.known_spells)
        available = len(self.get_available_spells())
        return (available, total)

    # === SPELL EFFECTS ===

    def apply_damage_shield(self, amount: int):
        """Apply damage shield effect from Ward of Vitality"""
        self.damage_shield += amount

    def apply_death_protection(self):
        """Apply death protection from Echo of Hope"""
        self.has_death_protection = True

    def apply_regeneration(self, rounds: int):
        """Apply regeneration effect from Lifebloom"""
        self.regeneration_rounds = rounds

    def process_regeneration(self) -> int:
        """Process regeneration at start of round, returns HP healed"""
        if self.regeneration_rounds > 0 and self.is_alive and self.is_conscious:
            healed = self.heal(1)
            self.regeneration_rounds -= 1
            return healed
        return 0

    # === DAMAGE AND HEALING ===

    def take_damage(self, damage: int) -> bool:
        """
        Apply damage to character, accounting for damage shield and death protection.

        Args:
            damage: Amount of damage to take

        Returns:
            True if character was just downed (hp reached 0)
        """
        if damage < 0:
            damage = 0

        # Apply damage shield first
        if self.damage_shield > 0:
            shield_absorbed = min(self.damage_shield, damage)
            self.damage_shield -= shield_absorbed
            damage -= shield_absorbed

        # Apply remaining damage to HP
        self.current_hp = max(0, self.current_hp - damage)

        # Check for death protection
        if self.current_hp <= 0 and self.has_death_protection:
            self.current_hp = 1  # Stay at 1 HP
            self.has_death_protection = False  # Protection used up
            return False

        # Check if character was just downed
        if self.current_hp <= 0 and self.is_conscious:
            self.is_conscious = False
            self.times_downed += 1

            # Perform death test (3 rolls, need 2+ successes)
            if not self._death_test():
                self.is_alive = False
                return True  # Character died

            return True  # Character was downed but survived death test

        return False  # Character was already down or survived damage

    def _death_test(self) -> bool:
        """
        Perform death test when character is downed.
        Roll 3d20, need 2+ rolls above 10 to survive.
        """
        successes = 0
        rolls = []

        for _ in range(3):
            roll = random.randint(1, 20)
            rolls.append(roll)
            if roll > 10:
                successes += 1

        survived = successes >= 2

        if not survived:
            self.death_test_failures += 1

        return survived

    def heal(self, amount: int) -> int:
        """
        Heal character (cannot exceed max HP).
        Can revive unconscious characters but not the dead.
        """
        if not self.is_alive:
            return 0  # Cannot heal the dead

        if amount < 0:
            amount = 0

        old_hp = self.current_hp
        self.current_hp = min(self.max_hp, self.current_hp + amount)

        # If healed from 0 HP, character regains consciousness
        if old_hp == 0 and self.current_hp > 0:
            self.is_conscious = True

        return self.current_hp - old_hp

    def get_ac(self) -> int:
        """Calculate character's Armor Class."""
        return 10 + self.get_grit_modifier()

    def get_stat(self, stat_name: str) -> int:
        """Get a raw stat value by name."""
        return getattr(self, stat_name, 0)

    def reset_for_expedition(self):
        """
        Reset character state for a new expedition.
        Called between expeditions to restore HP and clear temporary effects.
        """
        if not self.is_alive:
            return  # Cannot reset dead characters

        self.current_hp = self.max_hp
        self.is_conscious = True
        
        # Clear spell effects
        self.damage_shield = 0
        self.has_death_protection = False
        self.regeneration_rounds = 0
        
        # Clear all debuffs between expeditions
        self.debuff_manager.clear_all_debuffs()
        
        # Note: disabled_spells and times_downed persist between expeditions

    def get_spell_summary(self) -> str:
        """Get a summary of spell status for display"""
        if not self.can_cast_spells():
            return "No spells"

        available, total = self.get_spell_count()
        disabled = len(self.disabled_spells)
        
        if disabled > 0:
            return f"{available}/{total} spells ({disabled} disabled)"
        else:
            return f"{total} spells available"

    def __str__(self):
        """String representation for logging and debugging"""
        if not self.is_alive:
            return f"{self.name} ({self.role.value}) [DEAD]"

        consciousness = "Conscious" if self.is_conscious else "Unconscious"

        # Show spell info for casters
        spell_info = ""
        if self.can_cast_spells():
            available, total = self.get_spell_count()
            spell_info = f", {available}/{total} spells"

        # Show spell effects if any
        effects = []
        if self.damage_shield > 0:
            effects.append(f"Shield:{self.damage_shield}")
        if self.has_death_protection:
            effects.append("Protected")
        if self.regeneration_rounds > 0:
            effects.append(f"Regen:{self.regeneration_rounds}")
        
        effects_info = f" [{', '.join(effects)}]" if effects else ""
            
        # Show active debuffs if any
        debuffs_info = ""
        if self.debuff_manager.get_active_debuffs():
            debuffs_info = f" Debuffs:[{self.debuff_manager}]"

        return f"{self.name} ({self.role.value}) HP:{self.current_hp}/{self.max_hp} [{consciousness}]{spell_info}{effects_info}{debuffs_info}"


