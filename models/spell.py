"""
Spell system for the Fantasy Guild Manager simulation.
Spells are cast automatically by Support and Controller characters.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Union
import random


class SpellType(Enum):
    """Categories of spells available to different roles"""
    CONTROLLER_DEBUFF = "controller_debuff"
    CONTROLLER_DAMAGE = "controller_damage"
    SUPPORT_HEAL = "support_heal"
    SUPPORT_CURE = "support_cure"
    SUPPORT_BUFF = "support_buff"


class TargetType(Enum):
    """Who can be targeted by a spell"""
    ALLY = "ally"
    ENEMY = "enemy"
    SELF = "self"
    ALL_ALLIES = "all_allies"
    ALL_ENEMIES = "all_enemies"


from simulation.debuff_system import DebuffType

@dataclass
class SpellEffect:
    """Represents what a spell does when cast successfully"""
    # Damage/healing amounts
    damage: int = 0
    healing: int = 0
    
    # Debuffs to apply
    debuff: Optional[DebuffType] = None
    debuff_duration: int = 0  # Base duration, modified by Luck
    
    # Buffs to apply
    ac_bonus: int = 0
    damage_shield: int = 0  # Absorbs this much damage
    
    # Special effects
    prevents_death: bool = False
    area_effect: bool = False
    cures_debuffs: List[DebuffType] = None
    
    def __post_init__(self):
        if self.cures_debuffs is None:
            self.cures_debuffs = []


@dataclass
class Spell:
    """Represents a spell that characters can learn and cast"""
    name: str
    spell_type: SpellType
    target_type: TargetType
    base_dc: int  # Base difficulty class
    description: str
    effect: SpellEffect
    
    # Stat dependencies
    primary_stat: str = "wit"  # Usually wit for all spells
    secondary_stat: Optional[str] = None  # luck for controllers, grit for support
    
    # Spell-specific modifiers
    uses_floor_level: bool = True  # If DC scales with floor level
    uses_enemy_level: bool = False  # If DC scales with target level


# ============= SPELL DEFINITIONS =============

# Controller Spells - Focus on debuffing enemies
CONTROLLER_SPELLS = [
    Spell(
        name="Seren's Touch",
        spell_type=SpellType.CONTROLLER_DEBUFF,
        target_type=TargetType.ENEMY,
        base_dc=10,
        description="Confuses target, making them attack randomly",
        effect=SpellEffect(
            debuff=DebuffType.CONFUSED,
            debuff_duration=4  # 1d4 base + luck modifier
        ),
        secondary_stat="luck",
        uses_enemy_level=True
    ),
    
    Spell(
        name="Veil of Delirium", 
        spell_type=SpellType.CONTROLLER_DEBUFF,
        target_type=TargetType.ENEMY,
        base_dc=10,
        description="Curses target, reducing their luck rolls",
        effect=SpellEffect(
            debuff=DebuffType.CURSED,
            debuff_duration=6  # 1d6 base + luck
        ),
        secondary_stat="luck",
        uses_enemy_level=True
    ),
    
    Spell(
        name="Chains of Stillness",
        spell_type=SpellType.CONTROLLER_DEBUFF,
        target_type=TargetType.ENEMY,
        base_dc=10,
        description="Slows target, reducing initiative and reactions",
        effect=SpellEffect(
            debuff=DebuffType.SLOWED,
            debuff_duration=4  # 1d4 base + luck
        ),
        secondary_stat="luck",
        uses_enemy_level=True
    ),
    
    Spell(
        name="Hex of Frailty",
        spell_type=SpellType.CONTROLLER_DEBUFF,
        target_type=TargetType.ENEMY,
        base_dc=10,
        description="Weakens target, reducing their physical power",
        effect=SpellEffect(
            debuff=DebuffType.WEAKENED,
            debuff_duration=4  # 1d4 base + luck
        ),
        secondary_stat="luck",
        uses_enemy_level=True
    ),
    
    Spell(
        name="Mindshatter",
        spell_type=SpellType.CONTROLLER_DEBUFF,
        target_type=TargetType.ENEMY,
        base_dc=12,  # Harder to land but powerful
        description="Stuns target, making them lose their next action",
        effect=SpellEffect(
            debuff=DebuffType.STUNNED,
            debuff_duration=1  # Always 1 round
        ),
        secondary_stat="luck",
        uses_enemy_level=True
    ),
    
    Spell(
        name="Phantom Blight",
        spell_type=SpellType.CONTROLLER_DEBUFF,
        target_type=TargetType.ENEMY,
        base_dc=11,
        description="Poisons target with phantom toxins",
        effect=SpellEffect(
            debuff=DebuffType.POISONED,
            debuff_duration=8  # 2d4 base + luck (longer duration)
        ),
        secondary_stat="luck",
        uses_enemy_level=True
    ),
    
    Spell(
        name="Dreadful Gaze",
        spell_type=SpellType.CONTROLLER_DEBUFF,
        target_type=TargetType.ENEMY,
        base_dc=10,
        description="Frightens target, reducing their effectiveness",
        effect=SpellEffect(
            debuff=DebuffType.FRIGHTENED,
            debuff_duration=4  # 1d4 base + luck
        ),
        secondary_stat="luck",
        uses_enemy_level=True
    ),
    
    Spell(
        name="Blind Hex",
        spell_type=SpellType.CONTROLLER_DEBUFF,
        target_type=TargetType.ENEMY,
        base_dc=11,
        description="Blinds target, severely reducing accuracy",
        effect=SpellEffect(
            debuff=DebuffType.BLINDED,
            debuff_duration=6  # 1d6 base + luck
        ),
        secondary_stat="luck",
        uses_enemy_level=True
    ),
    
    Spell(
        name="Psychic Lance",
        spell_type=SpellType.CONTROLLER_DAMAGE,
        target_type=TargetType.ENEMY,
        base_dc=10,
        description="Strikes target's mind with psychic energy",
        effect=SpellEffect(
            damage=4  # 1d4 base + luck modifier
        ),
        secondary_stat="luck",
        uses_enemy_level=True
    )
]

# Support Spells - Focus on healing and helping allies
SUPPORT_SPELLS = [
    Spell(
        name="Mend Wounds",
        spell_type=SpellType.SUPPORT_HEAL,
        target_type=TargetType.ALLY,
        base_dc=10,
        description="Heals target's wounds with divine energy",
        effect=SpellEffect(
            healing=4  # 1d4 base + grit modifier
        ),
        secondary_stat="grit",
        uses_floor_level=True,
        uses_enemy_level=False  # Support spells don't scale with enemy level
    ),
    
    Spell(
        name="Lifebloom",
        spell_type=SpellType.SUPPORT_HEAL,
        target_type=TargetType.ALLY,
        base_dc=11,
        description="Creates ongoing healing effect",
        effect=SpellEffect(
            healing=1,  # 1 HP per round
            debuff_duration=6  # Duration in rounds (1d6 + grit)
        ),
        secondary_stat="grit"
    ),
    
    Spell(
        name="Sanctuary Pulse",
        spell_type=SpellType.SUPPORT_HEAL,
        target_type=TargetType.ALL_ALLIES,
        base_dc=12,
        description="Sends healing energy to all allies",
        effect=SpellEffect(
            healing=1,  # 1 HP to everyone
            area_effect=True
        ),
        secondary_stat="grit"
    ),
    
    Spell(
        name="Ward of Vitality",
        spell_type=SpellType.SUPPORT_BUFF,
        target_type=TargetType.ALLY,
        base_dc=10,
        description="Creates magical shield to absorb damage",
        effect=SpellEffect(
            damage_shield=4  # 4 + grit damage absorbed
        ),
        secondary_stat="grit",
        uses_floor_level=True,
        uses_enemy_level=False
    ),
    
    Spell(
        name="Echo of Hope",
        spell_type=SpellType.SUPPORT_BUFF,
        target_type=TargetType.ALLY,
        base_dc=13,  # Powerful effect, harder to cast
        description="Prevents target from dying this round",
        effect=SpellEffect(
            prevents_death=True,
            debuff_duration=1  # Lasts 1 round
        ),
        secondary_stat="grit"
    ),
    
    Spell(
        name="Heartening Howl",
        spell_type=SpellType.SUPPORT_CURE,
        target_type=TargetType.ALLY,
        base_dc=10,
        description="Cures mental ailments",
        effect=SpellEffect(
            cures_debuffs=[DebuffType.CONFUSED, DebuffType.FRIGHTENED]
        ),
        secondary_stat="grit"
    ),
    
    Spell(
        name="Soothing Touch",
        spell_type=SpellType.SUPPORT_CURE,
        target_type=TargetType.ALLY,
        base_dc=10,
        description="Neutralizes toxins and curses",
        effect=SpellEffect(
            cures_debuffs=[DebuffType.POISONED, DebuffType.CURSED]
        ),
        secondary_stat="grit"
    ),
    
    Spell(
        name="Cure Ailment",
        spell_type=SpellType.SUPPORT_CURE,
        target_type=TargetType.ALLY,
        base_dc=10,
        description="Restores sight and mobility",
        effect=SpellEffect(
            cures_debuffs=[DebuffType.BLINDED, DebuffType.SLOWED]
        ),
        secondary_stat="grit"
    )
]

# All spells combined for easy access
ALL_SPELLS = CONTROLLER_SPELLS + SUPPORT_SPELLS

# Create lookup dictionaries
SPELLS_BY_NAME = {spell.name: spell for spell in ALL_SPELLS}
SPELLS_BY_TYPE = {
    SpellType.CONTROLLER_DEBUFF: [s for s in ALL_SPELLS if s.spell_type == SpellType.CONTROLLER_DEBUFF],
    SpellType.CONTROLLER_DAMAGE: [s for s in ALL_SPELLS if s.spell_type == SpellType.CONTROLLER_DAMAGE],
    SpellType.SUPPORT_HEAL: [s for s in ALL_SPELLS if s.spell_type == SpellType.SUPPORT_HEAL],
    SpellType.SUPPORT_CURE: [s for s in ALL_SPELLS if s.spell_type == SpellType.SUPPORT_CURE],
    SpellType.SUPPORT_BUFF: [s for s in ALL_SPELLS if s.spell_type == SpellType.SUPPORT_BUFF]
}


def get_default_spells_for_role(role_name: str) -> List[str]:
    """Get the default starting spells for each role"""
    if role_name.lower() == "controller":
        return ["Psychic Lance"]  # Damage spell as default
    elif role_name.lower() == "support":
        return ["Mend Wounds"]  # Healing spell as default
    else:
        return []  # Strikers and Burglars don't cast spells


def generate_random_spells_for_role(role_name: str, count: int, rng: random.Random) -> List[str]:
    """Generate random spells for a character (excluding their default)"""
    if role_name.lower() == "controller":
        available = CONTROLLER_SPELLS.copy()
        # Remove default spell from options
        available = [s for s in available if s.name != "Psychic Lance"]
    elif role_name.lower() == "support":
        available = SUPPORT_SPELLS.copy()
        # Remove default spell from options
        available = [s for s in available if s.name != "Mend Wounds"]
    else:
        return []  # Non-casters get no spells
    
    # Randomly select spells
    spell_count = min(count, len(available))
    selected = rng.sample(available, spell_count)
    return [spell.name for spell in selected]


