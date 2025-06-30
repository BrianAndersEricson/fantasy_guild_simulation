import pytest
from simulation.dungeon_generator import DungeonGenerator, RoomType, Room

# === HELPERS ===

def check_room_validity(room: Room, expected_floor: int):
    assert room.floor_number == expected_floor
    assert room.room_type in RoomType
    assert isinstance(room.room_number, int)
    assert room.difficulty_level == expected_floor

    if room.room_type in [RoomType.COMBAT, RoomType.BOTH, RoomType.BOSS]:
        assert room.enemy_count >= expected_floor
    else:
        assert room.enemy_count == 0

    if room.room_type in [RoomType.TRAP, RoomType.BOTH]:
        assert room.trap_dc == 10 + expected_floor
    else:
        assert room.trap_dc == 0


# === UNIT TESTS ===

def test_generate_floor_structure():
    gen = DungeonGenerator(expedition_seed=123)
    floor = gen.generate_floor(1)

    assert len(floor) >= 6  # 5 + 1d4 rooms
    assert isinstance(floor[-1], Room)
    assert floor[-1].is_final_room
    assert floor[-1].is_boss_room
    assert floor[-1].room_type == RoomType.BOSS

def test_generate_room_probabilities_stable():
    gen1 = DungeonGenerator(expedition_seed=123)
    gen2 = DungeonGenerator(expedition_seed=123)

    floor1 = gen1.generate_floor(2)
    floor2 = gen2.generate_floor(2)

    for r1, r2 in zip(floor1, floor2):
        assert r1.room_type == r2.room_type
        assert r1.enemy_count == r2.enemy_count
        assert r1.trap_dc == r2.trap_dc

def test_room_type_distribution_preview():
    gen = DungeonGenerator(expedition_seed=42)
    preview = gen.generate_expedition_preview(max_floors=3)

    assert isinstance(preview, dict)
    assert set(preview.keys()) == {1, 2, 3}

    for floor_num, rooms in preview.items():
        assert isinstance(rooms, list)
        for room in rooms:
            check_room_validity(room, floor_num)

def test_get_floor_summary_output_shape():
    gen = DungeonGenerator(expedition_seed=99)
    summary = gen.get_floor_summary(1)

    assert "floor_number" in summary
    assert "total_rooms" in summary
    assert "room_types" in summary
    assert "total_enemies" in summary
    assert "boss_rooms" in summary
    assert "difficulty" in summary

    assert summary["floor_number"] == 1
    assert isinstance(summary["room_types"], dict)
    assert summary["total_rooms"] >= 6
    assert summary["boss_rooms"] >= 1

def test_dungeon_generator_seed_consistency():
    g1 = DungeonGenerator(expedition_seed=777)
    g2 = DungeonGenerator(expedition_seed=777)

    assert g1.generate_floor(1) != []  # floors aren't empty
    assert g1.generate_floor(1)[-1].room_type == RoomType.BOSS

    summary1 = g1.get_floor_summary(2)
    summary2 = g2.get_floor_summary(2)
    assert summary1 == summary2

def test_room_str_output_contains_keywords():
    room = Room(
        floor_number=1,
        room_number=3,
        room_type=RoomType.BOTH,
        difficulty_level=1,
        enemy_count=2,
        trap_dc=11,
        is_boss_room=True,
        is_final_room=True
    )
    s = str(room)
    assert "Room 3" in s
    assert "Both" in s
    assert "BOSS" in s
    assert "FINAL" in s

