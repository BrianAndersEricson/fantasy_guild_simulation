import pytest
import random
from simulation.trap_resolver import TrapResolver, TrapOutcome
from models.character import Character, CharacterRole
from models.party import Party
from models.events import EventType


def create_test_party(with_burglar=True) -> Party:
    roles = [CharacterRole.STRIKER, CharacterRole.SUPPORT, CharacterRole.CONTROLLER]
    if with_burglar:
        roles.insert(1, CharacterRole.BURGLAR)

    members = [
        Character(name=f"Member{i}", role=role, guild_id=1, might=10, grit=10, wit=10, luck=10)
        for i, role in enumerate(roles)
    ]
    return Party(guild_id=1, guild_name="Trap Testers", members=members)


class DummyEventLogger:
    def __init__(self):
        self.events = []

    def __call__(self, guild_id, guild_name, event_type, description, priority="normal", details=None):
        self.events.append({
            "event_type": event_type,
            "description": description,
            "priority": priority,
            "details": details or {}
        })


# === TEST CASES ===

def test_burglar_priority_for_detection():
    party = create_test_party(with_burglar=True)
    resolver = TrapResolver(rng=random.Random(1))
    detector = resolver.get_trap_detector(party)
    assert detector.role == CharacterRole.BURGLAR

def test_random_detector_fallback_when_burglar_unconscious():
    # Valid party with all roles
    members = [
        Character(name="Striker", role=CharacterRole.STRIKER, guild_id=1),
        Character(name="Burglar", role=CharacterRole.BURGLAR, guild_id=1),
        Character(name="Support", role=CharacterRole.SUPPORT, guild_id=1),
        Character(name="Controller", role=CharacterRole.CONTROLLER, guild_id=1),
    ]
    party = Party(guild_id=1, guild_name="Unconscious Burglar Squad", members=members)

    # Knock out the burglar using correct method
    burglar = party.get_member_by_role(CharacterRole.BURGLAR)
    burglar.take_damage(burglar.max_hp)  # Bring to 0 HP using system logic

    resolver = TrapResolver(rng=random.Random(1))
    detector = resolver.get_trap_detector(party)

    # Assert fallback occurred — burglar was skipped
    assert detector != burglar
    assert detector.is_alive

def test_critical_success(monkeypatch):
    rng = random.Random()
    logger = DummyEventLogger()
    resolver = TrapResolver(rng, emit_event_callback=logger)

    party = create_test_party()
    monkeypatch.setattr(resolver.rng, "randint", lambda a, b: 20)

    result = resolver.resolve_trap(party, floor_level=1)

    assert result.outcome == TrapOutcome.CRITICAL_SUCCESS
    assert any("critical success" in e["description"].lower() for e in logger.events)
    assert any(e["event_type"] == EventType.TRAP_DETECTED for e in logger.events)


def test_critical_failure(monkeypatch):
    rng = random.Random()
    logger = DummyEventLogger()
    resolver = TrapResolver(rng, emit_event_callback=logger)

    party = create_test_party()
    monkeypatch.setattr(resolver.rng, "randint", lambda a, b: 1)  # Force nat 1

    result = resolver.resolve_trap(party, floor_level=1)

    assert result.outcome == TrapOutcome.CRITICAL_FAILURE
    assert result.damage_dealt > 0
    assert result.damage_target is not None
    assert result.debuff_applied is not None
    assert any(e["event_type"] == EventType.TRAP_TRIGGERED for e in logger.events)
    assert any("critically fails" in e["description"].lower() for e in logger.events)


def test_normal_success(monkeypatch):
    rng = random.Random()
    logger = DummyEventLogger()
    resolver = TrapResolver(rng, emit_event_callback=logger)

    party = create_test_party()
    # Simulate base roll = 15, luck bonus = 2, total = 17 vs DC = 11
    monkeypatch.setattr(resolver.rng, "randint", lambda a, b: 15)

    party.members[0].luck = 14  # modifier = +2

    result = resolver.resolve_trap(party, floor_level=1)
    assert result.outcome == TrapOutcome.SUCCESS
    assert any("disarms the trap" in e["description"].lower() for e in logger.events)


def test_failure_triggers_damage(monkeypatch):
    rng = random.Random()
    logger = DummyEventLogger()
    resolver = TrapResolver(rng, emit_event_callback=logger)

    party = create_test_party()
    monkeypatch.setattr(resolver.rng, "randint", lambda a, b: 2)  # low base roll

    result = resolver.resolve_trap(party, floor_level=2)

    assert result.outcome == TrapOutcome.FAILURE
    assert result.damage_dealt > 0
    assert result.damage_target is not None
    assert any("trap springs" in e["description"].lower() for e in logger.events)


def test_trap_dc_scales_with_floor(monkeypatch):
    rng = random.Random()
    resolver = TrapResolver(rng)

    party = create_test_party()
    monkeypatch.setattr(resolver.rng, "randint", lambda a, b: 10)  # consistent base roll

    result1 = resolver.resolve_trap(party, floor_level=1)
    result2 = resolver.resolve_trap(party, floor_level=5)

    assert result1.trap_dc == 11
    assert result2.trap_dc == 15
    assert result2.trap_dc > result1.trap_dc

