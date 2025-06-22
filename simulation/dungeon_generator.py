"""
Dungeon Generator for Fantasy Guild Manager simulation.

This module creates procedurally generated dungeon floors using seeds
to ensure all parties in the same expedition face identical challenges.
The generator focuses purely on room layout and types - actual enemy
and trap details are handled by other resolvers.
"""

import random
import sys
import os
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any

# Add the project root to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class RoomType(Enum):
    """Types of rooms that can appear in the dungeon"""
    COMBAT = "combat"           # Monsters only
    TRAP = "trap"              # Trap only  
    BOTH = "both"              # Trap + monsters
    BOSS = "boss"              # Boss encounter
    HEALING_FOUNTAIN = "healing_fountain"  # Rare healing room


@dataclass
class Room:
    """
    Represents a single room in the dungeon.
    
    The Room contains basic parameters but not the actual game objects
    (enemies, traps, etc.) - those are created by the specific resolvers
    when the room is encountered.
    """
    
    # === Room Identity ===
    floor_number: int
    room_number: int
    room_type: RoomType
    
    # === Room Parameters ===
    difficulty_level: int       # Based on floor number
    enemy_count: int = 0        # Number of enemies (if combat room)
    trap_dc: int = 0           # Trap difficulty (if trap room)
    
    # === Special Properties ===
    is_boss_room: bool = False
    is_final_room: bool = False
    
    def __str__(self):
        """String representation for debugging"""
        special = []
        if self.is_boss_room:
            special.append("BOSS")
        if self.is_final_room:
            special.append("FINAL")
        
        special_str = f" [{', '.join(special)}]" if special else ""
        
        return f"Room {self.room_number}: {self.room_type.value.title()}{special_str}"


class DungeonGenerator:
    """
    Generates procedural dungeon floors using deterministic seeds.
    
    All parties in the same expedition use the same seed, ensuring
    they face identical challenges while allowing for different outcomes
    based on their performance and dice rolls.
    """
    
    def __init__(self, expedition_seed: int):
        """
        Initialize generator with expedition seed.
        
        Args:
            expedition_seed: Seed that determines dungeon layout for all parties
        """
        self.expedition_seed = expedition_seed
        self.rng = random.Random(expedition_seed)
        
        # Room generation probabilities
        self.COMBAT_CHANCE = 40         # 40% chance
        self.TRAP_CHANCE = 30           # 30% chance (41-70)
        self.BOTH_CHANCE = 24           # 24% chance (71-94)
        self.BOSS_CHANCE = 5            # 5% chance (95-99)
        self.HEALING_FOUNTAIN_CHANCE = 1 # 1% chance (100)
        
        print(f"Dungeon generator initialized with seed: {expedition_seed}")
    
    def generate_floor(self, floor_number: int) -> List[Room]:
        """
        Generate a complete floor with 5+1d4 rooms.
        
        The final room is always a boss. Other rooms are determined by
        probability rolls, with a small chance for additional bosses.
        
        Args:
            floor_number: Which floor to generate (affects difficulty)
            
        Returns:
            List of Room objects representing the floor layout
        """
        # Create a floor-specific RNG state to ensure consistency
        floor_seed = self.expedition_seed + floor_number * 1000
        floor_rng = random.Random(floor_seed)
        
        # Determine number of rooms for this floor
        room_count = 5 + floor_rng.randint(1, 4)
        rooms = []
        
        # Generate regular rooms (all except the last one)
        for room_num in range(1, room_count):
            room = self._generate_room(floor_rng, floor_number, room_num)
            rooms.append(room)
        
        # Final room is always a boss
        final_room = Room(
            floor_number=floor_number,
            room_number=room_count,
            room_type=RoomType.BOSS,
            difficulty_level=floor_number,
            is_boss_room=True,
            is_final_room=True
        )
        self._setup_room_parameters(final_room, floor_rng)
        rooms.append(final_room)
        
        return rooms
    
    def _generate_room(self, floor_rng: random.Random, floor_number: int, room_number: int) -> Room:
        """
        Generate a single room based on probability rolls.
        
        Args:
            floor_rng: Random number generator for this floor
            floor_number: Current floor number
            room_number: Position of this room on the floor
            
        Returns:
            Generated Room object
        """
        # Roll for room type
        roll = floor_rng.randint(1, 100)
        
        if roll <= self.COMBAT_CHANCE:
            room_type = RoomType.COMBAT
        elif roll <= self.COMBAT_CHANCE + self.TRAP_CHANCE:
            room_type = RoomType.TRAP
        elif roll <= self.COMBAT_CHANCE + self.TRAP_CHANCE + self.BOTH_CHANCE:
            room_type = RoomType.BOTH
        elif roll <= self.COMBAT_CHANCE + self.TRAP_CHANCE + self.BOTH_CHANCE + self.BOSS_CHANCE:
            room_type = RoomType.BOSS
        else:  # The remaining 1%
            room_type = RoomType.HEALING_FOUNTAIN
        
        # Create the room
        room = Room(
            floor_number=floor_number,
            room_number=room_number,
            room_type=room_type,
            difficulty_level=floor_number,
            is_boss_room=(room_type == RoomType.BOSS),
            is_final_room=False
        )
        
        # Set up room-specific parameters
        self._setup_room_parameters(room, floor_rng)
        
        return room
    
    def _setup_room_parameters(self, room: Room, floor_rng: random.Random):
        """
        Set up type-specific parameters for a room.
        
        Args:
            room: Room to configure
            floor_rng: Random number generator for this floor
        """
        difficulty = room.difficulty_level
        
        # Set enemy count for combat rooms
        if room.room_type in [RoomType.COMBAT, RoomType.BOTH, RoomType.BOSS]:
            if room.room_type == RoomType.BOSS:
                # Bosses have more enemies
                room.enemy_count = floor_rng.randint(1, 4) + difficulty + 1
            else:
                # Regular combat
                room.enemy_count = floor_rng.randint(1, 4) + difficulty
        
        # Set trap difficulty for trap rooms
        if room.room_type in [RoomType.TRAP, RoomType.BOTH]:
            room.trap_dc = 10 + difficulty
    
    def generate_expedition_preview(self, max_floors: int = 5) -> Dict[int, List[Room]]:
        """
        Generate a preview of multiple floors for expedition planning.
        
        This can be used to show viewers what challenges await, or for
        internal simulation planning.
        
        Args:
            max_floors: Maximum number of floors to generate
            
        Returns:
            Dictionary mapping floor numbers to room lists
        """
        floors = {}
        for floor_num in range(1, max_floors + 1):
            floors[floor_num] = self.generate_floor(floor_num)
        return floors
    
    def get_floor_summary(self, floor_number: int) -> Dict[str, Any]:
        """
        Get a summary of a floor's contents.
        
        Args:
            floor_number: Floor to summarize
            
        Returns:
            Dictionary with floor statistics
        """
        rooms = self.generate_floor(floor_number)
        
        room_counts = {}
        total_enemies = 0
        boss_count = 0
        
        for room in rooms:
            room_type = room.room_type.value
            room_counts[room_type] = room_counts.get(room_type, 0) + 1
            total_enemies += room.enemy_count
            if room.is_boss_room:
                boss_count += 1
        
        return {
            'floor_number': floor_number,
            'total_rooms': len(rooms),
            'room_types': room_counts,
            'total_enemies': total_enemies,
            'boss_rooms': boss_count,
            'difficulty': floor_number
        }


# === Test the generator ===
if __name__ == "__main__":
    print("Testing Dungeon Generator...")
    print("=" * 60)
    
    # Create generator with test seed
    generator = DungeonGenerator(expedition_seed=12345)
    
    # Test 1: Generate a single floor
    print("1. Generating Floor 1...")
    floor1 = generator.generate_floor(1)
    for room in floor1:
        print(f"   {room}")
        if room.room_type in [RoomType.COMBAT, RoomType.BOTH, RoomType.BOSS]:
            print(f"      Enemies: {room.enemy_count}")
        if room.room_type in [RoomType.TRAP, RoomType.BOTH]:
            print(f"      Trap DC: {room.trap_dc}")
    
    # Test 2: Generate multiple floors
    print(f"\n2. Generating floors 1-3...")
    for floor_num in range(1, 4):
        summary = generator.get_floor_summary(floor_num)
        print(f"\n   Floor {floor_num} Summary:")
        print(f"   - Rooms: {summary['total_rooms']}")
        print(f"   - Types: {summary['room_types']}")
        print(f"   - Total Enemies: {summary['total_enemies']}")
        print(f"   - Bosses: {summary['boss_rooms']}")
    
    # Test 3: Test deterministic generation
    print(f"\n3. Testing deterministic generation...")
    floor1_again = generator.generate_floor(1)
    
    matches = all(
        r1.room_type == r2.room_type and r1.enemy_count == r2.enemy_count
        for r1, r2 in zip(floor1, floor1_again)
    )
    
    print(f"   Floor 1 generated identically twice: {matches}")
    
    # Test 4: Different seed produces different results
    print(f"\n4. Testing different seed...")
    generator2 = DungeonGenerator(expedition_seed=54321)
    floor1_different = generator2.generate_floor(1)
    
    different = any(
        r1.room_type != r2.room_type or r1.enemy_count != r2.enemy_count
        for r1, r2 in zip(floor1, floor1_different)
    )
    
    print(f"   Different seed produces different floor: {different}")
    
    # Test 5: Room type distribution over many floors
    print(f"\n5. Testing room type distribution (10 floors)...")
    type_counts = {}
    total_rooms = 0
    
    for floor_num in range(1, 11):
        rooms = generator.generate_floor(floor_num)
        total_rooms += len(rooms)
        for room in rooms:
            room_type = room.room_type.value
            type_counts[room_type] = type_counts.get(room_type, 0) + 1
    
    print(f"   Total rooms across 10 floors: {total_rooms}")
    for room_type, count in type_counts.items():
        percentage = (count / total_rooms) * 100
        print(f"   {room_type}: {count} ({percentage:.1f}%)")
    
    print(f"\n✓ Dungeon generator is working! Ready for integration.")
