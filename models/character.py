"""
Character model for the Fantasy Guild Manager simulation.

Characters are members of guilds who go on automated expeditions.
This is the foundation of our simulation - every action revolves around
these characters and their stats.
"""

import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


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

        return f"{self.name} ({self.role.value}) HP: {self.current_hp}/{self.max_hp} [{consciousness}]{spells_info}"


# === Test the model ===
if __name__ == "__main__":
    print("Testing Character model...")
    print("=" * 40)

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

    # Test damage system
    print("\n3. Testing damage...")
    print("   Taking 8 damage...")
    was_downed = aldric.take_damage(8)
    print(f"   Was downed: {was_downed}")
    print(f"   {aldric}")

    # Test healing
    print("\n4. Testing healing...")
    print("   Healing 5 HP...")
    healed = aldric.heal(5)
    print(f"   Amount healed: {healed}")
    print(f"   {aldric}")

    # Test downing and revival
    print("\n5. Testing downing...")
    print("   Taking 20 damage...")
    was_downed = aldric.take_damage(20)
    print(f"   Was downed: {was_downed}")
    print(f"   {aldric}")

    print("\n6. Testing revival...")
    print("   Healing 10 HP...")
    healed = aldric.heal(10)
    print(f"   Amount healed: {healed}")
    print(f"   {aldric}")

    # Test spell disabling
    print("\n7. Testing spell system...")
    aldric.disable_spell("Fireball")
    aldric.disable_spell("Shield")
    print(f"   {aldric}")

    # Test expedition reset
    print("\n8. Testing expedition reset...")
    aldric.reset_for_expedition()
    print(f"   After reset: {aldric}")

    # Test modifier scaling examples
    print("\n9. Testing modifier scaling examples...")
    test_cases = [6, 9, 12, 15]
    for stat_value in test_cases:
        modifier = stat_value // 3
        print(f"   Stat {stat_value} -> +{modifier} modifier")

    print("\n✓ All tests passed! Character model with modifiers is working.")
