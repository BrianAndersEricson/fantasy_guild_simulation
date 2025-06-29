"""
Party model for the Fantasy Guild Manager simulation.

A Party represents a team of 4 characters (one of each role) that goes on
expeditions together. This is the core unit of the simulation - all
dungeon activities happen at the party level.
"""

import sys
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict

# Add the project root to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.character import Character, CharacterRole


@dataclass
class Party:
    """
    Represents a 4-character adventuring party.
    
    Each party must have exactly one character of each role:
    - 1 Striker (damage dealer)
    - 1 Burglar (trap detection, treasure finding)  
    - 1 Support (healing and buffs)
    - 1 Controller (enemy debuffs and crowd control)
    
    During expeditions, the party accumulates gold, clears rooms/floors,
    and may retreat based on morale calculations.
    """
    
    # === Identity ===
    guild_id: int
    guild_name: str
    members: List[Character] = field(default_factory=list)
    
    # === Expedition Progress ===
    gold_found: int = 0
    floors_cleared: int = 0
    rooms_cleared: int = 0
    monsters_defeated: int = 0
    
    # === Expedition Status ===
    is_active: bool = True      # False if retreated or wiped
    retreated: bool = False     # True if morale failed (this is normal completion)
    
    def __post_init__(self):
        """Validate party composition after creation"""
        self._validate_party_composition()
    
    def _validate_party_composition(self):
        """
        Ensure party has exactly one character of each role.
        
        This is critical for game balance - each role has specific
        responsibilities in the automated simulation.
        """
        if len(self.members) != 4:
            raise ValueError(f"Party must have exactly 4 members, got {len(self.members)}")
        
        roles_present = {member.role for member in self.members}
        required_roles = {CharacterRole.STRIKER, CharacterRole.BURGLAR, 
                         CharacterRole.SUPPORT, CharacterRole.CONTROLLER}
        
        if roles_present != required_roles:
            missing = required_roles - roles_present
            extra = roles_present - required_roles
            raise ValueError(f"Invalid party composition. Missing: {missing}, Extra: {extra}")
        
        # Ensure all members belong to the same guild
        guild_ids = {member.guild_id for member in self.members}
        if len(guild_ids) > 1:
            raise ValueError(f"All party members must be from same guild. Found: {guild_ids}")
    
    def get_member_by_role(self, role: CharacterRole) -> Optional[Character]:
        """
        Get the party member with the specified role.
        
        Returns None if that role's character is dead or unconscious.
        This is used throughout the simulation for role-specific actions.
        
        Args:
            role: The character role to find
            
        Returns:
            The character with that role, or None if dead/unconscious
        """
        for member in self.members:
            if member.role == role and member.is_alive and member.is_conscious:
                return member
        return None
    
    def alive_members(self) -> List[Character]:
        """Get all living and conscious party members"""
        return [member for member in self.members if member.is_alive and member.is_conscious]
    
    def unconscious_members(self) -> List[Character]:
        """Get all unconscious but living party members"""
        return [member for member in self.members if member.is_alive and not member.is_conscious]
    
    def dead_members(self) -> List[Character]:
        """Get all permanently dead party members"""
        return [member for member in self.members if not member.is_alive]
    
    def total_disabled_spells(self) -> int:
        """Count total disabled spells across all party members"""
        return sum(len(member.disabled_spells) for member in self.members)
    
    def total_missing_hp(self) -> int:
        """Calculate total HP lost across all party members"""
        return sum(member.max_hp - member.current_hp for member in self.members)
    
    def total_times_downed(self) -> int:
        """Count total times any party member has been downed (for morale)"""
        return sum(member.times_downed for member in self.members)
    
    def calculate_morale(self) -> int:
        """
        Calculate current party morale for retreat checks.
        
        Morale formula:
        Morale = 100 - (Total Missing HP) - (5 × Disabled Spells) - (20 × Currently Downed) - (10 × Times Ever Downed)
        
        Lower morale means higher chance of retreating from the dungeon.
        The "times downed" penalty represents lasting psychological trauma.
        
        Returns:
            Current morale value (0-100, though can go negative)
        """
        morale = 100
        morale -= self.total_missing_hp()
        morale -= (5 * self.total_disabled_spells())
        morale -= (20 * len(self.unconscious_members()))
        morale -= (10 * self.total_times_downed())  # Psychological trauma
        
        return max(0, morale)  # Morale can't go below 0
    
    def is_party_wiped(self) -> bool:
        """Check if entire party is unconscious or dead (expedition automatically ends)"""
        return len(self.alive_members()) == 0
    
    def add_gold(self, amount: int):
        """Add gold found during expedition"""
        if amount > 0:
            self.gold_found += amount
    
    def complete_room(self):
        """Mark a room as completed"""
        self.rooms_cleared += 1
    
    def complete_floor(self):
        """Mark a floor as completed"""
        self.floors_cleared += 1
    
    def defeat_monsters(self, count: int):
        """Add to monster defeat counter"""
        if count > 0:
            self.monsters_defeated += count
    
    def retreat_from_expedition(self):
        """Mark party as retreated (morale failure - this is normal completion)"""
        self.retreated = True
        self.is_active = False
    
    def complete_expedition(self):
        """Mark expedition as completed (same as retreat for infinite dungeons)"""
        self.retreat_from_expedition()  # In infinite dungeons, all expeditions end in retreat
    
    def reset_for_new_expedition(self):
        """
        Reset party state for a new expedition.
        
        Called between expeditions to clear progress counters
        and reset character states.
        """
        # Reset expedition progress
        self.gold_found = 0
        self.floors_cleared = 0
        self.rooms_cleared = 0
        self.monsters_defeated = 0
        
        # Reset expedition status
        self.is_active = True
        self.retreated = False
        
        # Reset all character states
        for member in self.members:
            member.reset_for_expedition()
    
    def get_expedition_summary(self) -> Dict:
        """
        Get a summary of the expedition results.
        
        Used for logging and viewer display.
        """
        return {
            'guild_name': self.guild_name,
            'floors_cleared': self.floors_cleared,
            'rooms_cleared': self.rooms_cleared,
            'gold_found': self.gold_found,
            'monsters_defeated': self.monsters_defeated,
            'survivors': len(self.alive_members()),
            'total_members': len(self.members),
            'status': 'retreated' if self.retreated 
                     else 'wiped' if self.is_party_wiped()
                     else 'active',
            'final_morale': self.calculate_morale()
        }
    
    def __str__(self):
        """String representation for logging"""
        status = ('Retreated' if self.retreated
                 else 'Wiped' if self.is_party_wiped()
                 else 'Active')
        
        return (f"{self.guild_name} - {status} | "
                f"Floors: {self.floors_cleared}, Gold: {self.gold_found}, "
                f"Alive: {len(self.alive_members())}/4, Morale: {self.calculate_morale()}")


def create_test_party(guild_id: int, guild_name: str) -> Party:
    """
    Helper function to create a balanced test party.
    
    This creates a party with one character of each role,
    useful for testing and demos.
    """
    members = [
        Character(f"{guild_name} Striker", CharacterRole.STRIKER, guild_id, might=12, grit=11, wit=8, luck=9),
        Character(f"{guild_name} Burglar", CharacterRole.BURGLAR, guild_id, might=9, grit=9, wit=10, luck=12),
        Character(f"{guild_name} Support", CharacterRole.SUPPORT, guild_id, might=8, grit=10, wit=12, luck=10),
        Character(f"{guild_name} Controller", CharacterRole.CONTROLLER, guild_id, might=9, grit=10, wit=11, luck=10),
    ]
    
    return Party(guild_id=guild_id, guild_name=guild_name, members=members)

