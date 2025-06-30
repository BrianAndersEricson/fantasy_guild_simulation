"""
Morale Checker for Fantasy Guild Manager
Handles morale checks and retreat decisions during expeditions
"""

import random
from dataclasses import dataclass
from enum import Enum

# Import our dependencies
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.character import Character, CharacterRole
from models.party import Party
from models.events import EventType


class MoraleOutcome(Enum):
    """Possible outcomes of a morale check"""
    SUCCESS = "success"      # Party continues expedition
    FAILURE = "failure"      # Party retreats from dungeon


@dataclass
class MoraleResult:
    """
    Result of a morale check.
    Contains all information needed for expedition control and event generation.
    """
    outcome: MoraleOutcome
    morale_dc: int
    roll_result: int
    rolls_made: list  # For transparency (shows both dice for floor completion)
    is_floor_completion: bool
    continues_expedition: bool = False  # Default value, will be set in __post_init__
    
    def __post_init__(self):
        self.continues_expedition = (self.outcome == MoraleOutcome.SUCCESS)


class MoraleChecker:
    """
    Handles morale check mechanics for expedition control.
    
    Uses consistent roll-over mechanics like all other systems.
    Higher damage/problems = higher DC = harder to continue.
    """
    
    def __init__(self, rng: random.Random = None, emit_event_callback=None):
        """
        Initialize morale checker.
        
        Args:
            rng: Random number generator. Uses unseeded random by default for true randomness
            emit_event_callback: Function to call for event generation
        """
        self.rng = rng if rng is not None else random.Random()
        self.emit_event = emit_event_callback or self._default_event_handler
    
    def _default_event_handler(self, guild_id, guild_name, event_type, description, priority="normal", details=None):
        """Default event handler for testing"""
        print(f"[EVENT] {description}")
    
    def calculate_morale_dc(self, party: Party) -> int:
        """
        Calculate the DC for morale checks based on party condition.
        
        DC = (Missing HP) + (5 × Disabled Spells) + (20 × Unconscious) + (10 × Times Downed)
        
        Args:
            party: The party to calculate morale DC for
            
        Returns:
            DC that must be beaten to continue expedition
        """
        dc = 0
        
        # Add missing HP penalty
        dc += party.total_missing_hp()
        
        # Add disabled spells penalty (5 per spell)
        dc += (5 * party.total_disabled_spells())
        
        # Add unconscious members penalty (20 per unconscious)
        dc += (20 * len(party.unconscious_members()))
        
        # Add times downed penalty (10 per cumulative downed)
        dc += (10 * party.total_times_downed())
        
        return dc
    
    def check_morale(self, party: Party, is_floor_completion: bool = False) -> MoraleResult:
        """
        Perform a morale check to determine if party continues or retreats.
        
        Args:
            party: The party making the morale check
            is_floor_completion: Whether this is a floor completion check (disadvantage)
            
        Returns:
            MoraleResult with outcome and all relevant data
        """
        # Calculate morale DC
        morale_dc = self.calculate_morale_dc(party)
        
        # Make the roll(s)
        if is_floor_completion:
            # Floor completion: roll 2d100, take lower (disadvantage)
            roll1 = self.rng.randint(1, 100)
            roll2 = self.rng.randint(1, 100)
            final_roll = min(roll1, roll2)  # Take lower for disadvantage
            rolls_made = [roll1, roll2]
        else:
            # Normal room: roll 1d100
            final_roll = self.rng.randint(1, 100)
            rolls_made = [final_roll]
        
        # Determine outcome
        if final_roll >= morale_dc:
            outcome = MoraleOutcome.SUCCESS
            self._handle_success(party, morale_dc, final_roll, rolls_made, is_floor_completion)
        else:
            outcome = MoraleOutcome.FAILURE
            self._handle_failure(party, morale_dc, final_roll, rolls_made, is_floor_completion)
        
        return MoraleResult(
            outcome=outcome,
            morale_dc=morale_dc,
            roll_result=final_roll,
            rolls_made=rolls_made,
            is_floor_completion=is_floor_completion
        )
    
    def _handle_success(self, party: Party, dc: int, roll: int, rolls: list, is_floor_completion: bool):
        """Handle successful morale check - party continues"""
        if is_floor_completion:
            if len(rolls) == 2:
                self.emit_event(
                    party.guild_id, party.guild_name, EventType.MORALE_SUCCESS,
                    f"Floor complete! Morale check: [{rolls[0]}, {rolls[1]}] taking {roll} vs DC {dc} - Press deeper!",
                    "high",
                    {
                        'morale_dc': dc,
                        'rolls': rolls,
                        'final_roll': roll,
                        'success': True,
                        'is_floor_completion': True
                    }
                )
        else:
            self.emit_event(
                party.guild_id, party.guild_name, EventType.MORALE_SUCCESS,
                f"Morale check: {roll} vs DC {dc} - The party steels their resolve!",
                "normal",
                {
                    'morale_dc': dc,
                    'roll': roll,
                    'success': True,
                    'is_floor_completion': False
                }
            )
    
    def _handle_failure(self, party: Party, dc: int, roll: int, rolls: list, is_floor_completion: bool):
        """Handle failed morale check - party retreats"""
        # Mark party as retreated
        party.retreat_from_expedition()
        
        if is_floor_completion:
            if len(rolls) == 2:
                self.emit_event(
                    party.guild_id, party.guild_name, EventType.MORALE_FAILURE,
                    f"Floor complete, but morale breaks! [{rolls[0]}, {rolls[1]}] taking {roll} vs DC {dc} - Time to retreat!",
                    "high",
                    {
                        'morale_dc': dc,
                        'rolls': rolls,
                        'final_roll': roll,
                        'success': False,
                        'is_floor_completion': True
                    }
                )
        else:
            self.emit_event(
                party.guild_id, party.guild_name, EventType.MORALE_FAILURE,
                f"Morale breaks! {roll} vs DC {dc} - The party retreats from the dungeon!",
                "high",
                {
                    'morale_dc': dc,
                    'roll': roll,
                    'success': False,
                    'is_floor_completion': False
                }
            )


