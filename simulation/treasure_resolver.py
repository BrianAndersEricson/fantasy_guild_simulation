"""
Treasure Resolver for Fantasy Guild Manager
Handles treasure finding mechanics for all room types
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


class TreasureOutcome(Enum):
    """Possible outcomes when searching for treasure"""
    CRITICAL_SUCCESS = "critical_success"    # Nat 20 - gold + magic item
    SUCCESS = "success"                      # Beat DC - gold only
    FAILURE = "failure"                      # Failed DC - no treasure


class MagicItemRarity(Enum):
    """Magic item rarity levels"""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"


@dataclass
class MagicItem:
    """Placeholder magic item for MVP"""
    name: str
    rarity: MagicItemRarity
    description: str
    identified: bool = False
    
    def __str__(self):
        status = "identified" if self.identified else "unidentified"
        return f"{self.name} ({self.rarity.value}, {status})"


@dataclass
class TreasureResult:
    """Result of searching for treasure in a room"""
    outcome: TreasureOutcome
    searching_character: Character
    treasure_dc: int
    roll_result: int
    gold_found: int = 0
    magic_item_found: Optional[MagicItem] = None


class TreasureResolver:
    """Handles all treasure-finding mechanics"""
    
    def __init__(self, rng: random.Random = None, emit_event_callback=None):
        """Initialize with unseeded random by default for true randomness"""
        self.rng = rng if rng is not None else random.Random()
        self.emit_event = emit_event_callback or self._default_event_handler
        
        # Placeholder magic item tables
        self.common_items = ["Rusty Sword", "Cracked Shield", "Faded Cloak", "Bent Wand"]
        self.uncommon_items = ["Silver Blade", "Iron Shield", "Mystic Robe", "Crystal Wand"]
        self.rare_items = ["Flaming Sword", "Dragon Shield", "Archmage Robe", "Staff of Power"]
    
    def _default_event_handler(self, guild_id, guild_name, event_type, description, priority="normal", details=None):
        """Default event handler for testing"""
        print(f"[{event_type.value.upper()}] {description}")
    
    def get_treasure_finder(self, party: Party) -> Character:
        """Get burglar if available, otherwise random living member"""
        burglar = party.get_member_by_role(CharacterRole.BURGLAR)
        if burglar and burglar.is_alive:
            return burglar
        
        living_members = party.alive_members()
        if living_members:
            return self.rng.choice(living_members)
        
        raise ValueError("No living party members to search for treasure")
    
    def calculate_gold_amount(self, floor_level: int) -> int:
        """Calculate gold found: Floor Level × 1d20"""
        return floor_level * self.rng.randint(1, 20)
    
    def generate_magic_item(self) -> MagicItem:
        """Generate random magic item with proper rarity distribution"""
        rarity_roll = self.rng.randint(1, 20)
        
        if rarity_roll <= 12:  # 1-12: Common
            rarity = MagicItemRarity.COMMON
            name = self.rng.choice(self.common_items)
        elif rarity_roll <= 18:  # 13-18: Uncommon
            rarity = MagicItemRarity.UNCOMMON
            name = self.rng.choice(self.uncommon_items)
        else:  # 19-20: Rare
            rarity = MagicItemRarity.RARE
            name = self.rng.choice(self.rare_items)
        
        return MagicItem(
            name=name,
            rarity=rarity,
            description=f"A {rarity.value} magical item",
            identified=False
        )
    
    def resolve_treasure(self, party: Party, floor_level: int, is_boss_room: bool = False) -> TreasureResult:
        """Main treasure resolution logic"""
        searcher = self.get_treasure_finder(party)
        
        # Calculate DC and roll
        treasure_dc = 10 + floor_level + (1 if is_boss_room else 0)
        base_roll = self.rng.randint(1, 20)
        luck_bonus = searcher.get_luck_modifier()
        
        # Apply debuff modifiers if present
        debuff_modifier = 0
        if hasattr(searcher, 'debuff_manager') and searcher.debuff_manager:
            debuff_modifier = searcher.debuff_manager.get_stat_modifier('luck', vs_enemies=False)
        
        total_roll = base_roll + luck_bonus + debuff_modifier
        
        # Create result
        result = TreasureResult(
            outcome=TreasureOutcome.SUCCESS,
            searching_character=searcher,
            treasure_dc=treasure_dc,
            roll_result=total_roll
        )
        
        # Determine outcome
        if base_roll == 20:  # Natural 20 = critical success
            result.outcome = TreasureOutcome.CRITICAL_SUCCESS
            result.gold_found = self.calculate_gold_amount(floor_level)
            result.magic_item_found = self.generate_magic_item()
            party.add_gold(result.gold_found)
            
            room_type = "boss chamber" if is_boss_room else "room"
            self.emit_event(
                party.guild_id, party.guild_name, EventType.TREASURE_FOUND,
                f"{searcher.name} finds amazing treasure! {result.gold_found} gold and {result.magic_item_found.name}!",
                "high",
                {'searcher': searcher.name, 'gold': result.gold_found, 'magic_item': result.magic_item_found.name}
            )
            
        elif total_roll >= treasure_dc:  # Success
            result.outcome = TreasureOutcome.SUCCESS
            result.gold_found = self.calculate_gold_amount(floor_level)
            party.add_gold(result.gold_found)
            
            room_type = "boss chamber" if is_boss_room else "room"
            self.emit_event(
                party.guild_id, party.guild_name, EventType.TREASURE_FOUND,
                f"{searcher.name} finds {result.gold_found} gold in the {room_type}",
                "normal",
                {'searcher': searcher.name, 'gold': result.gold_found}
            )
            
        else:  # Failure
            result.outcome = TreasureOutcome.FAILURE
            result.gold_found = 0
            
            room_type = "boss chamber" if is_boss_room else "room"
            self.emit_event(
                party.guild_id, party.guild_name, EventType.TREASURE_FOUND,
                f"{searcher.name} searches the {room_type} but finds nothing",
                "normal",
                {'searcher': searcher.name, 'gold': 0, 'found_treasure': False}
            )
        
        return result


# Test the treasure resolver
if __name__ == "__main__":
    from models.character import Character, CharacterRole
    from models.party import Party
    from simulation.debuff_system import DebuffManager
    
    print("Testing Treasure Resolver")
    print("=" * 40)
    
    # Create test party
    party = Party(
        guild_id=1,
        guild_name="Test Guild",
        members=[
            Character("Aldric", CharacterRole.STRIKER, 1, might=12, grit=10, wit=8, luck=6),
            Character("Lyra", CharacterRole.BURGLAR, 1, might=8, grit=9, wit=9, luck=12),
            Character("Elara", CharacterRole.SUPPORT, 1, might=7, grit=8, wit=12, luck=9),
            Character("Theron", CharacterRole.CONTROLLER, 1, might=7, grit=8, wit=11, luck=10),
        ]
    )
    
    # Add debuff managers
    for member in party.members:
        member.debuff_manager = DebuffManager()
    
    print("Party members:")
    for member in party.members:
        print(f"  {member.name} ({member.role.value}) - Luck: {member.luck} (+{member.get_luck_modifier()})")
    
    def test_event_handler(guild_id, guild_name, event_type, description, priority="normal", details=None):
        print(f"[EVENT] {description}")
    
    print("\nNOTE: Using unseeded random - results vary each run!")
    
    # Test 1: Basic treasure search
    print("\n1. Basic Treasure Search (Floor 2, DC 12):")
    resolver = TreasureResolver(emit_event_callback=test_event_handler)
    result = resolver.resolve_treasure(party, floor_level=2, is_boss_room=False)
    print(f"   Searcher: {result.searching_character.name}")
    print(f"   Roll: {result.roll_result} vs DC {result.treasure_dc}")
    print(f"   Outcome: {result.outcome.value}")
    print(f"   Gold: {result.gold_found}")
    
    # Test 2: Multiple attempts to show randomness
    print("\n2. Multiple Attempts (showing randomness):")
    for i in range(5):
        party.gold_found = 0  # Reset for clean comparison
        resolver = TreasureResolver(emit_event_callback=test_event_handler)
        result = resolver.resolve_treasure(party, floor_level=2, is_boss_room=False)
        print(f"   Attempt {i+1}: Roll {result.roll_result} vs DC {result.treasure_dc} = {result.outcome.value}, Gold: {result.gold_found}")
    
    # Test 3: Boss room vs normal room
    print("\n3. Boss Room vs Normal Room:")
    party.gold_found = 0
    resolver = TreasureResolver(emit_event_callback=test_event_handler)
    
    normal_result = resolver.resolve_treasure(party, floor_level=2, is_boss_room=False)
    print(f"   Normal room (DC 12): {normal_result.outcome.value}")
    
    boss_result = resolver.resolve_treasure(party, floor_level=2, is_boss_room=True)
    print(f"   Boss room (DC 13): {boss_result.outcome.value}")
    
    # Test 4: Force critical success to verify magic item generation
    print("\n4. Testing Critical Success (Forced Natural 20):")
    
    class ForcedCritRNG:
        def __init__(self):
            self.call_count = 0
            self.backup_rng = random.Random()
        
        def randint(self, min_val, max_val):
            self.call_count += 1
            if self.call_count == 1:  # First call is treasure roll
                return 20  # Force natural 20
            else:  # Other calls use true random for variety
                return self.backup_rng.randint(min_val, max_val)
        
        def choice(self, seq):
            return self.backup_rng.choice(seq)
    
    # Test critical success a few times to show magic item variety
    for i in range(3):
        party.gold_found = 0
        for member in party.members:
            member.is_conscious = True
        
        forced_rng = ForcedCritRNG()
        crit_resolver = TreasureResolver(forced_rng, test_event_handler)
        result = crit_resolver.resolve_treasure(party, floor_level=3, is_boss_room=True)
        
        print(f"   Critical #{i+1}: Gold: {result.gold_found}, Item: {result.magic_item_found.name} ({result.magic_item_found.rarity.value})")
    
    # Test 5: No burglar fallback
    print("\n5. No Burglar Available:")
    lyra = party.get_member_by_role(CharacterRole.BURGLAR)
    lyra.is_conscious = False  # Knock out burglar
    
    resolver = TreasureResolver(emit_event_callback=test_event_handler)
    result = resolver.resolve_treasure(party, floor_level=2, is_boss_room=False)
    print(f"   Fallback searcher: {result.searching_character.name} ({result.searching_character.role.value})")
    print(f"   Roll: {result.roll_result} vs DC {result.treasure_dc} = {result.outcome.value}")
    
    print("\n✓ Test complete! Run multiple times to see randomness in action.")
