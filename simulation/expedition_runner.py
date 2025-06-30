"""
Expedition Runner - Orchestrates complete dungeon expeditions for multiple parties.

This is the main simulation engine that coordinates all our existing resolvers
to run parties through dungeons simultaneously with timed event emission.

Updated to support the new enemy event system.
"""

import sys
import os
# Add the project root to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from models.character import Character, CharacterRole
from models.party import Party
from models.events import EventType, EventEmitter
from simulation.dungeon_generator import DungeonGenerator, RoomType
from simulation.combat_resolver import CombatResolver
from simulation.trap_resolver import TrapResolver
from simulation.treasure_resolver import TreasureResolver
from simulation.morale_checker import MoraleChecker


@dataclass
class ExpeditionResult:
    """Results of a complete expedition for a single party"""
    guild_id: int
    guild_name: str
    floors_cleared: int
    rooms_cleared: int
    gold_found: int
    monsters_defeated: int
    retreated: bool
    wiped: bool
    start_time: datetime
    end_time: datetime


@dataclass
class SimulationTick:
    """Represents a single tick of events to emit"""
    tick_number: int
    timestamp: float
    events: List[Dict] = field(default_factory=list)


class EventEmitterWrapper:
    """
    Wrapper to make a simple callback function compatible with EventEmitter interface.
    This allows combat_resolver to work with our callback-based event system.
    
    Updated to support all the new enemy-related events.
    """
    def __init__(self, callback_fn):
        self.callback = callback_fn
        self.events = []  # Track events for compatibility

    def emit(self, guild_id, guild_name, event_type, description, details=None, priority="normal", tags=None):
        """Forward to callback with correct signature"""
        self.callback(guild_id, guild_name, event_type, description, priority, details)

    def increment_tick(self):
        """For compatibility with tick tracking"""
        pass

    def clear_events(self):
        """For compatibility with event clearing"""
        self.events.clear()

    # === Combat Events ===
    
    def combat_start(self, guild_id, guild_name, enemy_count, is_boss=False):
        """Wrapper for combat start events"""
        encounter_type = "Boss" if is_boss else "Combat"
        self.callback(
            guild_id, guild_name, EventType.COMBAT_START,
            f"{encounter_type} encounter! {enemy_count} enemies appear!",
            "high" if is_boss else "normal",
            {'enemy_count': enemy_count, 'is_boss': is_boss}
        )

    def enemy_appears(self, guild_id, guild_name, enemy_name, enemy_type, is_boss=False):
        """Emit enemy appearance event"""
        self.callback(
            guild_id, guild_name, EventType.ENEMY_APPEARS,
            f"{enemy_name} appears! ({enemy_type})",
            "high" if is_boss else "normal",
            {'enemy': enemy_name, 'enemy_type': enemy_type, 'is_boss': is_boss}
        )

    def enemy_defeated(self, guild_id, guild_name, enemy_name):
        """Emit enemy defeated event"""
        self.callback(
            guild_id, guild_name, EventType.ENEMY_DEFEATED,
            f"{enemy_name} has been defeated!",
            "normal",
            {'enemy': enemy_name}
        )

    def boss_ability_triggered(self, guild_id, guild_name, boss_name, ability, description):
        """Emit boss ability trigger event"""
        self.callback(
            guild_id, guild_name, EventType.BOSS_ABILITY_TRIGGERED,
            f"{boss_name} {description}",
            "high",
            {'boss': boss_name, 'ability': ability}
        )

    # === Character Events ===
    
    def character_attack(self, guild_id, guild_name, character_name, damage, critical=False):
        """Wrapper for attack events"""
        if critical:
            self.callback(
                guild_id, guild_name, EventType.ATTACK_CRITICAL,
                f"{character_name} lands a CRITICAL HIT for {damage} damage!",
                "high",
                {'character': character_name, 'damage': damage, 'critical': True}
            )
        else:
            self.callback(
                guild_id, guild_name, EventType.ATTACK_HIT,
                f"{character_name} attacks for {damage} damage",
                "normal",
                {'character': character_name, 'damage': damage, 'critical': False}
            )

    def character_unconscious(self, guild_id, guild_name, character_name):
        """Wrapper for unconscious events"""
        self.callback(
            guild_id, guild_name, EventType.CHARACTER_UNCONSCIOUS,
            f"{character_name} has been knocked unconscious!",
            "high",
            {'character': character_name}
        )

    def character_dies(self, guild_id, guild_name, character_name):
        """Wrapper for death events"""
        self.callback(
            guild_id, guild_name, EventType.CHARACTER_DIES,
            f"💀 {character_name} has DIED! They will not return...",
            "critical",
            {'character': character_name}
        )

    def character_death_test(self, guild_id, guild_name, character_name, rolls, survived):
        """Emit character death test event"""
        rolls_str = ", ".join(str(r) for r in rolls)
        result = "SURVIVES" if survived else "DIES"
        
        self.callback(
            guild_id, guild_name, EventType.CHARACTER_DEATH_TEST,
            f"{character_name} death test: [{rolls_str}] - {result}!",
            "critical",
            {'character': character_name, 'rolls': rolls, 'survived': survived}
        )

    # === Status Effects ===
    
    def debuff_applied(self, guild_id, guild_name, target_name, debuff_type, source, duration):
        """Emit debuff application event"""
        self.callback(
            guild_id, guild_name, EventType.DEBUFF_APPLIED,
            f"{target_name} is {debuff_type} by {source}'s attack! ({duration} rounds)",
            "normal",
            {'target': target_name, 'debuff': debuff_type, 'source': source, 'duration': duration}
        )

    def debuff_expired(self, guild_id, guild_name, character_name, debuff_type):
        """Emit debuff expiration event"""
        self.callback(
            guild_id, guild_name, EventType.DEBUFF_EXPIRED,
            f"{character_name} recovers from {debuff_type}",
            "low",
            {'character': character_name, 'debuff': debuff_type}
        )

    def status_damage(self, guild_id, guild_name, character_name, damage, source):
        """Emit status effect damage event"""
        self.callback(
            guild_id, guild_name, EventType.STATUS_DAMAGE,
            f"{character_name} takes {damage} {source} damage!",
            "normal",
            {'character': character_name, 'damage': damage, 'source': source}
        )

    # === Other Events ===
    
    def expedition_start(self, guild_id, guild_name, party_details):
        """Emit expedition start event"""
        self.callback(
            guild_id, guild_name, EventType.EXPEDITION_START,
            f"The {guild_name} begin their expedition into the depths!",
            "high",
            party_details
        )

    def expedition_complete(self, guild_id, guild_name, floors, gold):
        """Emit expedition completion event"""
        self.callback(
            guild_id, guild_name, EventType.EXPEDITION_COMPLETE,
            f"The {guild_name} complete the dungeon! Floors: {floors}, Gold: {gold}",
            "high",
            {'floors': floors, 'gold': gold}
        )

    def expedition_retreat(self, guild_id, guild_name, morale, summary):
        """Emit expedition retreat event"""
        self.callback(
            guild_id, guild_name, EventType.EXPEDITION_RETREAT,
            f"The {guild_name} retreat from the dungeon! (Final morale: {morale})",
            "high",
            summary
        )

    def expedition_wipe(self, guild_id, guild_name, final_floor, summary):
        """Emit expedition wipe event"""
        self.callback(
            guild_id, guild_name, EventType.EXPEDITION_WIPE,
            f"DISASTER! The {guild_name} have been wiped out on Floor {final_floor}!",
            "critical",
            summary
        )

    def floor_enter(self, guild_id, guild_name, floor_num, room_count):
        """Emit floor entry event"""
        priority = "high" if floor_num >= 5 else "normal"
        self.callback(
            guild_id, guild_name, EventType.FLOOR_ENTER,
            f"Descending to Floor {floor_num} ({room_count} rooms await...)",
            priority,
            {'floor': floor_num, 'room_count': room_count}
        )

    def trap_triggered(self, guild_id, guild_name, character_name, damage, trap_type="trap"):
        """Emit trap triggered event"""
        self.callback(
            guild_id, guild_name, EventType.TRAP_TRIGGERED,
            f"{character_name} triggers a {trap_type}! Takes {damage} damage!",
            "normal",
            {'character': character_name, 'damage': damage, 'trap_type': trap_type}
        )

    def treasure_found(self, guild_id, guild_name, gold_amount, finder_name=None):
        """Emit treasure found event"""
        if finder_name:
            description = f"{finder_name} finds {gold_amount} gold!"
        else:
            description = f"The party finds {gold_amount} gold!"
        
        self.callback(
            guild_id, guild_name, EventType.TREASURE_FOUND,
            description,
            "normal",
            {'gold': gold_amount, 'character': finder_name}
        )

    def morale_check(self, guild_id, guild_name, roll, morale, success):
        """Emit morale check event"""
        result = "Continue deeper!" if success else "Time to retreat!"
        self.callback(
            guild_id, guild_name, EventType.MORALE_CHECK,
            f"Morale check: {roll} vs {morale} - {result}",
            "high",
            {'roll': roll, 'morale': morale, 'success': success}
        )


class ExpeditionRunner:
    """
    Orchestrates expeditions for multiple parties through a dungeon.

    Simply coordinates our existing resolvers and manages timing/synchronization.
    All actual game mechanics are handled by the specialized resolvers.
    """

    def __init__(self,
                 seed: int,
                 emit_event_callback: Optional[Callable] = None,
                 tick_duration: float = 2.0,
                 max_floors: int = 3):
        """
        Initialize the expedition runner.

        Args:
            seed: Random seed for dungeon generation
            emit_event_callback: Optional callback function for events (for backwards compatibility)
            tick_duration: Seconds between event ticks (default 2.0)
            max_floors: Maximum floors before expedition ends (default 3)
        """
        self.seed = seed
        self.tick_duration = tick_duration
        self.max_floors = max_floors

        # Only dungeon generation uses the seed - everything else should be random!
        import random

        # Create event handling based on whether callback was provided
        if emit_event_callback:
            self.emit_event = emit_event_callback
            # Create wrapper for combat resolver
            self.event_emitter_wrapper = EventEmitterWrapper(emit_event_callback)
        else:
            # Use default EventEmitter
            self.event_emitter = EventEmitter()
            self.emit_event = self.event_emitter.emit
            self.event_emitter_wrapper = self.event_emitter

        # Our existing resolvers handle all the mechanics
        # ONLY dungeon generator gets the seed - so all parties face same dungeon
        self.dungeon_generator = DungeonGenerator(seed)

        # All other resolvers use unseeded random - so outcomes vary each run!
        # Each gets its own RNG instance for true randomness
        self.combat_resolver = CombatResolver(self.event_emitter_wrapper, random.Random())
        self.trap_resolver = TrapResolver(random.Random(), self.emit_event)
        self.treasure_resolver = TreasureResolver(random.Random(), self.emit_event)
        self.morale_checker = MoraleChecker(random.Random(), self.emit_event)

        # Track ticks for synchronized viewing
        self.current_tick = 0
        self.tick_events: List[SimulationTick] = []

    def run_expedition(self, parties: List[Party]) -> List[ExpeditionResult]:
        """
        Run a complete expedition for multiple parties.

        Args:
            parties: List of Party objects to run through the dungeon

        Returns:
            List of ExpeditionResult objects, one per party
        """
        start_time = datetime.now()

        # Reset state
        self.current_tick = 0
        self.tick_events = []

        # Prepare parties
        active_parties = []
        for party in parties:
            party.reset_for_new_expedition()
            active_parties.append(party)

        # Announce expedition start
        self._emit_expedition_starts(active_parties)
        self._add_tick()

        # Process floors
        for floor_number in range(1, self.max_floors + 1):
            if not active_parties:
                break

            # Generate floor (same for all parties)
            rooms = self.dungeon_generator.generate_floor(floor_number)

            # Announce floor entry
            self._emit_floor_entries(active_parties, floor_number, len(rooms))
            self._add_tick()

            # Process each room
            for room_index, room in enumerate(rooms):
                if not active_parties:
                    break

                # Room entry
                self._emit_room_entries(active_parties, room, floor_number, room_index + 1)
                self._add_tick()

                # Process room contents for each party
                for party in active_parties[:]:  # Copy to allow removal
                    if party.is_party_wiped():
                        self._handle_party_wipe(party, floor_number, room_index + 1)
                        active_parties.remove(party)
                        continue

                    # Healing fountain is special
                    if room.room_type == RoomType.HEALING_FOUNTAIN:
                        self._process_healing_fountain(party)
                    else:
                        # Handle trap component
                        if room.room_type in [RoomType.TRAP, RoomType.BOTH]:
                            self.trap_resolver.resolve_trap(party, floor_number)
                            self._add_tick()

                            # Check if party wiped from trap
                            if party.is_party_wiped():
                                self._handle_party_wipe(party, floor_number, room_index + 1)
                                active_parties.remove(party)
                                continue

                        # Handle combat component
                        if room.room_type in [RoomType.COMBAT, RoomType.BOTH, RoomType.BOSS]:
                            self.combat_resolver.resolve_combat(party, room)
                            self._add_tick()

                            # Check if party wiped from combat
                            if party.is_party_wiped():
                                self._handle_party_wipe(party, floor_number, room_index + 1)
                                active_parties.remove(party)
                                continue

                        # Handle treasure (only if party survived to search)
                        if room.room_type != RoomType.HEALING_FOUNTAIN and not party.is_party_wiped():
                            self.treasure_resolver.resolve_treasure(
                                party, floor_number, room.is_boss_room
                            )
                            self._add_tick()

                    # Room complete - check morale (only if party survived)
                    if not party.is_party_wiped():
                        party.complete_room()
                        if not self._check_party_morale(party, floor_number, is_last_room=(room_index == len(rooms) - 1)):
                            active_parties.remove(party)

                self._add_tick()  # Pacing tick between rooms

            # Floor complete for surviving parties
            for party in active_parties:
                party.complete_floor()

            # Floor completion morale check (with disadvantage)
            for party in active_parties[:]:
                morale_result = self.morale_checker.check_morale(party, is_floor_completion=True)
                if not morale_result.continues_expedition:
                    active_parties.remove(party)

            self._add_tick()

        # Generate results
        end_time = datetime.now()
        results = []
        for party in parties:
            results.append(ExpeditionResult(
                guild_id=party.guild_id,
                guild_name=party.guild_name,
                floors_cleared=party.floors_cleared,
                rooms_cleared=party.rooms_cleared,
                gold_found=party.gold_found,
                monsters_defeated=party.monsters_defeated,
                retreated=party.retreated,
                wiped=party.is_party_wiped(),
                start_time=start_time,
                end_time=end_time
            ))

        return results

    def _emit_expedition_starts(self, parties: List[Party]):
        """Emit expedition start events for all parties"""
        for party in parties:
            self.emit_event(
                party.guild_id, party.guild_name, EventType.EXPEDITION_START,
                f"The {party.guild_name} begin their expedition!",
                priority="high",
                details={'party_size': len(party.alive_members())}
            )

    def _emit_floor_entries(self, parties: List[Party], floor_number: int, room_count: int):
        """Emit floor entry events for all parties"""
        for party in parties:
            self.emit_event(
                party.guild_id, party.guild_name, EventType.FLOOR_ENTER,
                f"Descending to floor {floor_number} ({room_count} rooms await...)",
                details={'floor': floor_number, 'rooms': room_count}
            )

    def _emit_room_entries(self, parties: List[Party], room, floor_number: int, room_number: int):
        """Emit room entry events for all parties"""
        room_desc = self._describe_room(room, room_number)
        for party in parties:
            self.emit_event(
                party.guild_id, party.guild_name, EventType.ROOM_ENTER,
                f"Entering {room_desc}",
                details={'floor': floor_number, 'room': room_number, 'type': room.room_type.value}
            )

    def _describe_room(self, room, room_number: int) -> str:
        """Generate descriptive text for a room"""
        descriptions = {
            RoomType.COMBAT: f"a monster lair (Room {room_number})",
            RoomType.TRAP: f"a trapped corridor (Room {room_number})",
            RoomType.BOTH: f"a dangerous chamber (Room {room_number})",
            RoomType.BOSS: f"a boss chamber (Room {room_number})",
            RoomType.HEALING_FOUNTAIN: f"a healing sanctuary (Room {room_number})"
        }
        return descriptions.get(room.room_type, f"Room {room_number}")

    def _process_healing_fountain(self, party: Party):
        """Process healing fountain room"""
        total_healed = 0
        for member in party.members:
            if member.is_alive and member.current_hp < member.max_hp:
                healed = member.heal(member.max_hp - member.current_hp)
                total_healed += healed

        self.emit_event(
            party.guild_id, party.guild_name, EventType.ROOM_ENTER,
            f"A healing fountain! The party restores {total_healed} HP",
            details={'healed': total_healed}
        )

    def _check_party_morale(self, party: Party, floor_number: int, is_last_room: bool) -> bool:
        """
        Check if party continues after room completion.

        Returns:
            True if party continues, False if they retreat
        """
        if party.is_party_wiped():
            return False

        # Don't check morale on last room of floor (will check at floor completion)
        if is_last_room:
            return True

        morale_result = self.morale_checker.check_morale(party, is_floor_completion=False)
        return morale_result.continues_expedition

    def _handle_party_wipe(self, party: Party, floor_number: int, room_number: int):
        """Handle when a party is completely wiped out"""
        self.emit_event(
            party.guild_id, party.guild_name, EventType.EXPEDITION_WIPE,
            f"DISASTER! The {party.guild_name} have been lost to the dungeon!",
            priority="critical",
            details={'final_floor': floor_number, 'final_room': room_number}
        )

    def _add_tick(self):
        """Add a tick marker for event synchronization"""
        tick = SimulationTick(
            tick_number=self.current_tick,
            timestamp=time.time() + (self.current_tick * self.tick_duration),
            events=[]  # Events are already emitted by resolvers
        )
        self.tick_events.append(tick)
        self.current_tick += 1

    def emit_tick_schedule(self, real_time: bool = True):
        """
        Emit events with proper timing for viewing.

        Args:
            real_time: If True, wait between ticks. If False, emit immediately.
        """
        for tick in self.tick_events:
            if real_time and tick.tick_number > 0:
                time.sleep(self.tick_duration)
            # In real implementation, this would coordinate with websockets
            print(f"[Tick {tick.tick_number:03d}]")

