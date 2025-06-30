"""
Trap Resolver for Fantasy Guild Manager
Handles trap detection, disarming, and consequences when traps trigger
"""

import random
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

# Import our dependencies
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.character import Character, CharacterRole
from models.party import Party
from models.events import EventType
from simulation.debuff_system import DebuffManager, create_trap_debuff


class TrapOutcome(Enum):
    """Possible outcomes when resolving a trap"""
    CRITICAL_SUCCESS = "critical_success"    # Nat 20 - disarmed + advantage
    SUCCESS = "success"                      # Beat DC - disarmed
    FAILURE = "failure"                      # Failed DC - trap triggers on random member
    CRITICAL_FAILURE = "critical_failure"    # Nat 1 - trap hits burglar + debuff


@dataclass
class TrapResult:
    """
    Result of attempting to handle a trap.
    Contains all information needed for event generation and party updates.
    """
    outcome: TrapOutcome
    detecting_character: Character
    trap_dc: int
    roll_result: int
    damage_dealt: int = 0
    damage_target: Optional[Character] = None
    debuff_applied: Optional[str] = None
    debuff_target: Optional[Character] = None
    events_generated: List[dict] = None
    
    def __post_init__(self):
        if self.events_generated is None:
            self.events_generated = []


class TrapResolver:
    """
    Handles all trap-related mechanics for dungeon rooms.
    
    Uses burglar's luck stat for detection with +1 per 3 luck scaling.
    Integrates with debuff system for trap consequences.
    Generates events for viewer narrative.
    """
    
    def __init__(self, rng: random.Random, emit_event_callback=None):
        """
        Initialize trap resolver.
        
        Args:
            rng: Seeded random number generator for deterministic results
            emit_event_callback: Function to call for event generation
        """
        self.rng = rng
        self.emit_event = emit_event_callback or self._default_event_handler
    
    def _default_event_handler(self, guild_id: int, guild_name: str, event_type: EventType,
                             description: str, priority: str = "normal",
                             details: dict = None):
        """Default event handler for testing"""
        print(f"[EVENT] {guild_name}: {description}")
    
    def calculate_luck_bonus(self, character: Character) -> int:
        """
        Calculate luck bonus for trap detection using character's modifier system.
        
        Args:
            character: Character attempting trap detection
            
        Returns:
            Bonus to add to trap detection rolls
        """
        return character.get_luck_modifier()
    
    def get_trap_detector(self, party: Party) -> Character:
        """
        Determine who attempts to detect/disarm the trap.
        Burglar gets priority, otherwise random living member.
        
        Args:
            party: The party encountering the trap
            
        Returns:
            Character who will attempt trap detection
        """
        # Look for living burglar first
        burglar = party.get_member_by_role(CharacterRole.BURGLAR)
        if burglar and burglar.is_alive:
            return burglar
        
        # No burglar available, pick random living member
        living_members = party.alive_members()
        if living_members:
            return self.rng.choice(living_members)
        
        # This shouldn't happen in normal play
        raise ValueError("No living party members to detect trap")
    
    def resolve_trap(self, party: Party, floor_level: int) -> TrapResult:
        """
        Main trap resolution logic following core mechanics.
        
        Args:
            party: Party attempting the trap
            floor_level: Current floor level (affects DC and damage)
            
        Returns:
            TrapResult with all outcomes and events
        """
        # Determine who's detecting the trap
        detector = self.get_trap_detector(party)
        
        # Calculate trap DC and detection roll
        trap_dc = 10 + floor_level
        base_roll = self.rng.randint(1, 20)
        luck_bonus = self.calculate_luck_bonus(detector)
        
        # Apply debuff modifiers if detector has any
        debuff_modifier = 0
        if hasattr(detector, 'debuff_manager') and detector.debuff_manager:
            debuff_modifier = detector.debuff_manager.get_stat_modifier('luck', vs_enemies=False)
        
        total_roll = base_roll + luck_bonus + debuff_modifier
        
        # Create result object
        result = TrapResult(
            outcome=TrapOutcome.SUCCESS,  # Will be updated
            detecting_character=detector,
            trap_dc=trap_dc,
            roll_result=total_roll
        )
        
        # Determine outcome based on roll
        if base_roll == 1:  # Natural 1 is always critical failure, regardless of bonuses
            result.outcome = TrapOutcome.CRITICAL_FAILURE
            self._handle_critical_failure(result, party, floor_level)
            
        elif base_roll == 20:  # Natural 20 is always critical success, regardless of penalties
            result.outcome = TrapOutcome.CRITICAL_SUCCESS
            self._handle_critical_success(result, party)
            
        elif total_roll >= trap_dc:
            result.outcome = TrapOutcome.SUCCESS
            self._handle_success(result, party)
            
        else:
            result.outcome = TrapOutcome.FAILURE
            self._handle_failure(result, party, floor_level)
        
        return result
    
    def _handle_critical_failure(self, result: TrapResult, party: Party, floor_level: int):
        """Handle critical failure (natural 1) - detector takes damage + debuff"""
        detector = result.detecting_character
        
        # Calculate damage (1d6 × floor level)
        damage = self.rng.randint(1, 6) * floor_level
        result.damage_dealt = damage
        result.damage_target = detector
        
        # Apply damage
        was_downed = detector.take_damage(damage)
        
        # Apply random debuff
        if hasattr(detector, 'debuff_manager') and detector.debuff_manager:
            trap_debuff = create_trap_debuff(self.rng)
            detector.debuff_manager.apply_debuff(trap_debuff)
            result.debuff_applied = trap_debuff.debuff_type.value
            result.debuff_target = detector
        
        # Generate events
        self.emit_event(
            party.guild_id, party.guild_name, EventType.TRAP_TRIGGERED,
            f"{detector.name} critically fails! Trap deals {damage} damage and applies {result.debuff_applied}!",
            "high",
            {
                'detector': detector.name,
                'damage': damage,
                'debuff': result.debuff_applied,
                'roll': 1,
                'was_downed': was_downed
            }
        )
        
        if was_downed:
            self.emit_event(
                party.guild_id, party.guild_name, EventType.CHARACTER_UNCONSCIOUS,
                f"{detector.name} has been downed by the trap!",
                "critical",
                {'character': detector.name, 'cause': 'trap'}
            )
    
    def _handle_critical_success(self, result: TrapResult, party: Party):
        """Handle critical success (natural 20) - trap disarmed + advantage"""
        detector = result.detecting_character
        
    def _handle_critical_success(self, result: TrapResult, party: Party):
        """Handle critical success (natural 20) - trap disarmed + advantage"""
        detector = result.detecting_character
        
        # Grant advantage on next roll (this would need integration with combat system)
        # For now, just note it in events
        self.emit_event(
            party.guild_id, party.guild_name, EventType.TRAP_DETECTED,
            f"{detector.name} expertly disarms the trap! (Critical success)",
            "normal",
            {
                'detector': detector.name,
                'roll': 20,
                'dc': result.trap_dc,
                'advantage_granted': True
            }
        )
    
    def _handle_success(self, result: TrapResult, party: Party):
        """Handle normal success - trap disarmed cleanly"""
        detector = result.detecting_character
        
        self.emit_event(
            party.guild_id, party.guild_name, EventType.TRAP_DETECTED,
            f"{detector.name} disarms the trap (rolled {result.roll_result} vs DC {result.trap_dc})",
            "normal",
            {
                'detector': detector.name,
                'roll': result.roll_result,
                'dc': result.trap_dc
            }
        )
    
    def _handle_failure(self, result: TrapResult, party: Party, floor_level: int):
        """Handle failure - trap triggers on random party member"""
        # Calculate damage (1d6 × floor level)
        damage = self.rng.randint(1, 6) * floor_level
        result.damage_dealt = damage
        
        # Pick random living target
        living_members = party.alive_members()
        if living_members:
            target = self.rng.choice(living_members)
            result.damage_target = target
            
            # Apply damage
            was_downed = target.take_damage(damage)
            
            # Generate events
            self.emit_event(
                party.guild_id, party.guild_name, EventType.TRAP_TRIGGERED,
                f"Trap springs! {target.name} takes {damage} damage",
                "high",
                {
                    'detector': result.detecting_character.name,
                    'target': target.name,
                    'damage': damage,
                    'roll': result.roll_result,
                    'dc': result.trap_dc,
                    'was_downed': was_downed
                }
            )
            
            if was_downed:
                self.emit_event(
                    party.guild_id, party.guild_name, EventType.CHARACTER_UNCONSCIOUS,
                    f"{target.name} has been downed by the trap!",
                    "critical",
                    {'character': target.name, 'cause': 'trap'}
                )


