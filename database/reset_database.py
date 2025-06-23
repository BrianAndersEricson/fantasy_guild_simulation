"""
Reset Database Script for Fantasy Guild Manager
Clears all data and repopulates with fresh test guilds
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager


def reset_database(db_path: str = "fantasy_guild_test.db", keep_schema: bool = True):
    """
    Reset the database to a clean state with fresh test data.
    
    Args:
        db_path: Path to the database file
        keep_schema: If True, keep tables and just clear data. If False, drop and recreate.
    """
    print("=== RESETTING DATABASE ===")
    print(f"Database: {db_path}")
    
    db = DatabaseManager(db_path)
    
    if keep_schema:
        print("\nClearing existing data...")
        # Clear data in correct order due to foreign keys
        db.cursor.execute("DELETE FROM event_log")
        db.cursor.execute("DELETE FROM expedition_results")
        db.cursor.execute("DELETE FROM expeditions")
        db.cursor.execute("DELETE FROM characters")
        db.cursor.execute("DELETE FROM guilds")
        db.conn.commit()
        print("✓ All data cleared")
    else:
        print("\nDropping all tables...")
        # Drop all tables
        db.cursor.execute("DROP TABLE IF EXISTS event_log")
        db.cursor.execute("DROP TABLE IF EXISTS expedition_results")
        db.cursor.execute("DROP TABLE IF EXISTS expeditions")
        db.cursor.execute("DROP TABLE IF EXISTS characters")
        db.cursor.execute("DROP TABLE IF EXISTS guilds")
        db.conn.commit()
        print("✓ All tables dropped")
        
        # Recreate tables
        print("\nRecreating tables...")
        db._create_tables()
        print("✓ Tables recreated")
    
    # Add fresh test data
    print("\nAdding test guilds...")
    
    test_guilds = [
        {
            "name": "Brave Companions",
            "motto": "Fortune favors the bold!",
            "characters": [
                {"name": "Aldric", "role": "striker", "might": 15, "grit": 12, "wit": 8, "luck": 10, "hp": 22},
                {"name": "Lyra", "role": "burglar", "might": 9, "grit": 10, "wit": 11, "luck": 15, "hp": 18},
                {"name": "Elara", "role": "support", "might": 8, "grit": 11, "wit": 15, "luck": 12, "hp": 17},
                {"name": "Magnus", "role": "controller", "might": 9, "grit": 10, "wit": 14, "luck": 13, "hp": 16}
            ]
        },
        {
            "name": "Iron Wolves",
            "motto": "Strength in unity",
            "characters": [
                {"name": "Grunk", "role": "striker", "might": 16, "grit": 13, "wit": 7, "luck": 9, "hp": 23},
                {"name": "Shadow", "role": "burglar", "might": 10, "grit": 9, "wit": 10, "luck": 16, "hp": 17},
                {"name": "Mystic", "role": "support", "might": 7, "grit": 10, "wit": 16, "luck": 11, "hp": 16},
                {"name": "Void", "role": "controller", "might": 8, "grit": 11, "wit": 15, "luck": 12, "hp": 17}
            ]
        },
        {
            "name": "Mystic Order",
            "motto": "Knowledge is power",
            "characters": [
                {"name": "Kael", "role": "striker", "might": 14, "grit": 11, "wit": 9, "luck": 11, "hp": 21},
                {"name": "Whisper", "role": "burglar", "might": 8, "grit": 10, "wit": 12, "luck": 17, "hp": 18},
                {"name": "Aurora", "role": "support", "might": 9, "grit": 9, "wit": 17, "luck": 10, "hp": 15},
                {"name": "Nebula", "role": "controller", "might": 10, "grit": 10, "wit": 16, "luck": 11, "hp": 16}
            ]
        }
    ]
    
    # Create guilds and characters
    for guild_data in test_guilds:
        # Create guild
        guild_id = db.create_guild(guild_data["name"], guild_data["motto"])
        print(f"\n✓ Created guild: {guild_data['name']} (ID: {guild_id})")
        
        # Create characters
        for char_data in guild_data["characters"]:
            char_id = db.create_character(
                guild_id=guild_id,
                name=char_data["name"],
                role=char_data["role"],
                might=char_data["might"],
                grit=char_data["grit"],
                wit=char_data["wit"],
                luck=char_data["luck"],
                max_hp=char_data["hp"]
            )
            print(f"  - {char_data['name']} ({char_data['role']})")
    
    # Show summary
    print("\n=== RESET COMPLETE ===")
    print(f"✓ {len(test_guilds)} guilds created")
    print(f"✓ {len(test_guilds) * 4} characters created")
    print(f"✓ All characters at full health")
    print(f"✓ All treasuries at 0 gold")
    print("\nDatabase is ready for testing!")
    
    db.close()


def quick_stats(db_path: str = "fantasy_guild_test.db"):
    """Show quick statistics about the current database state"""
    db = DatabaseManager(db_path)
    
    print("\n=== DATABASE STATISTICS ===")
    
    # Guild stats
    guilds = db.get_active_guilds()
    print(f"\nActive Guilds: {len(guilds)}")
    for guild in guilds:
        print(f"  - {guild['name']}: {guild['treasury']} gold, "
              f"{guild['total_expeditions']} expeditions")
        
        # Character stats for this guild
        chars = db.get_guild_characters(guild['id'])
        alive = sum(1 for c in chars if c['is_alive'])
        print(f"    Characters: {alive}/{len(chars)} alive")
    
    # Expedition stats
    expeditions = db.get_recent_expeditions(5)
    print(f"\nRecent Expeditions: {len(expeditions)}")
    for exp in expeditions:
        print(f"  - Expedition #{exp['expedition_number']}: "
              f"{exp['participating_guilds']} guilds, "
              f"status: {exp['status']}")
    
    db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Reset Fantasy Guild database")
    parser.add_argument("--stats", action="store_true", 
                       help="Show database statistics instead of resetting")
    parser.add_argument("--drop-tables", action="store_true",
                       help="Drop and recreate tables (full reset)")
    parser.add_argument("--db", default="fantasy_guild_test.db",
                       help="Database file path")
    
    args = parser.parse_args()
    
    if args.stats:
        quick_stats(args.db)
    else:
        reset_database(args.db, keep_schema=not args.drop_tables)
