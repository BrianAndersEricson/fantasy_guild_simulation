"""
Expedition Scheduler for Fantasy Guild Manager

Handles automated hourly expedition runs, managing the continuous
simulation that viewers can watch and bet on.

Now integrated with database for persistence!
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from models.character import Character, CharacterRole
from models.party import Party
from models.events import EventType
from simulation.expedition_runner import ExpeditionRunner, ExpeditionResult
from database.db_manager import DatabaseManager  # Import from the actual file


@dataclass
class ScheduledExpedition:
    """Records details of a scheduled expedition"""
    expedition_id: int
    database_id: Optional[int] = None  # ID in database
    scheduled_time: datetime = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    seed: int = 0
    participating_guilds: int = 0
    status: str = "scheduled"  # scheduled, running, completed, failed


class ExpeditionScheduler:
    """
    Manages the automated expedition schedule with database persistence.
    
    Core responsibilities:
    - Run expeditions every hour (or configurable interval)
    - Load guilds and characters from database
    - Save all expedition results and events
    - Track expedition history
    - Handle recovery between expeditions
    """
    
    def __init__(self, 
                 interval_minutes: int = 60,
                 tick_duration: float = 2.0,
                 max_floors: int = 3,
                 db_path: str = "fantasy_guild.db"):
        """
        Initialize the expedition scheduler.
        
        Args:
            interval_minutes: Minutes between expeditions (default 60 for hourly)
            tick_duration: Seconds between event ticks for replay
            max_floors: Maximum dungeon floors per expedition
            db_path: Path to SQLite database
        """
        self.interval_minutes = interval_minutes
        self.tick_duration = tick_duration
        self.max_floors = max_floors
        
        # Database connection
        self.db = DatabaseManager(db_path)
        
        # Create custom event callback that saves to database
        self.current_expedition_db_id = None
        self.event_tick_counter = 0
        
        # Scheduler setup
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
        
        # Expedition tracking
        self.expedition_counter = self._get_last_expedition_number()
        self.current_expedition: Optional[ScheduledExpedition] = None
        self.expedition_history: List[ScheduledExpedition] = []
        
        # State tracking
        self.is_running = False
        self.last_expedition_results: List[ExpeditionResult] = []
    
    def _get_last_expedition_number(self) -> int:
        """Get the last expedition number from database"""
        recent = self.db.get_recent_expeditions(1)
        if recent:
            return recent[0]['expedition_number']
        return 0
    
    def _emit_and_save_event(self, guild_id: int, guild_name: str, event_type: EventType,
                            description: str, priority: str = "normal", details: dict = None):
        """
        Event callback that both prints and saves to database.
        
        This replaces the default event handler when running expeditions.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {description}")
        
        # Save to database if we have an active expedition
        if self.current_expedition_db_id:
            self.db.save_event(
                expedition_id=self.current_expedition_db_id,
                guild_id=guild_id,
                guild_name=guild_name,
                event_type=event_type.value,
                description=description,
                priority=priority,
                details=details,
                tick_number=self.event_tick_counter
            )
            
            # Increment tick counter
            self.event_tick_counter += 1
    
    def _load_guild_party(self, guild_data: Dict) -> Optional[Party]:
        """
        Load a guild's party from the database.
        
        Args:
            guild_data: Guild record from database
            
        Returns:
            Party object ready for expedition, or None if invalid
        """
        # Get available characters
        characters = self.db.get_guild_characters(guild_data['id'], available_only=True)
        
        # Need at least 4 alive and available characters
        if len(characters) < 4:
            print(f"Guild '{guild_data['name']}' doesn't have enough available characters")
            return None
        
        # Create Character objects from database records
        party_members = []
        roles_needed = [CharacterRole.STRIKER, CharacterRole.BURGLAR, 
                       CharacterRole.SUPPORT, CharacterRole.CONTROLLER]
        
        # Try to fill each role
        for role in roles_needed:
            # Find character with this role
            role_char = None
            for char_data in characters:
                if char_data['role'] == role.value and char_data not in party_members:
                    role_char = char_data
                    break
            
            if role_char:
                # Create Character object
                character = Character(
                    name=role_char['name'],
                    role=role,
                    guild_id=guild_data['id'],
                    might=role_char['might'],
                    grit=role_char['grit'],
                    wit=role_char['wit'],
                    luck=role_char['luck']
                )
                # Restore HP and other status
                character.max_hp = role_char['max_hp']
                character.current_hp = role_char['current_hp']
                character.times_downed = role_char['times_downed']
                character.is_alive = role_char['is_alive']
                
                # Track database ID for updates
                character.db_id = role_char['id']
                
                party_members.append(character)
        
        # Verify we have all 4 roles
        if len(party_members) != 4:
            print(f"Guild '{guild_data['name']}' doesn't have all required roles")
            return None
        
        # Create party
        return Party(
            guild_id=guild_data['id'],
            guild_name=guild_data['name'],
            members=party_members
        )
    
    def start(self, run_immediately: bool = False):
        """
        Start the expedition scheduler.
        
        Args:
            run_immediately: If True, run an expedition right away
        """
        if self.is_running:
            print("Scheduler is already running")
            return
        
        # Schedule the recurring job
        self.scheduler.add_job(
            func=self._run_expedition,
            trigger="interval",
            minutes=self.interval_minutes,
            id="expedition_job",
            name="Hourly Expedition",
            next_run_time=datetime.now() if run_immediately else None
        )
        
        self.scheduler.start()
        self.is_running = True
        
        next_run = self.scheduler.get_job("expedition_job").next_run_time
        print(f"Expedition scheduler started. Next expedition at: {next_run}")
        
        # Show active guilds
        try:
            active_guilds = self.db.get_active_guilds()
            print(f"Active guilds: {len(active_guilds)}")
            for guild in active_guilds:
                print(f"  - {guild['name']} (Treasury: {guild['treasury']} gold)")
        except sqlite3.ProgrammingError as e:
            print(f"Warning: Could not list guilds due to database access: {e}")
        
        self._print_schedule()
    
    def stop(self):
        """Stop the expedition scheduler"""
        if not self.is_running:
            print("Scheduler is not running")
            return
            
        self.scheduler.shutdown(wait=True)
        self.is_running = False
        self.db.close()
        print("Expedition scheduler stopped")
    
    def _run_expedition(self):
        """
        Run a scheduled expedition for all active guilds.
        
        This is the main method called by the scheduler.
        """
        # Create a fresh database connection for this thread
        db = DatabaseManager(self.db.db_path)
        
        self.expedition_counter += 1
        self.event_tick_counter = 0  # Reset tick counter
        
        # Generate expedition seed based on current time
        seed = int(datetime.now().timestamp())
        
        # Create expedition record in database
        self.current_expedition_db_id = db.create_expedition(
            self.expedition_counter, seed
        )
        
        # Create expedition tracking record
        self.current_expedition = ScheduledExpedition(
            expedition_id=self.expedition_counter,
            database_id=self.current_expedition_db_id,
            scheduled_time=datetime.now(),
            seed=seed
        )
        
        print(f"\n{'='*60}")
        print(f"EXPEDITION #{self.expedition_counter} STARTING")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Seed: {seed}")
        print(f"{'='*60}\n")
        
        # Load active guilds from database
        active_guilds = self.db.get_active_guilds()
        parties = []
        
        # Process each guild and create parties
        for guild_data in active_guilds:
            party = self._load_guild_party(guild_data)
            if party:
                parties.append(party)
                print(f"  {guild_data['name']} sends forth their party!")
        
        self.current_expedition.participating_guilds = len(parties)
        self.current_expedition.actual_start = datetime.now()
        self.current_expedition.status = "running"
        
        # Emit global expedition announcement
        self._emit_and_save_event(
            guild_id=0,
            guild_name="SYSTEM",
            event_type=EventType.EXPEDITION_START,
            description=f"Expedition #{self.expedition_counter} begins! {len(parties)} guilds delve into the dungeon!",
            priority="critical",
            details={
                'expedition_id': self.expedition_counter,
                'seed': seed,
                'guild_count': len(parties)
            }
        )
        
        # Run the expedition
        if parties:
            runner = ExpeditionRunner(
                seed=seed,
                emit_event_callback=self._emit_and_save_event,
                tick_duration=self.tick_duration,
                max_floors=self.max_floors
            )
            
            try:
                self.last_expedition_results = runner.run_expedition(parties)
                self.current_expedition.status = "completed"
                
                # Commit all events to database
                self.db.commit_events()
                
                # Process and save results
                self._process_expedition_results(self.last_expedition_results, parties)
                
            except Exception as e:
                print(f"ERROR: Expedition failed - {str(e)}")
                self.current_expedition.status = "failed"
                import traceback
                traceback.print_exc()
        
        # Mark expedition complete in database
        self.current_expedition.actual_end = datetime.now()
        total_floors = self.max_floors  # Could calculate actual floors generated
        self.db.complete_expedition(
            self.current_expedition_db_id,
            self.current_expedition.participating_guilds,
            total_floors
        )
        
        # Add to history
        self.expedition_history.append(self.current_expedition)
        
        # Print summary
        self._print_expedition_summary()
        
        # Schedule next expedition
        next_run = self.scheduler.get_job("expedition_job").next_run_time
        if next_run:
            if next_run.tzinfo:
                next_run_local = next_run.astimezone()
            else:
                next_run_local = next_run
            print(f"\nNext expedition scheduled for: {next_run_local.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def _process_expedition_results(self, results: List[ExpeditionResult], parties: List[Party]):
        """
        Process expedition results - save to database and update characters.
        
        Args:
            results: List of expedition results
            parties: List of parties that participated
        """
        print("\n--- Saving Expedition Results ---")
        
        # Create a map of guild_id to party for character updates
        party_map = {party.guild_id: party for party in parties}
        
        for result in sorted(results, key=lambda r: r.gold_found, reverse=True):
            status = "WIPED" if result.wiped else "RETREATED" if result.retreated else "COMPLETED"
            print(f"{result.guild_name}: {status} - "
                  f"Floors: {result.floors_cleared}, "
                  f"Rooms: {result.rooms_cleared}, "
                  f"Gold: {result.gold_found}")
            
            # Save expedition result
            survivors = 0
            party = party_map.get(result.guild_id)
            if party:
                survivors = len(party.alive_members())
            
            self.db.save_expedition_result(
                expedition_id=self.current_expedition_db_id,
                guild_id=result.guild_id,
                floors_cleared=result.floors_cleared,
                rooms_cleared=result.rooms_cleared,
                gold_found=result.gold_found,
                monsters_defeated=result.monsters_defeated,
                survivors=survivors,
                retreated=result.retreated,
                wiped=result.wiped
            )
            
            # Update guild stats
            self.db.update_guild_stats(
                guild_id=result.guild_id,
                gold_earned=result.gold_found,
                floors_cleared=result.floors_cleared
            )
            
            # Update character states
            if party:
                for character in party.members:
                    if hasattr(character, 'db_id'):
                        self.db.update_character_status(
                            character_id=character.db_id,
                            current_hp=character.current_hp,
                            is_alive=character.is_alive,
                            times_downed=character.times_downed
                        )
    
    def _print_expedition_summary(self):
        """Print summary of the completed expedition"""
        if not self.last_expedition_results:
            return
            
        total_gold = sum(r.gold_found for r in self.last_expedition_results)
        total_floors = sum(r.floors_cleared for r in self.last_expedition_results)
        survivals = sum(1 for r in self.last_expedition_results if not r.wiped)
        
        duration = self.current_expedition.actual_end - self.current_expedition.actual_start
        
        print(f"\n--- Expedition #{self.expedition_counter} Complete ---")
        print(f"Duration: {duration.total_seconds():.1f} seconds")
        print(f"Total Gold Found: {total_gold}")
        print(f"Total Floors Cleared: {total_floors}")
        print(f"Survival Rate: {survivals}/{len(self.last_expedition_results)}")
        
        # Show top performers
        print("\nTop Performers:")
        for i, result in enumerate(sorted(self.last_expedition_results, 
                                        key=lambda r: r.gold_found, reverse=True)[:3]):
            print(f"  {i+1}. {result.guild_name}: {result.gold_found} gold")
    
    def _print_schedule(self):
        """Print the expedition schedule for the next 24 hours"""
        print("\n--- Upcoming Expedition Schedule ---")
        
        # Get the job to check if it uses timezone
        job = self.scheduler.get_job("expedition_job")
        if job and job.next_run_time:
            # Use appropriate timezone handling
            current_time = datetime.now(timezone.utc) if job.next_run_time.tzinfo else datetime.now()
            
            for i in range(min(24, int(24 // (self.interval_minutes / 60)))):
                expedition_time = current_time + timedelta(minutes=self.interval_minutes * i)
                # Convert to local time for display
                if expedition_time.tzinfo:
                    expedition_time = expedition_time.astimezone()
                print(f"Expedition #{self.expedition_counter + i}: "
                      f"{expedition_time.strftime('%Y-%m-%d %H:%M')}")
    
    def _job_executed(self, event):
        """Handle successful job execution"""
        if event.job_id == "expedition_job":
            print(f"Expedition job completed successfully")
    
    def _job_error(self, event):
        """Handle job execution errors"""
        if event.job_id == "expedition_job":
            print(f"ERROR: Expedition job failed: {event.exception}")
    
    def get_next_expedition_time(self) -> Optional[datetime]:
        """Get the time of the next scheduled expedition"""
        if not self.is_running:
            return None
            
        job = self.scheduler.get_job("expedition_job")
        return job.next_run_time if job else None
    
    def get_time_until_next_expedition(self) -> Optional[timedelta]:
        """Get time remaining until next expedition"""
        next_time = self.get_next_expedition_time()
        if next_time:
            # Handle timezone-aware datetime from APScheduler
            now = datetime.now(timezone.utc) if next_time.tzinfo else datetime.now()
            return next_time - now
        return None


# Create a setup script to populate initial data
def setup_test_data(db_path: str = "fantasy_guild.db"):
    """Create initial guilds and characters for testing"""
    print("Setting up test data...")
    db = DatabaseManager(db_path)
    
    # Define test guilds with their characters
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
        try:
            # Create guild
            guild_id = db.create_guild(guild_data["name"], guild_data["motto"])
            print(f"Created guild: {guild_data['name']} (ID: {guild_id})")
            
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
                print(f"  - Created {char_data['name']} ({char_data['role']})")
                
        except ValueError as e:
            print(f"Skipping: {e}")
    
    db.close()
    print("Test data setup complete!")


# Test the scheduler with database
if __name__ == "__main__":
    print("Testing Expedition Scheduler with Database")
    print("="*60)
    
    # First, set up test data if needed
    db_path = "fantasy_guild_test.db"
    
    # Check if we need to create test data
    temp_db = DatabaseManager(db_path)
    if not temp_db.get_active_guilds():
        temp_db.close()
        setup_test_data(db_path)
    else:
        temp_db.close()
        print("Using existing guilds in database")
    
    # Create scheduler with short interval for testing
    scheduler = ExpeditionScheduler(
        interval_minutes=2,  # Every 2 minutes for testing
        tick_duration=2.0,   # 2 second ticks for replay
        db_path=db_path
    )
    
    # Start scheduler with immediate first run
    scheduler.start(run_immediately=True)
    
    try:
        # Let it run for a while
        print("\nScheduler running. Press Ctrl+C to stop...")
        while True:
            time.sleep(30)
            
            # Print time until next expedition
            time_remaining = scheduler.get_time_until_next_expedition()
            if time_remaining:
                minutes = int(time_remaining.total_seconds() // 60)
                seconds = int(time_remaining.total_seconds() % 60)
                print(f"\nNext expedition in: {minutes}m {seconds}s")
                
    except KeyboardInterrupt:
        print("\n\nStopping scheduler...")
        scheduler.stop()
        print("Done!")
