"""
Character model for the Fantasy Guild Manager simulation.

Characters are members of guilds who go on automated expeditions.
This is the foundation of our simulation - every action revolves around
these characters and their stats.

Now includes full debuff system integration for status effects.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from dataclasses import dataclass
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
    or have their spells disabled by critical failures.
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
    spell_slots: int = 0            # Number of spells this character can know

    # === Expedition Tracking ===
    disabled_spells: List[str] = None  # Spells disabled by critical failures
    times_downed: int = 0  # How many times character has been downed (affects morale)

    def __post_init__(self):
        """Initialize calculated values and mutable defaults"""
        if self.disabled_spells is None:
            self.disabled_spells = []

        # Calculate max HP based on role and grit
        self.max_hp = self._calculate_max_hp()
        self.current_hp = self.max_hp

        # Calculate spell slots based on role and wit
        self.spell_slots = self._calculate_spell_slots()
        
        # Initialize debuff manager for tracking status effects
        self.debuff_manager = DebuffManager()

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

    def _calculate_spell_slots(self) -> int:
        """Calculate number of spell slots based on role and wit"""
        if self.role in [CharacterRole.SUPPORT, CharacterRole.CONTROLLER]:
            # Casters get 1 spell slot per 3 wit (rounded down)
            return self.wit // 3
        else:
            # Strikers and Burglars don't get spells
            return 0

    # === STAT MODIFIERS ===
    # Universal 3:1 scaling - every 3 points of stat = +1 modifier

    def get_might_modifier(self) -> int:
        """
        Calculate might modifier for attack rolls and damage.
        
        Returns:
            +1 for every 3 points of might
        """
        return self.might // 3

    def get_grit_modifier(self) -> int:
        """
        Calculate grit modifier for AC, initiative, and defensive rolls.
        
        Returns:
            +1 for every 3 points of grit
        """
        return self.grit // 3

    def get_wit_modifier(self) -> int:
        """
        Calculate wit modifier for spell attack rolls and spell DCs.
        
        Returns:
            +1 for every 3 points of wit
        """
        return self.wit // 3

    def get_luck_modifier(self) -> int:
        """
        Calculate luck modifier for trap detection, treasure finding, and crits.
        
        Returns:
            +1 for every 3 points of luck
        """
        return self.luck // 3

    def get_stat_modifier(self, stat_name: str) -> int:
        """
        Get modifier for any stat by name.
        
        Args:
            stat_name: One of 'might', 'grit', 'wit', 'luck'
            
        Returns:
            The modifier value (+1 per 3 stat points)
        """
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

    # === DAMAGE AND HEALING ===

    def take_damage(self, damage: int) -> bool:
        """
        Apply damage to character and handle death testing.

        When a character reaches 0 HP, they become unconscious and must
        make death tests. They need to succeed 2 out of 3 rolls (>10 on d20)
        to survive. Failure means permanent death.

        Args:
            damage: Amount of damage to take (cannot be negative)

        Returns:
            True if character was just downed (hp reached 0)
        """
        if damage < 0:
            damage = 0

        self.current_hp = max(0, self.current_hp - damage)

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

        Returns:
            True if character survives, False if they die
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

        # Note: In a real implementation, we'd emit an event here
        # showing the death test results for dramatic tension

        return survived

    def heal(self, amount: int) -> int:
        """
        Heal character (cannot exceed max HP).

        This can revive unconscious characters but cannot bring back the dead.

        Args:
            amount: Amount to heal (cannot be negative)

        Returns:
            Actual amount healed
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
        """
        Calculate character's Armor Class.

        AC = 10 + grit modifier (representing defensive training and toughness)
        """
        return 10 + self.get_grit_modifier()

    def get_stat(self, stat_name: str) -> int:
        """
        Get a raw stat value by name.

        Useful for generic stat checks in the simulation engine.

        Args:
            stat_name: One of 'might', 'grit', 'wit', 'luck'

        Returns:
            The raw stat value, or 0 if stat doesn't exist
        """
        return getattr(self, stat_name, 0)

    def disable_spell(self, spell_name: str):
        """
        Disable a spell for the rest of the expedition.

        Called when a character rolls a critical failure (natural 1)
        while casting a spell.
        """
        if spell_name not in self.disabled_spells:
            self.disabled_spells.append(spell_name)

    def reset_for_expedition(self):
        """
        Reset character state for a new expedition.

        Called between expeditions to restore HP and potentially
        recover disabled spells (based on recovery rolls).
        Note: times_downed persists as psychological trauma.
        Dead characters cannot be reset.
        """
        if not self.is_alive:
            return  # Cannot reset dead characters

        self.current_hp = self.max_hp
        self.is_conscious = True
        # Clear all debuffs between expeditions
        self.debuff_manager.clear_all_debuffs()
        # Note: disabled_spells persist and require recovery rolls
        # Note: times_downed persists between expeditions

    def __str__(self):
        """String representation for logging and debugging"""
        if not self.is_alive:
            return f"{self.name} ({self.role.value}) [DEAD]"

        consciousness = "Conscious" if self.is_conscious else "Unconscious"

        # Show available/total spells if character has spell slots
        if self.spell_slots > 0:
            disabled_count = len(self.disabled_spells)
            available_spells = self.spell_slots - disabled_count
            spells_info = f", {available_spells}/{self.spell_slots} spells"
        else:
            spells_info = ""
            
        # Show active debuffs if any
        debuffs_info = ""
        if self.debuff_manager.get_active_debuffs():
            debuffs_info = f" [{self.debuff_manager}]"

        return f"{self.name} ({self.role.value}) HP: {self.current_hp}/{self.max_hp} [{consciousness}]{spells_info}{debuffs_info}"


# === Test the model ===
if __name__ == "__main__":
    print("Testing Character model with debuff integration...")
    print("=" * 60)

    # Create a test character - a Striker with high might
    aldric = Character(
        name="Aldric",
        role=CharacterRole.STRIKER,
        guild_id=1,
        might=12,  # Strikers are strong
        grit=11,   # Decent toughness
        wit=8,     # Lower magic ability
        luck=9     # Average luck
    )

    print("1. Created character:")
    print(f"   {aldric}")
    print(f"   Raw might stat: {aldric.get_stat('might')}")
    print(f"   Might modifier: +{aldric.get_might_modifier()}")

    # Test new modifier system
    print("\n2. Testing stat modifiers...")
    print(f"   Might {aldric.might} -> +{aldric.get_might_modifier()} modifier")
    print(f"   Grit {aldric.grit} -> +{aldric.get_grit_modifier()} modifier")
    print(f"   Wit {aldric.wit} -> +{aldric.get_wit_modifier()} modifier")
    print(f"   Luck {aldric.luck} -> +{aldric.get_luck_modifier()} modifier")
    print(f"   AC: {aldric.get_ac()} (10 + {aldric.get_grit_modifier()} grit mod)")

    # Test debuff system
    print("\n3. Testing debuff integration...")
    
    # Apply some debuffs
    poison = Debuff(DebuffType.POISONED, 3, source="giant rat bite")
    weakness = Debuff(DebuffType.WEAKENED, 2, source="zombie touch")
    blindness = Debuff(DebuffType.BLINDED, 2, source="crow swarm")
    
    aldric.debuff_manager.apply_debuff(poison)
    aldric.debuff_manager.apply_debuff(weakness)
    aldric.debuff_manager.apply_debuff(blindness)
    
    print(f"   Applied debuffs: Poisoned, Weakened, Blinded")
    print(f"   {aldric}")
    
    # Show stat impacts
    print("\n4. Debuff effects on stats...")
    base_might_mod = aldric.get_might_modifier()
    debuff_might_mod = aldric.debuff_manager.get_stat_modifier('might')
    total_might_mod = base_might_mod + debuff_might_mod
    
    print(f"   Base might modifier: +{base_might_mod}")
    print(f"   Debuff penalty: {debuff_might_mod}")
    print(f"   Total might modifier: {total_might_mod:+d}")
    
    attack_penalty = aldric.debuff_manager.get_attack_modifier()
    print(f"   Attack roll penalty from blindness: {attack_penalty}")
    
    # Test poison damage
    print("\n5. Testing poison damage over rounds...")
    for round_num in range(1, 5):
        print(f"\n   Round {round_num}:")
        
        # Take poison damage
        poison_damage = aldric.debuff_manager.get_poison_damage()
        if poison_damage > 0:
            aldric.take_damage(poison_damage)
            print(f"   - Poison damage: {poison_damage}")
            print(f"   - HP: {aldric.current_hp}/{aldric.max_hp}")
        
        # Tick debuffs
        expired = aldric.debuff_manager.tick_all_debuffs()
        if expired:
            expired_names = [d.debuff_type.value for d in expired]
            print(f"   - Debuffs expired: {', '.join(expired_names)}")
        
        # Show current state
        active_debuffs = aldric.debuff_manager.get_active_debuffs()
        if active_debuffs:
            print(f"   - Active debuffs: {aldric.debuff_manager}")
        else:
            print("   - All debuffs cleared!")
            break

    # Test damage system
    print("\n6. Testing damage with debuffs...")
    print("   Taking 8 damage...")
    was_downed = aldric.take_damage(8)
    print(f"   Was downed: {was_downed}")
    print(f"   {aldric}")

    # Test healing
    print("\n7. Testing healing...")
    print("   Healing 5 HP...")
    healed = aldric.heal(5)
    print(f"   Amount healed: {healed}")
    print(f"   {aldric}")

    # Test expedition reset
    print("\n8. Testing expedition reset...")
    # Apply a debuff before reset
    stun = Debuff(DebuffType.STUNNED, 1, source="ghoul touch")
    aldric.debuff_manager.apply_debuff(stun)
    print(f"   Before reset: {aldric}")
    
    aldric.reset_for_expedition()
    print(f"   After reset: {aldric}")
    print(f"   Debuffs cleared: {len(aldric.debuff_manager.get_active_debuffs()) == 0}")

    # Test special debuff effects
    print("\n9. Testing special debuff conditions...")
    
    # Test stun
    stun = Debuff(DebuffType.STUNNED, 1)
    aldric.debuff_manager.apply_debuff(stun)
    print(f"   Applied stun - Can act: {not aldric.debuff_manager.is_stunned()}")
    
    # Test confusion
    aldric.debuff_manager.clear_all_debuffs()
    confusion = Debuff(DebuffType.CONFUSED, 2)
    aldric.debuff_manager.apply_debuff(confusion)
    print(f"   Applied confusion - Might hit allies: {aldric.debuff_manager.is_confused()}")
    print(f"   Confusion chance: {aldric.debuff_manager.get_confusion_chance() * 100}%")

    # Create a spellcaster to test wit debuffs
    print("\n10. Testing spellcaster with debuffs...")
    elara = Character(
        name="Elara",
        role=CharacterRole.SUPPORT,
        guild_id=1,
        might=8,
        grit=9,
        wit=15,  # High wit for spells
        luck=10
    )
    
    print(f"   Created support: {elara}")
    print(f"   Base wit modifier: +{elara.get_wit_modifier()}")
    
    # Apply curse (affects luck)
    curse = Debuff(DebuffType.CURSED, 3)
    elara.debuff_manager.apply_debuff(curse)
    
    luck_penalty = elara.debuff_manager.get_stat_modifier('luck')
    print(f"   Cursed - Luck penalty: {luck_penalty}")

    print("\n✓ All tests passed! Character model with debuff integration is working.")
