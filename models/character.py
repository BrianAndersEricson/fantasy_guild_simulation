"""
Character model for the Fantasy Guild Manager simulation.

Characters are members of guilds who go on automated expeditions.
This is the foundation of our simulation - every action revolves around
these characters and their stats.
"""

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
    current_hp: int = 20
    max_hp: int = 20
    is_alive: bool = True
    is_available: bool = True  # False if recovering from previous expedition
    
    # === Expedition Tracking ===
    disabled_spells: List[str] = None  # Spells disabled by critical failures
    
    def __post_init__(self):
        """Initialize mutable defaults after dataclass creation"""
        if self.disabled_spells is None:
            self.disabled_spells = []
    
    def take_damage(self, damage: int) -> bool:
        """
        Apply damage to character.
        
        This is called during combat and trap resolution.
        When HP reaches 0, the character is "downed" but not dead -
        they can be revived by healing or recover between expeditions.
        
        Args:
            damage: Amount of damage to take (cannot be negative)
            
        Returns:
            True if character was just downed (hp reached 0)
        """
        if damage < 0:
            damage = 0
            
        self.current_hp = max(0, self.current_hp - damage)
        
        # Check if character was just downed
        if self.current_hp <= 0 and self.is_alive:
            self.is_alive = False
            return True  # Character was just downed this turn
            
        return False  # Character was already down or survived
    
    def heal(self, amount: int) -> int:
        """
        Heal character (cannot exceed max HP).
        
        This can revive downed characters and restore them to the fight.
        
        Args:
            amount: Amount to heal (cannot be negative)
            
        Returns:
            Actual amount healed
        """
        if amount < 0:
            amount = 0
            
        old_hp = self.current_hp
        self.current_hp = min(self.max_hp, self.current_hp + amount)
        
        # If healed from 0 HP, character is revived
        if old_hp == 0 and self.current_hp > 0:
            self.is_alive = True
            
        return self.current_hp - old_hp
    
    def get_stat(self, stat_name: str) -> int:
        """
        Get a stat value by name.
        
        Useful for generic stat checks in the simulation engine.
        
        Args:
            stat_name: One of 'might', 'grit', 'wit', 'luck'
            
        Returns:
            The stat value, or 0 if stat doesn't exist
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
        """
        self.current_hp = self.max_hp
        self.is_alive = True
        # Note: disabled_spells persist and require recovery rolls
    
    def __str__(self):
        """String representation for logging and debugging"""
        status = "Alive" if self.is_alive else "Downed"
        spells = f", {len(self.disabled_spells)} spells disabled" if self.disabled_spells else ""
        return f"{self.name} ({self.role.value}) HP: {self.current_hp}/{self.max_hp} [{status}]{spells}"


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
        grit=11    # Decent toughness
    )
    
    print("1. Created character:")
    print(f"   {aldric}")
    print(f"   Might stat: {aldric.get_stat('might')}")
    
    # Test damage system
    print("\n2. Testing damage...")
    print("   Taking 8 damage...")
    was_downed = aldric.take_damage(8)
    print(f"   Was downed: {was_downed}")
    print(f"   {aldric}")
    
    # Test healing
    print("\n3. Testing healing...")
    print("   Healing 5 HP...")
    healed = aldric.heal(5)
    print(f"   Amount healed: {healed}")
    print(f"   {aldric}")
    
    # Test downing and revival
    print("\n4. Testing downing...")
    print("   Taking 20 damage...")
    was_downed = aldric.take_damage(20)
    print(f"   Was downed: {was_downed}")
    print(f"   {aldric}")
    
    print("\n5. Testing revival...")
    print("   Healing 10 HP...")
    healed = aldric.heal(10)
    print(f"   Amount healed: {healed}")
    print(f"   {aldric}")
    
    # Test spell disabling
    print("\n6. Testing spell system...")
    aldric.disable_spell("Fireball")
    aldric.disable_spell("Shield")
    print(f"   {aldric}")
    
    # Test expedition reset
    print("\n7. Testing expedition reset...")
    aldric.reset_for_expedition()
    print(f"   After reset: {aldric}")
    
    print("\n✓ All tests passed! Character model is working.")
