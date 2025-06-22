"""
Debuff System for Fantasy Guild Manager
Handles all status effects that can be applied to characters or enemies
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import random


class DebuffType(Enum):
    """All possible debuff types from core mechanics"""
    POISONED = "poisoned"        # -2 all rolls, 1 damage/round
    WEAKENED = "weakened"        # -2 MIGHT rolls
    SLOWED = "slowed"           # -2 initiative, no reactions
    STUNNED = "stunned"         # Skip next turn
    CONFUSED = "confused"       # 50% hit random ally
    CURSED = "cursed"          # -2 LUCK rolls
    BLINDED = "blinded"        # -4 attack rolls
    FRIGHTENED = "frightened"   # -2 all rolls vs enemies


@dataclass
class Debuff:
    """
    Represents a single debuff effect on a character/enemy.
    
    Each debuff has a type, remaining duration, and optional severity.
    Duration decreases each round and debuff is removed when it hits 0.
    """
    debuff_type: DebuffType
    duration_remaining: int
    severity: int = 1  # For future scaling (e.g., greater poison)
    source: str = "unknown"  # What caused this debuff (for events)
    
    def tick_duration(self) -> bool:
        """
        Reduce duration by 1. Returns True if debuff expired.
        
        Returns:
            True if debuff should be removed (duration <= 0)
        """
        self.duration_remaining -= 1
        return self.duration_remaining <= 0
    
    def get_stat_modifier(self, stat_name: str) -> int:
        """
        Get the modifier this debuff applies to a specific stat.
        
        Args:
            stat_name: The stat being modified ("might", "grit", "wit", "luck")
            
        Returns:
            Negative number representing penalty to the stat
        """
        # Poisoned affects all stats
        if self.debuff_type == DebuffType.POISONED:
            return -2 * self.severity
            
        # Weakened affects might
        elif self.debuff_type == DebuffType.WEAKENED and stat_name == "might":
            return -2 * self.severity
            
        # Cursed affects luck
        elif self.debuff_type == DebuffType.CURSED and stat_name == "luck":
            return -2 * self.severity
            
        # Frightened affects all stats when fighting enemies
        elif self.debuff_type == DebuffType.FRIGHTENED:
            return -2 * self.severity
            
        # No modifier for this stat
        return 0
    
    def get_attack_modifier(self) -> int:
        """
        Get modifier to attack rolls specifically.
        
        Returns:
            Negative number representing penalty to attack rolls
        """
        if self.debuff_type == DebuffType.BLINDED:
            return -4 * self.severity
        elif self.debuff_type == DebuffType.SLOWED:
            return -2 * self.severity  # Initiative penalty affects attacks too
        return 0
    
    def blocks_actions(self) -> bool:
        """
        Check if this debuff prevents taking actions.
        
        Returns:
            True if character cannot act this turn
        """
        return self.debuff_type == DebuffType.STUNNED
    
    def causes_confusion(self) -> bool:
        """
        Check if this debuff causes confusion (hit allies).
        
        Returns:
            True if there's a chance to hit allies instead
        """
        return self.debuff_type == DebuffType.CONFUSED


class DebuffManager:
    """
    Manages all debuffs for a single character or enemy.
    
    Handles applying new debuffs, ticking durations, removing expired
    debuffs, and calculating total stat modifiers.
    """
    
    def __init__(self):
        # Store debuffs by type to prevent stacking same effect
        self.active_debuffs: Dict[DebuffType, Debuff] = {}
        self.damage_per_tick: int = 0  # For poison damage
    
    def apply_debuff(self, debuff: Debuff) -> bool:
        """
        Apply a new debuff, replacing any existing debuff of same type.
        
        Args:
            debuff: The debuff to apply
            
        Returns:
            True if this is a new debuff type, False if replacing existing
        """
        is_new = debuff.debuff_type not in self.active_debuffs
        
        # Replace any existing debuff of same type
        self.active_debuffs[debuff.debuff_type] = debuff
        
        # Update poison damage counter
        self._update_poison_damage()
        
        return is_new
    
    def tick_all_debuffs(self) -> List[Debuff]:
        """
        Reduce duration on all debuffs and remove expired ones.
        
        Returns:
            List of debuffs that just expired
        """
        expired_debuffs = []
        debuffs_to_remove = []
        
        for debuff_type, debuff in self.active_debuffs.items():
            if debuff.tick_duration():
                expired_debuffs.append(debuff)
                debuffs_to_remove.append(debuff_type)
        
        # Remove expired debuffs
        for debuff_type in debuffs_to_remove:
            del self.active_debuffs[debuff_type]
        
        # Update poison damage
        self._update_poison_damage()
        
        return expired_debuffs
    
    def get_stat_modifier(self, stat_name: str, vs_enemies: bool = True) -> int:
        """
        Calculate total modifier to a stat from all active debuffs.
        
        Args:
            stat_name: The stat being checked
            vs_enemies: Whether this roll is against enemies (for frightened)
            
        Returns:
            Total negative modifier to apply to stat
        """
        total_modifier = 0
        
        for debuff in self.active_debuffs.values():
            # Frightened only applies when fighting enemies
            if debuff.debuff_type == DebuffType.FRIGHTENED and not vs_enemies:
                continue
                
            total_modifier += debuff.get_stat_modifier(stat_name)
        
        return total_modifier
    
    def get_attack_modifier(self) -> int:
        """
        Calculate total modifier to attack rolls from all debuffs.
        
        Returns:
            Total negative modifier to apply to attack rolls
        """
        total_modifier = 0
        
        for debuff in self.active_debuffs.values():
            total_modifier += debuff.get_attack_modifier()
        
        return total_modifier
    
    def is_stunned(self) -> bool:
        """Check if character is stunned and cannot act."""
        return DebuffType.STUNNED in self.active_debuffs
    
    def is_confused(self) -> bool:
        """Check if character might hit allies due to confusion."""
        return DebuffType.CONFUSED in self.active_debuffs
    
    def get_confusion_chance(self) -> float:
        """Get chance to hit ally instead of enemy when confused."""
        if self.is_confused():
            return 0.5  # 50% chance from core rules
        return 0.0
    
    def get_poison_damage(self) -> int:
        """Get damage to take this round from poison effects."""
        return self.damage_per_tick
    
    def has_debuff(self, debuff_type: DebuffType) -> bool:
        """Check if character has a specific debuff."""
        return debuff_type in self.active_debuffs
    
    def get_active_debuffs(self) -> List[Debuff]:
        """Get list of all currently active debuffs."""
        return list(self.active_debuffs.values())
    
    def clear_all_debuffs(self):
        """Remove all debuffs (for recovery between expeditions)."""
        self.active_debuffs.clear()
        self.damage_per_tick = 0
    
    def _update_poison_damage(self):
        """Recalculate poison damage per tick based on active poison debuffs."""
        self.damage_per_tick = 0
        
        if DebuffType.POISONED in self.active_debuffs:
            poison = self.active_debuffs[DebuffType.POISONED]
            self.damage_per_tick = 1 * poison.severity  # 1 damage per severity level
    
    def __str__(self) -> str:
        """String representation for debugging."""
        if not self.active_debuffs:
            return "None"
        
        debuff_names = [d.debuff_type.value for d in self.active_debuffs.values()]
        return ', '.join(debuff_names)


# Utility functions for common debuff creation
def create_trap_debuff(rng: random.Random, duration: int = None) -> Debuff:
    """
    Create a random debuff from a trap trigger.
    
    Args:
        rng: Random number generator (for deterministic results)
        duration: Override duration, otherwise rolls 1d4
        
    Returns:
        Random debuff appropriate for trap effects
    """
    if duration is None:
        duration = rng.randint(1, 4)  # 1d4 rounds
    
    # Roll 1d8 for debuff type (from core rules)
    debuff_roll = rng.randint(1, 8)
    
    debuff_types = [
        DebuffType.POISONED,   # 1
        DebuffType.WEAKENED,   # 2
        DebuffType.SLOWED,     # 3
        DebuffType.STUNNED,    # 4
        DebuffType.CONFUSED,   # 5
        DebuffType.CURSED,     # 6
        DebuffType.BLINDED,    # 7
        DebuffType.FRIGHTENED  # 8
    ]
    
    debuff_type = debuff_types[debuff_roll - 1]
    
    return Debuff(
        debuff_type=debuff_type,
        duration_remaining=duration,
        source="trap"
    )


# Test the debuff system with actual Character integration
if __name__ == "__main__":
    import sys
    import os
    
    # Add parent directory to path so we can import models
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from models.character import Character, CharacterRole
    
    print("Testing Debuff System with Character Integration")
    print("=" * 50)
    
    # Create a test character (striker with decent stats)
    aldric = Character(
        name="Aldric",
        role=CharacterRole.STRIKER,
        guild_id=1,
        might=12,
        grit=10,
        wit=8,
        luck=9
    )
    
    # Add debuff manager to character (we'll need to add this to Character class)
    aldric.debuff_manager = DebuffManager()
    
    print(f"Created character: {aldric.name}")
    print(f"Base stats - Might: {aldric.might}, Grit: {aldric.grit}, Wit: {aldric.wit}, Luck: {aldric.luck}")
    print(f"Current HP: {aldric.current_hp}/{aldric.max_hp}")
    
    # Test applying debuffs
    print("\n--- Applying Debuffs ---")
    poison = Debuff(DebuffType.POISONED, 3, source="spider bite")
    weakness = Debuff(DebuffType.WEAKENED, 2, source="cursed sword")
    blindness = Debuff(DebuffType.BLINDED, 2, source="flash bomb")
    
    aldric.debuff_manager.apply_debuff(poison)
    aldric.debuff_manager.apply_debuff(weakness)
    aldric.debuff_manager.apply_debuff(blindness)
    
    print(f"Applied debuffs: {aldric.debuff_manager}")
    
    # Test stat modifications
    print("\n--- Stat Modifications ---")
    print(f"Base might: {aldric.might}")
    print(f"Might with debuffs: {aldric.might + aldric.debuff_manager.get_stat_modifier('might')}")
    print(f"Base luck: {aldric.luck}")
    print(f"Luck with debuffs: {aldric.luck + aldric.debuff_manager.get_stat_modifier('luck')}")
    
    # Test attack modifiers
    print(f"\nAttack roll modifiers: {aldric.debuff_manager.get_attack_modifier()}")
    print(f"Sample attack roll: 1d20{aldric.debuff_manager.get_attack_modifier():+d} + {aldric.might} (might)")
    
    # Test action blocking
    print(f"\nCan act this turn: {not aldric.debuff_manager.is_stunned()}")
    print(f"Might hit allies: {aldric.debuff_manager.is_confused()}")
    
    # Simulate combat rounds with poison damage
    print("\n--- Combat Round Simulation ---")
    for round_num in range(1, 5):
        print(f"\nRound {round_num}:")
        
        # Take poison damage
        poison_damage = aldric.debuff_manager.get_poison_damage()
        if poison_damage > 0:
            aldric.take_damage(poison_damage)
            print(f"  Poison damage: {poison_damage} (HP: {aldric.current_hp}/{aldric.max_hp})")
        
        # Tick debuff durations
        expired = aldric.debuff_manager.tick_all_debuffs()
        if expired:
            print(f"  Debuffs expired: {[d.debuff_type.value for d in expired]}")
        
        print(f"  Active debuffs: {aldric.debuff_manager}")
        print(f"  Current modifiers - Might: {aldric.debuff_manager.get_stat_modifier('might'):+d}, Attack: {aldric.debuff_manager.get_attack_modifier():+d}")
        
        if not aldric.debuff_manager.get_active_debuffs():
            print("  All debuffs cleared!")
            break
    
    # Test random trap debuff
    print("\n--- Random Trap Debuff Test ---")
    rng = random.Random(12345)
    
    for i in range(3):
        trap_debuff = create_trap_debuff(rng)
        print(f"Trap {i+1}: {trap_debuff.debuff_type.value} for {trap_debuff.duration_remaining} rounds")
        
        # Show what this would do to our character
        temp_manager = DebuffManager()
        temp_manager.apply_debuff(trap_debuff)
        might_mod = temp_manager.get_stat_modifier('might')
        attack_mod = temp_manager.get_attack_modifier()
        
        effects = []
        if might_mod != 0:
            effects.append(f"might {might_mod:+d}")
        if attack_mod != 0:
            effects.append(f"attack {attack_mod:+d}")
        if temp_manager.is_stunned():
            effects.append("stunned")
        if temp_manager.is_confused():
            effects.append("confused")
        if temp_manager.get_poison_damage() > 0:
            effects.append(f"{temp_manager.get_poison_damage()} poison/round")
        
        if effects:
            print(f"         Effects: {', '.join(effects)}")
        else:
            print(f"         Effects: none")
    
    print(f"\nFinal character state: HP {aldric.current_hp}/{aldric.max_hp}")
    print("Debuff system integration test complete!")
