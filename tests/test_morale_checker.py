import pytest
import random
from simulation.morale_checker import MoraleChecker, MoraleOutcome, MoraleResult
from models.character import Character, CharacterRole
from models.party import Party


# === TEST UTILITIES ===

def create_precise_party() -> Party:
    """
    Creates a 4-member party where:
    - One member is missing 1 HP
    - One member has 1 disabled spell
    - One member is unconscious
    - One member has been downed twice
    """
    roles = [
        CharacterRole.STRIKER,
        CharacterRole.BURGLAR,
        CharacterRole.SUPPORT,
        CharacterRole.CONTROLLER
    ]

    members = []
    for i, role in enumerate(roles):
        c = Character(name=f"Test{i}", role=role, guild_id=1)
        c.max_hp = 20
        c.current_hp = 20
        c.is_conscious = True
        c.times_downed = 0

        if i == 0:
            c.current_hp = 19  # Missing 1 HP
        elif i == 1:
            if c. known_spells: 
                c.disable_spell(c.known_spells[0])
            else:
                c.disabled_spells = ["TestSpell"]
        elif i == 2:
            c.current_hp = 0
            c.is_conscious = False  # Unconscious
        elif i == 3:
            c.times_downed = 2

        members.append(c)

    return Party(members=members, guild_id=1, guild_name="TestGuild")


class DummyEventEmitter:
    """Captures events for testing purposes"""
    def __init__(self):
        self.events = []

    def __call__(self, guild_id, guild_name, event_type, description, priority, details):
        self.events.append({
            "event_type": event_type,
            "description": description,
            "priority": priority,
            "details": details
        })


# === TEST CASES ===

def test_calculate_morale_dc_components():
    party = create_precise_party()
    checker = MoraleChecker()
    dc = checker.calculate_morale_dc(party)

    # Expected:
    # - 1 missing HP → +1
    # - 1 disabled spell → +5
    # - 1 unconscious member → +20
    # - 2 times downed → +20
    # - Missing HP from unconscious member -> +20
    expected_dc = 1 + 5 + 20 + 20 + 20
    assert dc == expected_dc


def test_successful_morale_check(monkeypatch):
    party = create_precise_party()
    emitter = DummyEventEmitter()
    checker = MoraleChecker(rng=random.Random(1), emit_event_callback=emitter)

    monkeypatch.setattr(checker.rng, "randint", lambda a, b: 100)  # Always pass
    result = checker.check_morale(party)

    assert isinstance(result, MoraleResult)
    assert result.outcome == MoraleOutcome.SUCCESS
    assert result.continues_expedition
    assert not party.retreated
    assert len(emitter.events) == 1
    assert emitter.events[0]['event_type'].name == "MORALE_SUCCESS"


def test_failed_morale_check(monkeypatch):
    party = create_precise_party()
    emitter = DummyEventEmitter()
    checker = MoraleChecker(rng=random.Random(1), emit_event_callback=emitter)

    monkeypatch.setattr(checker.rng, "randint", lambda a, b: 1)  # Always fail
    result = checker.check_morale(party)

    assert isinstance(result, MoraleResult)
    assert result.outcome == MoraleOutcome.FAILURE
    assert not result.continues_expedition
    assert party.retreated
    assert len(emitter.events) == 1
    assert emitter.events[0]['event_type'].name == "MORALE_FAILURE"


def test_floor_completion_uses_disadvantage(monkeypatch):
    party = create_precise_party()
    emitter = DummyEventEmitter()
    checker = MoraleChecker(rng=random.Random(), emit_event_callback=emitter)

    # Simulate a disadvantage roll: [10, 70], should take 10
    rolls = [10, 70]
    call_counter = {'i': 0}
    def fake_randint(a, b):
        val = rolls[call_counter['i']]
        call_counter['i'] += 1
        return val

    monkeypatch.setattr(checker.rng, "randint", fake_randint)
    result = checker.check_morale(party, is_floor_completion=True)

    assert isinstance(result, MoraleResult)
    assert result.rolls_made == [10, 70]
    assert result.roll_result == 10
    assert result.is_floor_completion


def test_event_details_keys():
    party = create_precise_party()
    emitter = DummyEventEmitter()
    checker = MoraleChecker(rng=random.Random(42), emit_event_callback=emitter)

    result = checker.check_morale(party)

    event = emitter.events[0]
    assert "morale_dc" in event["details"]
    assert ("roll" in event["details"] or "rolls" in event["details"])
    assert "success" in event["details"]
    assert isinstance(result, MoraleResult)

