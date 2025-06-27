"""
Event system for the Fantasy Guild Manager simulation.

Events are the narrative heart of the simulation. They create the story
that viewers follow as multiple guilds explore dungeons simultaneously.
Every interesting action generates an event for the live feed.

Updated to support the new enemy system with specific enemy events.
"""

import sys
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional

# Add the project root to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class EventType(Enum):
    """
    Types of events that can occur during expeditions.

    These create the narrative structure that viewers follow.
    Each event type has different importance and viewer interest levels.
    """

    # === Expedition Flow ===
    EXPEDITION_START = "expedition_start"
    EXPEDITION_RETREAT = "expedition_retreat"
    EXPEDITION_WIPE = "expedition_wipe"
    EXPEDITION_COMPLETE = "expedition_complete"

    # === Dungeon Navigation ===
    FLOOR_ENTER = "floor_enter"
    ROOM_ENTER = "room_enter"
    ROOM_COMPLETE = "room_complete"

    # === Trap Events ===
    TRAP_DETECTED = "trap_detected"
    TRAP_DISARMED = "trap_disarmed"
    TRAP_TRIGGERED = "trap_triggered"
    TRAP_CRITICAL_FAIL = "trap_critical_fail"

    # === Combat Events ===
    COMBAT_START = "combat_start"
    COMBAT_END = "combat_end"
    ATTACK_HIT = "attack_hit"
    ATTACK_MISS = "attack_miss"
    ATTACK_CRITICAL = "attack_critical"
    SPELL_CAST = "spell_cast"
    SPELL_FAIL = "spell_fail"
    SPELL_CRITICAL = "spell_critical"

    # === Enemy Events (NEW) ===
    ENEMY_APPEARS = "enemy_appears"
    ENEMY_DEFEATED = "enemy_defeated"
    BOSS_ABILITY_TRIGGERED = "boss_ability_triggered"
    ENEMY_SPECIAL_ATTACK = "enemy_special_attack"

    # === Character Events ===
    CHARACTER_UNCONSCIOUS = "character_unconscious"
    CHARACTER_DEATH_TEST = "character_death_test"
    CHARACTER_DIES = "character_dies"
    CHARACTER_REVIVED = "character_revived"
    CHARACTER_HEALED = "character_healed"
    SPELL_DISABLED = "spell_disabled"

    # === Status Effects (NEW) ===
    DEBUFF_APPLIED = "debuff_applied"
    DEBUFF_EXPIRED = "debuff_expired"
    STATUS_DAMAGE = "status_damage"

    # === Treasure Events ===
    TREASURE_FOUND = "treasure_found"
    TREASURE_CRITICAL = "treasure_critical"
    MAGIC_ITEM_FOUND = "magic_item_found"

    # === Party Events ===
    MORALE_CHECK = "morale_check"
    MORALE_SUCCESS = "morale_success"
    MORALE_FAILURE = "morale_failure"


@dataclass
class SimulationEvent:
    """
    Represents a single event in the simulation.

    Events are the building blocks of the viewer experience.
    They provide both human-readable descriptions and structured
    data for analysis and display.
    """

    # === Core Event Data ===
    timestamp: datetime
    guild_id: int
    guild_name: str
    event_type: EventType
    description: str

    # === Optional Details ===
    details: Dict[str, Any] = field(default_factory=dict)

    # === Categorization ===
    priority: str = "normal"  # "low", "normal", "high", "critical"
    tags: List[str] = field(default_factory=list)

    # === Tick Support for Replay ===
    tick_number: int = 0  # For synchronized replay timing

    def is_combat_event(self) -> bool:
        """Check if this is a combat-related event"""
        combat_types = {
            EventType.COMBAT_START, EventType.COMBAT_END,
            EventType.ATTACK_HIT, EventType.ATTACK_MISS, EventType.ATTACK_CRITICAL,
            EventType.SPELL_CAST, EventType.SPELL_FAIL, EventType.SPELL_CRITICAL,
            EventType.ENEMY_APPEARS, EventType.ENEMY_DEFEATED,
            EventType.BOSS_ABILITY_TRIGGERED, EventType.ENEMY_SPECIAL_ATTACK
        }
        return self.event_type in combat_types

    def is_character_event(self) -> bool:
        """Check if this event involves a specific character"""
        return 'character' in self.details or 'target' in self.details

    def is_enemy_event(self) -> bool:
        """Check if this event involves a specific enemy"""
        return 'enemy' in self.details or 'attacker' in self.details

    def is_death_related(self) -> bool:
        """Check if this event involves character death or unconsciousness"""
        death_types = {
            EventType.CHARACTER_UNCONSCIOUS, EventType.CHARACTER_DEATH_TEST,
            EventType.CHARACTER_DIES, EventType.CHARACTER_REVIVED
        }
        return self.event_type in death_types

    def is_status_effect_event(self) -> bool:
        """Check if this event involves status effects/debuffs"""
        status_types = {
            EventType.DEBUFF_APPLIED, EventType.DEBUFF_EXPIRED,
            EventType.STATUS_DAMAGE
        }
        return self.event_type in status_types

    def get_character_name(self) -> Optional[str]:
        """Get the name of the character involved in this event"""
        return self.details.get('character') or self.details.get('target')

    def get_enemy_name(self) -> Optional[str]:
        """Get the name of the enemy involved in this event"""
        return self.details.get('enemy') or (
            self.details.get('attacker') if self.details.get('enemy', False) else None
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'guild_id': self.guild_id,
            'guild_name': self.guild_name,
            'event_type': self.event_type.value,
            'description': self.description,
            'details': self.details,
            'priority': self.priority,
            'tags': self.tags,
            'tick_number': self.tick_number
        }

    def __str__(self):
        """Format for live feed display"""
        time_str = self.timestamp.strftime("%H:%M:%S")
        priority_marker = "🔥" if self.priority == "critical" else "⚡" if self.priority == "high" else ""
        return f"[{time_str}] {priority_marker}{self.guild_name}: {self.description}"


class EventEmitter:
    """
    Manages event creation and broadcasting for the simulation.

    This is the central hub for generating narrative events.
    The simulation engine calls these methods to create events
    that viewers see in real-time.
    """

    def __init__(self):
        self.events: List[SimulationEvent] = []
        self.event_listeners = []  # For future websocket broadcasting
        self.current_tick = 0  # Track tick number for replay

    def emit(self, guild_id: int, guild_name: str, event_type: EventType,
             description: str, details: Dict[str, Any] = None,
             priority: str = "normal", tags: List[str] = None) -> SimulationEvent:
        """
        Create and emit a new event.

        This is the main method used throughout the simulation to generate
        narrative events for the viewer feed.

        Args:
            guild_id: ID of the guild this event belongs to
            guild_name: Name of the guild for display
            event_type: Type of event (affects processing and display)
            description: Human-readable description for viewers
            details: Structured data for programmatic use
            priority: Event importance level
            tags: Additional categorization tags

        Returns:
            The created event
        """
        event = SimulationEvent(
            timestamp=datetime.now(),
            guild_id=guild_id,
            guild_name=guild_name,
            event_type=event_type,
            description=description,
            details=details or {},
            priority=priority,
            tags=tags or [],
            tick_number=self.current_tick
        )

        self.events.append(event)
        self._broadcast_event(event)
        return event

    def increment_tick(self):
        """Increment the tick counter for synchronized replay"""
        self.current_tick += 1

    def _broadcast_event(self, event: SimulationEvent):
        """
        Broadcast event to all listeners.

        In the full implementation, this would send the event
        via websockets to connected viewers.
        """
        # For now, just print to console
        print(event)

        # Future: Send via websocket to web clients
        # for listener in self.event_listeners:
        #     listener.send_event(event)

    # === Convenience Methods for Common Events ===

    def expedition_start(self, guild_id: int, guild_name: str,
                        party_details: Dict[str, Any]):
        """Emit expedition start event"""
        return self.emit(
            guild_id, guild_name, EventType.EXPEDITION_START,
            f"The {guild_name} begin their expedition into the depths!",
            details=party_details,
            priority="high",
            tags=["expedition", "start"]
        )

    def expedition_complete(self, guild_id: int, guild_name: str,
                           floors: int, gold: int):
        """Emit expedition completion event"""
        return self.emit(
            guild_id, guild_name, EventType.EXPEDITION_COMPLETE,
            f"The {guild_name} complete the dungeon! Floors: {floors}, Gold: {gold}",
            details={'floors': floors, 'gold': gold},
            priority="high",
            tags=["expedition", "complete"]
        )

    def expedition_retreat(self, guild_id: int, guild_name: str,
                          morale: int, summary: Dict[str, Any]):
        """Emit expedition retreat event"""
        return self.emit(
            guild_id, guild_name, EventType.EXPEDITION_RETREAT,
            f"The {guild_name} retreat from the dungeon! (Final morale: {morale})",
            details=summary,
            priority="high",
            tags=["expedition", "retreat"]
        )

    def expedition_wipe(self, guild_id: int, guild_name: str,
                       final_floor: int, summary: Dict[str, Any]):
        """Emit expedition wipe event"""
        return self.emit(
            guild_id, guild_name, EventType.EXPEDITION_WIPE,
            f"DISASTER! The {guild_name} have been wiped out on Floor {final_floor}!",
            details=summary,
            priority="critical",
            tags=["expedition", "wipe", "death"]
        )

    def floor_enter(self, guild_id: int, guild_name: str,
                   floor_num: int, room_count: int):
        """Emit floor entry event"""
        priority = "high" if floor_num >= 5 else "normal"  # Deeper floors more exciting
        return self.emit(
            guild_id, guild_name, EventType.FLOOR_ENTER,
            f"Descending to Floor {floor_num} ({room_count} rooms await...)",
            details={'floor': floor_num, 'room_count': room_count},
            priority=priority,
            tags=["exploration", "floor"]
        )

    def combat_start(self, guild_id: int, guild_name: str,
                    enemy_count: int, is_boss: bool = False):
        """Emit combat start event"""
        encounter_type = "Boss" if is_boss else "Combat"
        return self.emit(
            guild_id, guild_name, EventType.COMBAT_START,
            f"{encounter_type} encounter! {enemy_count} enemies appear!",
            details={'enemy_count': enemy_count, 'is_boss': is_boss},
            priority="high" if is_boss else "normal",
            tags=["combat", "start"] + (["boss"] if is_boss else [])
        )

    def enemy_appears(self, guild_id: int, guild_name: str,
                     enemy_name: str, enemy_type: str, is_boss: bool = False):
        """Emit enemy appearance event"""
        return self.emit(
            guild_id, guild_name, EventType.ENEMY_APPEARS,
            f"{enemy_name} appears! ({enemy_type})",
            details={'enemy': enemy_name, 'enemy_type': enemy_type, 'is_boss': is_boss},
            priority="high" if is_boss else "normal",
            tags=["combat", "enemy"] + (["boss"] if is_boss else [])
        )

    def enemy_defeated(self, guild_id: int, guild_name: str, enemy_name: str):
        """Emit enemy defeated event"""
        return self.emit(
            guild_id, guild_name, EventType.ENEMY_DEFEATED,
            f"{enemy_name} has been defeated!",
            details={'enemy': enemy_name},
            priority="normal",
            tags=["combat", "victory"]
        )

    def boss_ability_triggered(self, guild_id: int, guild_name: str,
                              boss_name: str, ability: str, description: str):
        """Emit boss ability trigger event"""
        return self.emit(
            guild_id, guild_name, EventType.BOSS_ABILITY_TRIGGERED,
            f"{boss_name} {description}",
            details={'boss': boss_name, 'ability': ability},
            priority="high",
            tags=["combat", "boss", "ability"]
        )

    def character_attack(self, guild_id: int, guild_name: str,
                        character_name: str, damage: int, critical: bool = False):
        """Emit character attack event"""
        if critical:
            description = f"{character_name} lands a CRITICAL HIT for {damage} damage!"
            event_type = EventType.ATTACK_CRITICAL
            priority = "high"
        else:
            description = f"{character_name} attacks for {damage} damage"
            event_type = EventType.ATTACK_HIT
            priority = "normal"

        return self.emit(
            guild_id, guild_name, event_type, description,
            details={'character': character_name, 'damage': damage, 'critical': critical},
            priority=priority,
            tags=["combat", "attack"]
        )

    def debuff_applied(self, guild_id: int, guild_name: str,
                      target_name: str, debuff_type: str, source: str, duration: int):
        """Emit debuff application event"""
        return self.emit(
            guild_id, guild_name, EventType.DEBUFF_APPLIED,
            f"{target_name} is {debuff_type} by {source}'s attack! ({duration} rounds)",
            details={'target': target_name, 'debuff': debuff_type, 'source': source, 'duration': duration},
            priority="normal",
            tags=["combat", "debuff", "status"]
        )

    def debuff_expired(self, guild_id: int, guild_name: str,
                      character_name: str, debuff_type: str):
        """Emit debuff expiration event"""
        return self.emit(
            guild_id, guild_name, EventType.DEBUFF_EXPIRED,
            f"{character_name} recovers from {debuff_type}",
            details={'character': character_name, 'debuff': debuff_type},
            priority="low",
            tags=["status", "recovery"]
        )

    def status_damage(self, guild_id: int, guild_name: str,
                     character_name: str, damage: int, source: str):
        """Emit status effect damage event"""
        return self.emit(
            guild_id, guild_name, EventType.STATUS_DAMAGE,
            f"{character_name} takes {damage} {source} damage!",
            details={'character': character_name, 'damage': damage, 'source': source},
            priority="normal",
            tags=["damage", "status"]
        )

    def character_unconscious(self, guild_id: int, guild_name: str, character_name: str):
        """Emit character unconscious event"""
        return self.emit(
            guild_id, guild_name, EventType.CHARACTER_UNCONSCIOUS,
            f"{character_name} has been knocked unconscious!",
            details={'character': character_name},
            priority="high",
            tags=["character", "damage", "unconscious"]
        )

    def character_death_test(self, guild_id: int, guild_name: str,
                           character_name: str, rolls: List[int], survived: bool):
        """Emit character death test event"""
        rolls_str = ", ".join(str(r) for r in rolls)
        result = "SURVIVES" if survived else "DIES"

        return self.emit(
            guild_id, guild_name, EventType.CHARACTER_DEATH_TEST,
            f"{character_name} death test: [{rolls_str}] - {result}!",
            details={'character': character_name, 'rolls': rolls, 'survived': survived},
            priority="critical",
            tags=["character", "death", "test"]
        )

    def character_dies(self, guild_id: int, guild_name: str, character_name: str):
        """Emit character death event"""
        return self.emit(
            guild_id, guild_name, EventType.CHARACTER_DIES,
            f"💀 {character_name} has DIED! They will not return...",
            details={'character': character_name},
            priority="critical",
            tags=["character", "death", "permanent"]
        )

    def trap_triggered(self, guild_id: int, guild_name: str,
                      character_name: str, damage: int, trap_type: str = "trap"):
        """Emit trap triggered event"""
        return self.emit(
            guild_id, guild_name, EventType.TRAP_TRIGGERED,
            f"{character_name} triggers a {trap_type}! Takes {damage} damage!",
            details={'character': character_name, 'damage': damage, 'trap_type': trap_type},
            priority="normal",
            tags=["trap", "damage"]
        )

    def treasure_found(self, guild_id: int, guild_name: str,
                      gold_amount: int, finder_name: str = None):
        """Emit treasure found event"""
        if finder_name:
            description = f"{finder_name} finds {gold_amount} gold!"
        else:
            description = f"The party finds {gold_amount} gold!"

        return self.emit(
            guild_id, guild_name, EventType.TREASURE_FOUND,
            description,
            details={'gold': gold_amount, 'character': finder_name},
            priority="normal",
            tags=["treasure", "gold"]
        )

    def morale_check(self, guild_id: int, guild_name: str,
                    roll: int, morale: int, success: bool):
        """Emit morale check event"""
        result = "Continue deeper!" if success else "Time to retreat!"
        return self.emit(
            guild_id, guild_name, EventType.MORALE_CHECK,
            f"Morale check: {roll} vs {morale} - {result}",
            details={'roll': roll, 'morale': morale, 'success': success},
            priority="high",
            tags=["morale", "party"]
        )

    # === Event Filtering and Analysis ===

    def get_recent_events(self, count: int = 50) -> List[SimulationEvent]:
        """Get the most recent events for display"""
        return self.events[-count:] if len(self.events) > count else self.events

    def get_events_for_guild(self, guild_id: int) -> List[SimulationEvent]:
        """Get all events for a specific guild"""
        return [event for event in self.events if event.guild_id == guild_id]

    def get_events_by_type(self, event_type: EventType) -> List[SimulationEvent]:
        """Get all events of a specific type"""
        return [event for event in self.events if event.event_type == event_type]

    def get_combat_events(self) -> List[SimulationEvent]:
        """Get all combat-related events"""
        return [event for event in self.events if event.is_combat_event()]

    def get_enemy_events(self) -> List[SimulationEvent]:
        """Get all enemy-related events"""
        return [event for event in self.events if event.is_enemy_event()]

    def get_death_events(self) -> List[SimulationEvent]:
        """Get all death-related events"""
        return [event for event in self.events if event.is_death_related()]

    def get_status_effect_events(self) -> List[SimulationEvent]:
        """Get all status effect events"""
        return [event for event in self.events if event.is_status_effect_event()]

    def clear_events(self):
        """Clear all events (for testing or new expedition)"""
        self.events.clear()
        self.current_tick = 0

    def get_event_summary(self) -> Dict[str, int]:
        """Get summary statistics of all events"""
        summary = {}
        for event in self.events:
            event_type = event.event_type.value
            summary[event_type] = summary.get(event_type, 0) + 1
        return summary


