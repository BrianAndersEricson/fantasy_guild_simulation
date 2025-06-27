"""
Enemy Model for Fantasy Guild Manager

Represents individual enemy instances in combat, created from enemy types.
Tracks HP, status effects, and special abilities during encounters.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

from models.enemy_types import (
    EnemyType, SpecialAbility, BossType, BossModifier,
    get_enemies_for_floor, BOSS_MODIFIERS
)


@dataclass
class StatusEffect:
    """Represents a status effect on a character"""
    effect_type: SpecialAbility
    duration: int  # Number of actions/rounds remaining
    
    def tick(self) -> bool:
        """Reduce duration by 1. Returns True if effect expired."""
        self.duration -= 1
        return self.duration <= 0


@dataclass
class Enemy:
    """
    Represents an individual enemy in combat.
    
    Created from an EnemyType with stats calculated based on floor level.
    """
    # Identity
    name: str
    enemy_type: EnemyType
    enemy_number: int  # Which enemy in the group (1, 2, 3, etc.)
    
    # Combat stats
    max_hp: int
    current_hp: int
    ac: int
    might: int
    damage_die: int
    
    # Boss properties
    is_boss: bool = False
    boss_ability: Optional[BossType] = None
    boss_triggered: bool = False  # For one-time boss abilities
    
    # Combat state
    status_effects: List[StatusEffect] = field(default_factory=list)
    
    @classmethod
    def create_from_type(cls, enemy_type: EnemyType, floor: int, 
                        enemy_number: int, rng: random.Random,
                        is_boss: bool = False, boss_modifier: Optional[BossModifier] = None) -> 'Enemy':
        """
        Factory method to create an enemy from an enemy type.
        
        Args:
            enemy_type: The type of enemy to create
            floor: Current dungeon floor (affects stats)
            enemy_number: Which enemy in the encounter (1, 2, etc.)
            rng: Seeded random number generator
            is_boss: Whether this is a boss enemy
            boss_modifier: Boss modifications to apply
            
        Returns:
            Fully initialized Enemy instance
        """
        # Calculate base stats
        tier = enemy_type.tier.value
        
        # HP calculation
        if tier >= 4 and enemy_type.hp_die == 4:  # Special 2d4 case
            hp = floor * 5 + rng.randint(1, 4) + rng.randint(1, 4)
        else:
            hp = floor * 5 + rng.randint(1, enemy_type.hp_die)
        
        # AC calculation
        if tier >= 4:
            base_ac = 10 + (floor // 2)
        else:
            base_ac = 10 + floor
        ac = base_ac + enemy_type.ac_modifier
        
        # Might calculation
        if tier >= 4:
            might = floor // 2
        else:
            might = floor
        
        # Damage die
        damage_die = enemy_type.damage_die
        
        # Apply boss modifiers if applicable
        boss_ability = None
        if is_boss and boss_modifier:
            mods = boss_modifier.apply_to_enemy(enemy_type)
            hp = int(hp * mods['hp_multiplier'])
            ac += mods['ac_bonus']
            might += mods['might_bonus']
            boss_ability = mods['boss_ability']
            
        # Create name
        if is_boss:
            name = f"{boss_modifier.boss_type.value.title()} {enemy_type.name}"
        else:
            name = f"{enemy_type.name} {enemy_number}"
        
        return cls(
            name=name,
            enemy_type=enemy_type,
            enemy_number=enemy_number,
            max_hp=hp,
            current_hp=hp,
            ac=ac,
            might=might,
            damage_die=damage_die,
            is_boss=is_boss,
            boss_ability=boss_ability
        )
    
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
    
    def heal(self, amount: int) -> int:
        """
        Heal the enemy (for regeneration).
        
        Returns actual amount healed.
        """
        old_hp = self.current_hp
        self.current_hp = min(self.max_hp, self.current_hp + amount)
        return self.current_hp - old_hp
    
    def is_bloodied(self) -> bool:
        """Check if enemy is below half HP (for boss triggers)"""
        return self.current_hp <= self.max_hp // 2
    
    def add_status_effect(self, effect_type: SpecialAbility, duration: int):
        """Add a status effect to this enemy"""
        # Don't add duplicate effects - refresh duration instead
        for effect in self.status_effects:
            if effect.effect_type == effect_type:
                effect.duration = max(effect.duration, duration)
                return
        
        self.status_effects.append(StatusEffect(effect_type, duration))
    
    def tick_status_effects(self):
        """Process status effects, removing expired ones"""
        self.status_effects = [e for e in self.status_effects if not e.tick()]
    
    def has_status_effect(self, effect_type: SpecialAbility) -> bool:
        """Check if enemy has a specific status effect"""
        return any(e.effect_type == effect_type for e in self.status_effects)
    
    def get_effective_ac(self) -> int:
        """Get AC including any status effect modifiers"""
        ac = self.ac
        
        # Blinded enemies are easier to hit
        if self.has_status_effect(SpecialAbility.BLIND):
            ac -= 2
            
        return max(0, ac)
    
    def get_effective_might(self) -> int:
        """Get might including any status effect modifiers"""
        might = self.might
        
        # Weakened enemies hit less hard
        if self.has_status_effect(SpecialAbility.WEAKEN):
            might -= 2
            
        # Boss aura affects nearby enemies (handled in combat resolver)
        
        return max(0, might)
    
    def get_status_summary(self) -> str:
        """Get a summary of active status effects"""
        if not self.status_effects:
            return ""
        
        effects = [f"{e.effect_type.value}({e.duration})" for e in self.status_effects]
        return f" [{', '.join(effects)}]"
    
    def __str__(self):
        """String representation for debugging"""
        status = "Alive" if self.is_alive() else "Dead"
        boss_marker = " [BOSS]" if self.is_boss else ""
        effects = self.get_status_summary()
        return f"{self.name}{boss_marker} HP: {self.current_hp}/{self.max_hp} AC: {self.ac}{effects} [{status}]"


def create_encounter(floor: int, enemy_count: int, is_boss_room: bool,
                    rng: random.Random) -> List[Enemy]:
    """
    Create a complete enemy encounter for a room.
    
    Args:
        floor: Current dungeon floor
        enemy_count: Number of enemies to create
        is_boss_room: Whether this is a boss encounter
        rng: Seeded random number generator
        
    Returns:
        List of Enemy instances for the encounter
    """
    enemies = []
    available_types = get_enemies_for_floor(floor)
    
    if is_boss_room and enemy_count > 0:
        # First enemy is the boss
        enemy_type = rng.choice(available_types)
        boss_modifier = rng.choice(BOSS_MODIFIERS)
        
        boss = Enemy.create_from_type(
            enemy_type=enemy_type,
            floor=floor,
            enemy_number=1,
            rng=rng,
            is_boss=True,
            boss_modifier=boss_modifier
        )
        enemies.append(boss)
        
        # Rest are minions (if any)
        for i in range(2, enemy_count + 1):
            enemy_type = rng.choice(available_types)
            minion = Enemy.create_from_type(
                enemy_type=enemy_type,
                floor=floor,
                enemy_number=i,
                rng=rng,
                is_boss=False
            )
            enemies.append(minion)
    else:
        # Regular encounter - random enemy types
        for i in range(1, enemy_count + 1):
            enemy_type = rng.choice(available_types)
            enemy = Enemy.create_from_type(
                enemy_type=enemy_type,
                floor=floor,
                enemy_number=i,
                rng=rng,
                is_boss=False
            )
            enemies.append(enemy)
    
    return enemies


# === Test the enemy system ===
if __name__ == "__main__":
    print("Testing Enemy System...")
    print("=" * 60)
    
    rng = random.Random(12345)
    
    # Test creating enemies for different floors
    test_floors = [1, 3, 5, 7, 9]
    
    for floor in test_floors:
        print(f"\n=== FLOOR {floor} ===")
        
        # Regular encounter
        print("\nRegular Encounter (3 enemies):")
        enemies = create_encounter(floor, 3, False, rng)
        for enemy in enemies:
            print(f"  {enemy}")
        
        # Boss encounter
        print("\nBoss Encounter (1 boss + 2 minions):")
        boss_enemies = create_encounter(floor, 3, True, rng)
        for enemy in boss_enemies:
            print(f"  {enemy}")
    
    # Test status effects
    print("\n=== STATUS EFFECT TEST ===")
    test_enemy = enemies[0]
    print(f"Starting: {test_enemy}")
    
    test_enemy.add_status_effect(SpecialAbility.POISON, 3)
    test_enemy.add_status_effect(SpecialAbility.SLOW, 2)
    print(f"After effects: {test_enemy}")
    
    test_enemy.tick_status_effects()
    print(f"After 1 tick: {test_enemy}")
    
    test_enemy.tick_status_effects()
    print(f"After 2 ticks: {test_enemy}")
    
    print("\n✓ Enemy system is working!")
