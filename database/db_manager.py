"""
Database models for Fantasy Guild Manager

Uses SQLite for persistence of guilds, characters, expeditions, and events.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any
import json


class DatabaseManager:
    """
    Manages all database operations for the Fantasy Guild Manager.
    
    Uses SQLite for simplicity and portability.
    """
    
    def __init__(self, db_path: str = "fantasy_guild.db"):
        """
        Initialize database connection and create tables if needed.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """Establish database connection"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self.cursor = self.conn.cursor()
        
        # Enable foreign keys
        self.cursor.execute("PRAGMA foreign_keys = ON")
    
    def _create_tables(self):
        """Create all necessary tables if they don't exist"""
        
        # Guilds table - persists across seasons
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS guilds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                motto TEXT,
                treasury INTEGER DEFAULT 0,
                total_expeditions INTEGER DEFAULT 0,
                total_floors_cleared INTEGER DEFAULT 0,
                total_gold_earned INTEGER DEFAULT 0,
                established_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        
        # Characters table - guild members
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL REFERENCES guilds(id),
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                
                -- Base stats
                might INTEGER NOT NULL,
                grit INTEGER NOT NULL,
                wit INTEGER NOT NULL,
                luck INTEGER NOT NULL,
                
                -- Current status
                max_hp INTEGER NOT NULL,
                current_hp INTEGER NOT NULL,
                is_alive BOOLEAN DEFAULT 1,
                is_available BOOLEAN DEFAULT 1,
                times_downed INTEGER DEFAULT 0,
                death_date TIMESTAMP,
                
                -- Tracking
                total_damage_dealt INTEGER DEFAULT 0,
                total_damage_taken INTEGER DEFAULT 0,
                total_rooms_cleared INTEGER DEFAULT 0,
                
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, name)
            )
        """)
        
        # Expeditions table - records of each hourly run
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expeditions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expedition_number INTEGER NOT NULL,
                seed INTEGER NOT NULL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                participating_guilds INTEGER DEFAULT 0,
                total_floors_generated INTEGER DEFAULT 0,
                status TEXT DEFAULT 'scheduled'
            )
        """)
        
        # Expedition results - how each guild performed
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expedition_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expedition_id INTEGER NOT NULL REFERENCES expeditions(id),
                guild_id INTEGER NOT NULL REFERENCES guilds(id),
                floors_cleared INTEGER DEFAULT 0,
                rooms_cleared INTEGER DEFAULT 0,
                gold_found INTEGER DEFAULT 0,
                monsters_defeated INTEGER DEFAULT 0,
                party_size INTEGER DEFAULT 4,
                survivors INTEGER DEFAULT 4,
                retreated BOOLEAN DEFAULT 0,
                wiped BOOLEAN DEFAULT 0,
                final_floor INTEGER DEFAULT 0,
                final_room INTEGER DEFAULT 0,
                UNIQUE(expedition_id, guild_id)
            )
        """)
        
        # Event log - stores all events for replay
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expedition_id INTEGER NOT NULL REFERENCES expeditions(id),
                guild_id INTEGER NOT NULL,
                guild_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL,
                priority TEXT DEFAULT 'normal',
                details TEXT,  -- JSON string
                tick_number INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for common queries
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_expedition 
            ON event_log(expedition_id, tick_number)
        """)
        
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_guild 
            ON expedition_results(guild_id)
        """)
        
        self.conn.commit()
    
    # === Guild Operations ===
    
    def create_guild(self, name: str, motto: str = "") -> int:
        """
        Create a new guild.
        
        Returns:
            Guild ID of the created guild
        """
        try:
            self.cursor.execute("""
                INSERT INTO guilds (name, motto) VALUES (?, ?)
            """, (name, motto))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(f"Guild '{name}' already exists")
    
    def get_guild(self, guild_id: int) -> Optional[Dict]:
        """Get guild by ID"""
        self.cursor.execute("SELECT * FROM guilds WHERE id = ?", (guild_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def get_guild_by_name(self, name: str) -> Optional[Dict]:
        """Get guild by name"""
        self.cursor.execute("SELECT * FROM guilds WHERE name = ?", (name,))
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def get_active_guilds(self) -> List[Dict]:
        """Get all active guilds"""
        self.cursor.execute("SELECT * FROM guilds WHERE is_active = 1")
        return [dict(row) for row in self.cursor.fetchall()]
    
    def update_guild_stats(self, guild_id: int, gold_earned: int, floors_cleared: int):
        """Update guild statistics after expedition"""
        self.cursor.execute("""
            UPDATE guilds 
            SET treasury = treasury + ?,
                total_gold_earned = total_gold_earned + ?,
                total_floors_cleared = total_floors_cleared + ?,
                total_expeditions = total_expeditions + 1
            WHERE id = ?
        """, (gold_earned, gold_earned, floors_cleared, guild_id))
        self.conn.commit()
    
    # === Character Operations ===
    
    def create_character(self, guild_id: int, name: str, role: str,
                        might: int, grit: int, wit: int, luck: int,
                        max_hp: int) -> int:
        """Create a new character"""
        try:
            self.cursor.execute("""
                INSERT INTO characters 
                (guild_id, name, role, might, grit, wit, luck, max_hp, current_hp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (guild_id, name, role, might, grit, wit, luck, max_hp, max_hp))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(f"Character '{name}' already exists in this guild")
    
    def get_guild_characters(self, guild_id: int, available_only: bool = False) -> List[Dict]:
        """Get all characters for a guild"""
        query = "SELECT * FROM characters WHERE guild_id = ?"
        params = [guild_id]
        
        if available_only:
            query += " AND is_available = 1 AND is_alive = 1"
            
        self.cursor.execute(query, params)
        return [dict(row) for row in self.cursor.fetchall()]
    
    def update_character_status(self, character_id: int, current_hp: int,
                               is_alive: bool, times_downed: int):
        """Update character status after expedition"""
        self.cursor.execute("""
            UPDATE characters
            SET current_hp = ?, is_alive = ?, times_downed = ?
            WHERE id = ?
        """, (current_hp, is_alive, times_downed, character_id))
        
        # If character died, record death date
        if not is_alive:
            self.cursor.execute("""
                UPDATE characters SET death_date = CURRENT_TIMESTAMP
                WHERE id = ? AND death_date IS NULL
            """, (character_id,))
        
        self.conn.commit()
    
    # === Expedition Operations ===
    
    def create_expedition(self, expedition_number: int, seed: int) -> int:
        """Create a new expedition record"""
        self.cursor.execute("""
            INSERT INTO expeditions 
            (expedition_number, seed, start_time, status)
            VALUES (?, ?, CURRENT_TIMESTAMP, 'running')
        """, (expedition_number, seed))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def complete_expedition(self, expedition_id: int, participating_guilds: int,
                           total_floors: int):
        """Mark expedition as complete"""
        self.cursor.execute("""
            UPDATE expeditions
            SET end_time = CURRENT_TIMESTAMP,
                status = 'completed',
                participating_guilds = ?,
                total_floors_generated = ?
            WHERE id = ?
        """, (participating_guilds, total_floors, expedition_id))
        self.conn.commit()
    
    def save_expedition_result(self, expedition_id: int, guild_id: int,
                              floors_cleared: int, rooms_cleared: int,
                              gold_found: int, monsters_defeated: int,
                              survivors: int, retreated: bool, wiped: bool):
        """Save how a guild performed in an expedition"""
        self.cursor.execute("""
            INSERT INTO expedition_results
            (expedition_id, guild_id, floors_cleared, rooms_cleared,
             gold_found, monsters_defeated, survivors, retreated, wiped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (expedition_id, guild_id, floors_cleared, rooms_cleared,
              gold_found, monsters_defeated, survivors, retreated, wiped))
        self.conn.commit()
    
    def get_expedition_results(self, expedition_id: int) -> List[Dict]:
        """Get all results for a specific expedition"""
        self.cursor.execute("""
            SELECT er.*, g.name as guild_name
            FROM expedition_results er
            JOIN guilds g ON er.guild_id = g.id
            WHERE er.expedition_id = ?
            ORDER BY er.gold_found DESC
        """, (expedition_id,))
        return [dict(row) for row in self.cursor.fetchall()]
    
    # === Event Log Operations ===
    
    def save_event(self, expedition_id: int, guild_id: int, guild_name: str,
                   event_type: str, description: str, priority: str = "normal",
                   details: Dict = None, tick_number: int = 0):
        """Save an event to the log for replay"""
        details_json = json.dumps(details) if details else None
        
        self.cursor.execute("""
            INSERT INTO event_log
            (expedition_id, guild_id, guild_name, event_type, description,
             priority, details, tick_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (expedition_id, guild_id, guild_name, event_type, description,
              priority, details_json, tick_number))
        # Don't commit after every event for performance
    
    def commit_events(self):
        """Commit all pending events"""
        self.conn.commit()
    
    def get_expedition_events(self, expedition_id: int, guild_id: Optional[int] = None) -> List[Dict]:
        """
        Get all events for an expedition, optionally filtered by guild.
        
        Returns events in tick order for proper replay.
        """
        query = """
            SELECT * FROM event_log 
            WHERE expedition_id = ?
        """
        params = [expedition_id]
        
        if guild_id:
            query += " AND guild_id = ?"
            params.append(guild_id)
            
        query += " ORDER BY tick_number, id"
        
        self.cursor.execute(query, params)
        
        events = []
        for row in self.cursor.fetchall():
            event = dict(row)
            # Parse JSON details
            if event['details']:
                event['details'] = json.loads(event['details'])
            events.append(event)
            
        return events
    
    # === Statistics and Leaderboards ===
    
    def get_guild_leaderboard(self, metric: str = "total_gold_earned") -> List[Dict]:
        """Get guild rankings by various metrics"""
        valid_metrics = ["total_gold_earned", "total_floors_cleared", 
                        "total_expeditions", "treasury"]
        
        if metric not in valid_metrics:
            metric = "total_gold_earned"
            
        self.cursor.execute(f"""
            SELECT * FROM guilds 
            WHERE is_active = 1
            ORDER BY {metric} DESC
            LIMIT 20
        """)
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_recent_expeditions(self, limit: int = 10) -> List[Dict]:
        """Get most recent expeditions"""
        self.cursor.execute("""
            SELECT * FROM expeditions
            WHERE status = 'completed'
            ORDER BY start_time DESC
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


# Test the database
if __name__ == "__main__":
    print("Testing Database Manager")
    print("="*50)
    
    # Create database
    db = DatabaseManager("test_fantasy_guild.db")
    
    # Create test guilds
    print("Creating test guilds...")
    guild1_id = db.create_guild("Brave Companions", "Fortune favors the bold!")
    guild2_id = db.create_guild("Iron Wolves", "Strength in unity")
    print(f"Created guilds: {guild1_id}, {guild2_id}")
    
    # Create test characters
    print("\nCreating test characters...")
    char1_id = db.create_character(
        guild1_id, "Aldric", "striker", 
        might=15, grit=12, wit=8, luck=10, max_hp=22
    )
    char2_id = db.create_character(
        guild1_id, "Lyra", "burglar",
        might=9, grit=10, wit=11, luck=15, max_hp=18
    )
    print(f"Created characters: {char1_id}, {char2_id}")
    
    # Create test expedition
    print("\nCreating test expedition...")
    exp_id = db.create_expedition(1, 12345)
    
    # Save some test events
    print("Saving test events...")
    db.save_event(exp_id, guild1_id, "Brave Companions", "expedition_start",
                  "The Brave Companions begin their expedition!", "high", 
                  {"party_size": 4}, 0)
    db.save_event(exp_id, guild1_id, "Brave Companions", "combat_start",
                  "Combat encounter! 3 enemies appear!", "normal",
                  {"enemy_count": 3}, 5)
    db.commit_events()
    
    # Complete expedition
    db.complete_expedition(exp_id, 2, 3)
    db.save_expedition_result(exp_id, guild1_id, 2, 15, 350, 12, 3, True, False)
    
    # Test retrieval
    print("\nRetrieving expedition results...")
    results = db.get_expedition_results(exp_id)
    for result in results:
        print(f"  {result['guild_name']}: {result['gold_found']} gold")
    
    print("\nRetrieving events...")
    events = db.get_expedition_events(exp_id)
    for event in events[:3]:
        print(f"  Tick {event['tick_number']}: {event['description']}")
    
    print("\nDatabase test complete!")
    db.close()
