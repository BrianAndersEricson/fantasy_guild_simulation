"""
Enemy Types for Fantasy Guild Manager

Defines all enemy types with their special abilities and tier-based scaling.
Enemies become progressively more dangerous as parties delve deeper.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any


class EnemyTier(Enum):
    """Enemy tiers determine which enemies appear on which floors"""
    TIER_1 = 1  # Floors 1-2
    TIER_2 = 2  # Floors 3-4
    TIER_3 = 3  # Floors 5-6
    TIER_4 = 4  # Floors 7-8
    TIER_5 = 5  # Floors 9-10


class SpecialAbility(Enum):
    """Special abilities that enemies can inflict on hit"""
    NONE = "none"
    POISON = "poison"           # -2 all rolls, 1 damage/round
    SLOW = "slow"              # -2 initiative, no reactions
    WEAKEN = "weaken"          # -2 MIGHT rolls
    BLIND = "blind"            # -4 attack rolls
    STUN = "stun"              # Skip next turn
    FRIGHTEN = "frighten"      # -2 all rolls vs enemies
    CURSE = "curse"            # -2 LUCK rolls
    BURN = "burn"              # Same as poison (different flavor)


@dataclass
class EnemyType:
    """
    Defines a type of enemy with base stats and special abilities.
    
    Actual stats are calculated based on floor level when spawned.
    """
    name: str
    tier: EnemyTier
    
    # Base stat modifiers (applied to floor-based calculations)
    hp_die: int = 4           # d4, d6, d8, d10, etc.
    ac_modifier: int = 0      # Adjustment to base AC
    damage_die: int = 4       # Base damage die
    
    # Special ability (if any)
    special_ability: SpecialAbility = SpecialAbility.NONE
    special_trigger: int = 3  # Roll this or higher on d4 to trigger
    
    # Flavor text
    description: str = ""
    
    def get_hp_formula(self, floor: int) -> str:
        """Get HP formula for this enemy type"""
        if self.tier.value >= 4:  # Tier 4+ uses 2 dice
            return f"{floor} × 5 + 2d{self.hp_die}"
        else:
            return f"{floor} × 5 + 1d{self.hp_die}"
    
    def get_ac_formula(self, floor: int) -> str:
        """Get AC formula for this enemy type"""
        base = f"10 + {floor}"
        if self.tier.value >= 4:  # Tier 4+ uses floor/2
            base = f"10 + {floor//2}"
        
        if self.ac_modifier > 0:
            return f"{base} + {self.ac_modifier}"
        elif self.ac_modifier < 0:
            return f"{base} - {abs(self.ac_modifier)}"
        else:
            return base
    
    def get_damage_formula(self, floor: int) -> str:
        """Get damage formula for this enemy type"""
        if self.tier.value >= 4:  # Tier 4+ uses different scaling
            if self.damage_die == 4:  # Special case for 2d4
                return f"2d4 + {floor//2}"
            else:
                return f"1d{self.damage_die} + {floor//2}"
        else:
            return f"1d{self.damage_die} + {floor}"


# === TIER 1 ENEMIES (Floors 1-2) ===

GIANT_RAT = EnemyType(
    name="Giant Rat",
    tier=EnemyTier.TIER_1,
    hp_die=4,
    ac_modifier=0,
    damage_die=4,
    special_ability=SpecialAbility.POISON,
    description="A rat the size of a small dog, with yellowed fangs dripping venom"
)

SLIME = EnemyType(
    name="Slime",
    tier=EnemyTier.TIER_1,
    hp_die=4,
    ac_modifier=-1,  # Sluggish
    damage_die=4,
    special_ability=SpecialAbility.SLOW,
    description="A translucent blob of acidic goo that leaves sticky residue"
)

GIANT_BAT = EnemyType(
    name="Giant Bat",
    tier=EnemyTier.TIER_1,
    hp_die=4,
    ac_modifier=2,  # Flying
    damage_die=4,
    special_ability=SpecialAbility.NONE,
    description="A massive bat with a wingspan of six feet, swooping from the darkness"
)

CAVE_BEETLE = EnemyType(
    name="Cave Beetle",
    tier=EnemyTier.TIER_1,
    hp_die=4,
    ac_modifier=1,  # Hard shell
    damage_die=4,
    special_ability=SpecialAbility.NONE,
    description="An oversized beetle with a chitinous shell that clicks menacingly"
)

# === TIER 2 ENEMIES (Floors 3-4) ===

SKELETON = EnemyType(
    name="Skeleton",
    tier=EnemyTier.TIER_2,
    hp_die=6,
    ac_modifier=2,  # Bones deflect blows
    damage_die=6,
    special_ability=SpecialAbility.NONE,
    description="Animated bones held together by dark magic, wielding ancient weapons"
)

ZOMBIE = EnemyType(
    name="Zombie",
    tier=EnemyTier.TIER_2,
    hp_die=6,
    ac_modifier=-1,  # Slow
    damage_die=6,
    special_ability=SpecialAbility.WEAKEN,
    description="A shambling corpse reeking of decay, moaning for flesh"
)

CARRION_CROW_SWARM = EnemyType(
    name="Carrion Crow Swarm",
    tier=EnemyTier.TIER_2,
    hp_die=6,
    ac_modifier=1,  # Hard to hit swarm
    damage_die=6,
    special_ability=SpecialAbility.BLIND,
    description="A murder of crows that attacks as one, pecking at eyes and exposed flesh"
)

SPITTING_SPIDER = EnemyType(
    name="Spitting Spider",
    tier=EnemyTier.TIER_2,
    hp_die=6,
    ac_modifier=0,
    damage_die=6,
    special_ability=SpecialAbility.POISON,
    description="A hairy arachnid the size of a dinner plate that spits acidic venom"
)

# === TIER 3 ENEMIES (Floors 5-6) ===

GHOUL = EnemyType(
    name="Ghoul",
    tier=EnemyTier.TIER_3,
    hp_die=8,
    ac_modifier=0,
    damage_die=8,
    special_ability=SpecialAbility.STUN,
    description="A hunched humanoid with elongated claws and a paralyzing touch"
)

SHADOW_HOUND = EnemyType(
    name="Shadow Hound",
    tier=EnemyTier.TIER_3,
    hp_die=8,
    ac_modifier=1,  # Shadowy form
    damage_die=8,
    special_ability=SpecialAbility.FRIGHTEN,
    description="A spectral canine that seems to phase in and out of reality"
)

VENOMOUS_SNAKE = EnemyType(
    name="Venomous Snake",
    tier=EnemyTier.TIER_3,
    hp_die=8,
    ac_modifier=1,  # Quick strikes
    damage_die=8,
    special_ability=SpecialAbility.POISON,
    description="A serpent with scales that shimmer with deadly toxins"
)

ANIMATED_ARMOR = EnemyType(
    name="Animated Armor",
    tier=EnemyTier.TIER_3,
    hp_die=8,
    ac_modifier=2,  # Metal plates
    damage_die=8,
    special_ability=SpecialAbility.NONE,
    description="An empty suit of armor that moves with supernatural grace"
)

# === TIER 4 ENEMIES (Floors 7-8) ===

BONE_GOLEM = EnemyType(
    name="Bone Golem",
    tier=EnemyTier.TIER_4,
    hp_die=4,  # Uses 2d4
    ac_modifier=2,  # Reinforced bones
    damage_die=4,  # Uses 2d4
    special_ability=SpecialAbility.NONE,
    description="A massive construct assembled from the bones of countless victims"
)

DIRE_WOLF = EnemyType(
    name="Dire Wolf",
    tier=EnemyTier.TIER_4,
    hp_die=4,  # Uses 2d4
    ac_modifier=0,
    damage_die=4,  # Uses 2d4
    special_ability=SpecialAbility.FRIGHTEN,
    description="A wolf the size of a horse with glowing red eyes"
)

PLAGUE_BEAR = EnemyType(
    name="Plague Bear",
    tier=EnemyTier.TIER_4,
    hp_die=4,  # Uses 2d4
    ac_modifier=0,
    damage_die=4,  # Uses 2d4
    special_ability=SpecialAbility.POISON,
    description="A diseased ursine horror with matted fur and weeping sores"
)

GARGOYLE = EnemyType(
    name="Gargoyle",
    tier=EnemyTier.TIER_4,
    hp_die=4,  # Uses 2d4
    ac_modifier=2,  # Stone hide and flying
    damage_die=4,  # Uses 2d4
    special_ability=SpecialAbility.NONE,
    description="A living statue with bat-like wings and a heart of stone"
)

# === TIER 5 ENEMIES (Floors 9-10) ===

WRAITH = EnemyType(
    name="Wraith",
    tier=EnemyTier.TIER_5,
    hp_die=10,
    ac_modifier=2,  # Incorporeal
    damage_die=10,
    special_ability=SpecialAbility.CURSE,
    description="A ghostly figure wrapped in tattered robes, draining life with its touch"
)

REVENANT = EnemyType(
    name="Revenant",
    tier=EnemyTier.TIER_5,
    hp_die=10,
    ac_modifier=0,
    damage_die=10,
    special_ability=SpecialAbility.STUN,
    description="An undead warrior driven by vengeance, unable to truly die"
)

HELL_HOUND = EnemyType(
    name="Hell Hound",
    tier=EnemyTier.TIER_5,
    hp_die=10,
    ac_modifier=0,
    damage_die=10,
    special_ability=SpecialAbility.BURN,
    description="A demonic canine wreathed in flames, leaving burning pawprints"
)

STONE_TITAN = EnemyType(
    name="Stone Titan",
    tier=EnemyTier.TIER_5,
    hp_die=10,
    ac_modifier=2,  # Massive stone body
    damage_die=10,
    special_ability=SpecialAbility.NONE,
    description="A colossal humanoid carved from living rock, each step shaking the ground"
)

# === ENEMY COLLECTIONS BY TIER ===

TIER_1_ENEMIES = [GIANT_RAT, SLIME, GIANT_BAT, CAVE_BEETLE]
TIER_2_ENEMIES = [SKELETON, ZOMBIE, CARRION_CROW_SWARM, SPITTING_SPIDER]
TIER_3_ENEMIES = [GHOUL, SHADOW_HOUND, VENOMOUS_SNAKE, ANIMATED_ARMOR]
TIER_4_ENEMIES = [BONE_GOLEM, DIRE_WOLF, PLAGUE_BEAR, GARGOYLE]
TIER_5_ENEMIES = [WRAITH, REVENANT, HELL_HOUND, STONE_TITAN]

ENEMIES_BY_TIER = {
    EnemyTier.TIER_1: TIER_1_ENEMIES,
    EnemyTier.TIER_2: TIER_2_ENEMIES,
    EnemyTier.TIER_3: TIER_3_ENEMIES,
    EnemyTier.TIER_4: TIER_4_ENEMIES,
    EnemyTier.TIER_5: TIER_5_ENEMIES,
}


def get_enemies_for_floor(floor: int) -> list[EnemyType]:
    """
    Get the appropriate enemy types for a given floor.
    
    Args:
        floor: The dungeon floor number
        
    Returns:
        List of enemy types that can appear on this floor
    """
    if floor <= 2:
        return TIER_1_ENEMIES
    elif floor <= 4:
        return TIER_2_ENEMIES
    elif floor <= 6:
        return TIER_3_ENEMIES
    elif floor <= 8:
        return TIER_4_ENEMIES
    else:
        return TIER_5_ENEMIES


def get_tier_for_floor(floor: int) -> EnemyTier:
    """Get the enemy tier for a given floor"""
    if floor <= 2:
        return EnemyTier.TIER_1
    elif floor <= 4:
        return EnemyTier.TIER_2
    elif floor <= 6:
        return EnemyTier.TIER_3
    elif floor <= 8:
        return EnemyTier.TIER_4
    else:
        return EnemyTier.TIER_5


# === BOSS VARIANTS ===

class BossType(Enum):
    """Types of boss modifications"""
    RAGE = "rage"          # +2 damage when below half HP
    SUMMON = "summon"      # Call 1d4 minions when first bloodied
    AURA = "aura"          # All enemies get +1 to rolls
    REGENERATE = "regenerate"  # Heal 1d4 HP per round


@dataclass 
class BossModifier:
    """Modifications applied to enemies to make them bosses"""
    boss_type: BossType
    description: str
    
    def apply_to_enemy(self, enemy_type: EnemyType) -> Dict[str, Any]:
        """
        Apply boss modifications to an enemy type.
        
        Returns dict of modifications to apply.
        """
        return {
            'hp_multiplier': 2,
            'ac_bonus': 2,
            'might_bonus': 2,
            'boss_ability': self.boss_type,
            'boss_description': self.description
        }


BOSS_MODIFIERS = [
    BossModifier(BossType.RAGE, "becomes enraged when wounded"),
    BossModifier(BossType.SUMMON, "calls for reinforcements"),
    BossModifier(BossType.AURA, "empowers nearby allies"),
    BossModifier(BossType.REGENERATE, "regenerates wounds")
]


