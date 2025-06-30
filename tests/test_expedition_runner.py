import pytest
import random
from datetime import datetime
from simulation.expedition_runner import ExpeditionRunner, ExpeditionResult
from models.character import Character, CharacterRole
from models.party import Party
from models.events import EventType, EventEmitter
from simulation.dungeon_generator import RoomType

def create_basic_party(guild_id=1, name="Test Guild") -> Party:
    return Party(
        guild_id=guild_id,
        guild_name=name,
        members=[
            Character(name="Alice", role=CharacterRole.STRIKER, guild_id=guild_id, might=12, grit=10, wit=8, luck=10),
            Character(name="Ben", role=CharacterRole.BURGLAR, guild_id=guild_id, might=9, grit=9, wit=11, luck=13),
            Character(name="Cora", role=CharacterRole.SUPPORT, guild_id=guild_id, might=7, grit=12, wit=14, luck=9),
            Character(name="Dax", role=CharacterRole.CONTROLLER, guild_id=guild_id, might=8, grit=11, wit=13, luck=11)
        ]
    )


class DummyEventCollector:
    def __init__(self):
        self.events = []

    def emit(self, guild_id, guild_name, event_type, description, priority="normal", details=None):
        self.events.append({
            "guild_id": guild_id,
            "guild_name": guild_name,
            "type": event_type,
            "desc": description,
            "priority": priority,
            "details": details or {}
        })


# === TEST CASES ===

def test_expedition_runs_to_completion_without_errors():
    collector = DummyEventCollector()
    party = create_basic_party()
    runner = ExpeditionRunner(seed=42, emit_event_callback=collector.emit, tick_duration=0.0, max_floors=1)

    results = runner.run_expedition([party])

    assert isinstance(results, list)
    assert len(results) == 1
    result = results[0]

    assert result.guild_name == "Test Guild"
    assert result.floors_cleared >= 0
    assert result.rooms_cleared >= 0
    assert isinstance(result.start_time, datetime)
    assert isinstance(result.end_time, datetime)
    assert result.end_time >= result.start_time


def test_expedition_emits_start_and_floor_events():
    collector = DummyEventCollector()
    party = create_basic_party()
    runner = ExpeditionRunner(seed=99, emit_event_callback=collector.emit, tick_duration=0.0, max_floors=1)
    runner.run_expedition([party])

    event_types = [e["type"] for e in collector.events]
    assert EventType.EXPEDITION_START in event_types
    assert EventType.FLOOR_ENTER in event_types


def test_party_retreat_or_wipe_possible():
    # Run 5 simulations to try to force a retreat or wipe (random chance)
    retreat_detected = False
    wipe_detected = False

    for _ in range(5):
        collector = DummyEventCollector()
        party = create_basic_party()
        runner = ExpeditionRunner(seed=123, emit_event_callback=collector.emit, tick_duration=0.0, max_floors=2)
        results = runner.run_expedition([party])
        result = results[0]

        if result.retreated:
            retreat_detected = True
        if result.wiped:
            wipe_detected = True

        if retreat_detected and wipe_detected:
            break

    assert retreat_detected or wipe_detected  # At least one condition should have happened


def test_tick_schedule_increments_correctly():
    collector = DummyEventCollector()
    party = create_basic_party()
    runner = ExpeditionRunner(seed=555, emit_event_callback=collector.emit, tick_duration=0.0, max_floors=1)
    runner.run_expedition([party])

    ticks = runner.tick_events
    assert isinstance(ticks, list)
    assert len(ticks) >= 1
    for i, tick in enumerate(ticks):
        assert tick.tick_number == i


def test_expedition_result_consistency_across_runs():
    # Same seed → same dungeon layout, but RNG divergence causes different outcomes
    party1 = create_basic_party()
    party2 = create_basic_party()

    collector = DummyEventCollector()
    runner = ExpeditionRunner(seed=2024, emit_event_callback=collector.emit, tick_duration=0.0, max_floors=2)

    result1 = runner.run_expedition([party1])[0]
    result2 = runner.run_expedition([party2])[0]

    assert result1 != result2 or result1.gold_found != result2.gold_found  # Likely, due to randomness

def test_healing_fountain_room_heals_characters(monkeypatch):
    from simulation.dungeon_generator import RoomType
    collector = DummyEventCollector()
    party = create_basic_party()
    for member in party.members:
        member.current_hp = member.max_hp - 5  # Simulate damage

    runner = ExpeditionRunner(seed=999, emit_event_callback=collector.emit, tick_duration=0.0, max_floors=1)

    monkeypatch.setattr(runner.dungeon_generator, "generate_floor", lambda floor: [
        type("FakeRoom", (), {
            "room_type": RoomType.HEALING_FOUNTAIN,
            "is_boss_room": False,
            "is_final_room": False
        })()
    ])

    results = runner.run_expedition([party])
    assert any("healing fountain" in e["desc"].lower() for e in collector.events)
    assert all(m.current_hp == m.max_hp for m in party.members)

