
import pytest
import random

from models.party import Party, create_test_party
from models.character import Character, CharacterRole


@pytest.fixture
def test_party():
    return create_test_party(1, "Test Guild")


def test_party_initialization(test_party):
    assert len(test_party.members) == 4
    roles = {member.role for member in test_party.members}
    assert roles == {CharacterRole.STRIKER, CharacterRole.BURGLAR, CharacterRole.SUPPORT, CharacterRole.CONTROLLER}


def test_get_member_by_role(test_party):
    striker = test_party.get_member_by_role(CharacterRole.STRIKER)
    assert striker is not None
    assert striker.role == CharacterRole.STRIKER


def test_alive_unconscious_dead_members(test_party):
    assert len(test_party.alive_members()) == 4

    # Knock one unconscious
    member = test_party.members[0]
    member.current_hp = 0
    member.is_conscious = False

    assert len(test_party.alive_members()) == 3
    assert len(test_party.unconscious_members()) == 1

    # Kill another
    test_party.members[1].is_alive = False
    assert len(test_party.dead_members()) == 1


def test_total_disabled_spells_and_missing_hp(test_party):
    # Disable spells on support and controller
    test_party.members[2].disabled_spells.append("heal")
    test_party.members[3].disabled_spells.append("fireball")

    # Injure striker and burglar
    test_party.members[0].current_hp -= 3
    test_party.members[1].current_hp -= 2

    assert test_party.total_disabled_spells() == 2
    assert test_party.total_missing_hp() == 5


def test_total_times_downed(test_party):
    test_party.members[0].times_downed = 1
    test_party.members[1].times_downed = 2
    assert test_party.total_times_downed() == 3


def test_calculate_morale(test_party):
    # Simulate some expedition damage
    test_party.members[0].current_hp -= 5  # missing HP
    test_party.members[1].disabled_spells.append("trap sense")
    test_party.members[2].is_conscious = False  # unconscious
    test_party.members[3].times_downed = 1

    morale = test_party.calculate_morale()
    assert isinstance(morale, int)
    assert morale <= 100


def test_party_wipe_detection(test_party):
    for member in test_party.members:
        member.is_conscious = False

    assert test_party.is_party_wiped() is True


def test_expedition_progress_tracking(test_party):
    test_party.add_gold(50)
    test_party.complete_room()
    test_party.complete_floor()
    test_party.defeat_monsters(3)

    assert test_party.gold_found == 50
    assert test_party.rooms_cleared == 1
    assert test_party.floors_cleared == 1
    assert test_party.monsters_defeated == 3


def test_retreat_and_completion_flags(test_party):
    test_party.retreat_from_expedition()
    assert test_party.retreated is True
    assert test_party.is_active is False

    test_party.complete_expedition()
    assert test_party.retreated is True


def test_reset_for_new_expedition(test_party):
    test_party.add_gold(100)
    test_party.complete_room()
    test_party.members[0].current_hp -= 5
    test_party.members[0].is_conscious = False

    test_party.reset_for_new_expedition()
    assert test_party.gold_found == 0
    assert test_party.rooms_cleared == 0
    assert test_party.members[0].is_conscious is True


def test_expedition_summary(test_party):
    test_party.add_gold(42)
    test_party.complete_floor()
    test_party.complete_room()
    test_party.members[0].is_conscious = False

    summary = test_party.get_expedition_summary()
    assert summary['guild_name'] == "Test Guild"
    assert summary['gold_found'] == 42
    assert summary['status'] in {'retreated', 'wiped', 'active'}
    assert summary['survivors'] <= 4

