"""
Expedition Scheduler for Fantasy Guild Manager

Handles automated hourly expedition runs, managing the continuous
simulation that viewers can watch and bet on.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from models.character import Character, CharacterRole
from models.party import Party
from models.events import EventType
from simulation.expedition_runner import ExpeditionRunner, ExpeditionResult


@dataclass
class ScheduledExpedition:
    """Records details of a scheduled expedition"""
    expedition_id: int
    scheduled_time: datetime
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    seed: int = 0
    participating_guilds: int = 0
    status: str = "scheduled"  # scheduled, running, completed, failed


class ExpeditionScheduler:
    """
    Manages the automated expedition schedule.
    
    Core responsibilities:
    - Run expeditions every hour (or configurable interval)
    - Generate unique seeds for each expedition
    - Manage active guilds and their parties
    - Track expedition history
    - Handle recovery between expeditions
    """
    
    def __init__(self, 
                 interval_minutes: int = 60,
                 emit_event_callback: Optional[Callable] = None,
                 tick_duration: float = 2.0,
                 max_floors: int = 3):
        """
        Initialize the expedition scheduler.
        
        Args:
            interval_minutes: Minutes between expeditions (default 60 for hourly)
            emit_event_callback: Function to call for events
            tick_duration: Seconds between event ticks
            max_floors: Maximum dungeon floors per expedition
        """
        self.interval_minutes = interval_minutes
        self.emit_event = emit_event_callback or self._default_event_handler
        self.tick_duration = tick_duration
        self.max_floors = max_floors
        
        # Scheduler setup
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
        
        # Expedition tracking
        self.expedition_counter = 0
        self.current_expedition: Optional[ScheduledExpedition] = None
        self.expedition_history: List[ScheduledExpedition] = []
        
        # Guild management (in real system, would load from database)
        self.active_guilds: Dict[int, Party] = {}
        
        # State tracking
        self.is_running = False
        self.last_expedition_results: List[ExpeditionResult] = []
    
    def _default_event_handler(self, guild_id: int, guild_name: str, event_type: EventType,
                              description: str, priority: str = "normal", details: dict = None):
        """Default event handler for testing"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {description}")
    
    def register_guild(self, party: Party):
        """
        Register a guild to participate in scheduled expeditions.
        
        Args:
            party: The guild's party configuration
        """
        self.active_guilds[party.guild_id] = party
        print(f"Guild '{party.guild_name}' registered for expeditions")
    
    def unregister_guild(self, guild_id: int):
        """Remove a guild from scheduled expeditions"""
        if guild_id in self.active_guilds:
            guild_name = self.active_guilds[guild_id].guild_name
            del self.active_guilds[guild_id]
            print(f"Guild '{guild_name}' unregistered from expeditions")
    
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
        
        # Show schedule for next 24 hours
        self._print_schedule()
    
    def stop(self):
        """Stop the expedition scheduler"""
        if not self.is_running:
            print("Scheduler is not running")
            return
            
        self.scheduler.shutdown(wait=True)
        self.is_running = False
        print("Expedition scheduler stopped")
    
    def _run_expedition(self):
        """
        Run a scheduled expedition for all active guilds.
        
        This is the main method called by the scheduler.
        """
        self.expedition_counter += 1
        
        # Generate expedition seed based on current time
        # This ensures unique dungeons each hour
        seed = int(datetime.now().timestamp())
        
        # Create expedition record
        self.current_expedition = ScheduledExpedition(
            expedition_id=self.expedition_counter,
            scheduled_time=datetime.now(),
            seed=seed,
            participating_guilds=len(self.active_guilds)
        )
        
        print(f"\n{'='*60}")
        print(f"EXPEDITION #{self.expedition_counter} STARTING")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Seed: {seed}")
        print(f"Participating Guilds: {len(self.active_guilds)}")
        print(f"{'='*60}\n")
        
        # Update status
        self.current_expedition.actual_start = datetime.now()
        self.current_expedition.status = "running"
        
        # Emit global expedition announcement
        self.emit_event(
            guild_id=0,
            guild_name="SYSTEM",
            event_type=EventType.EXPEDITION_START,
            description=f"Expedition #{self.expedition_counter} begins! {len(self.active_guilds)} guilds delve into the dungeon!",
            priority="critical",
            details={
                'expedition_id': self.expedition_counter,
                'seed': seed,
                'guild_count': len(self.active_guilds)
            }
        )
        
        # Prepare parties for expedition
        parties = []
        for guild_id, party in self.active_guilds.items():
            # Reset party state for new expedition
            party.reset_for_new_expedition()
            
            # Apply recovery from previous expedition
            self._apply_recovery(party)
            
            parties.append(party)
        
        # Run the expedition
        if parties:
            runner = ExpeditionRunner(
                seed=seed,
                emit_event_callback=self.emit_event,
                tick_duration=self.tick_duration,
                max_floors=self.max_floors
            )
            
            try:
                self.last_expedition_results = runner.run_expedition(parties)
                self.current_expedition.status = "completed"
                
                # Process results
                self._process_expedition_results(self.last_expedition_results)
                
            except Exception as e:
                print(f"ERROR: Expedition failed - {str(e)}")
                self.current_expedition.status = "failed"
                import traceback
                traceback.print_exc()
        
        # Mark expedition complete
        self.current_expedition.actual_end = datetime.now()
        self.expedition_history.append(self.current_expedition)
        
        # Print summary
        self._print_expedition_summary()
        
        # Schedule next expedition
        next_run = self.scheduler.get_job("expedition_job").next_run_time
        if next_run:
            # Convert to local time for display
            if next_run.tzinfo:
                next_run_local = next_run.astimezone()
            else:
                next_run_local = next_run
            print(f"\nNext expedition scheduled for: {next_run_local.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def _apply_recovery(self, party: Party):
        """
        Apply recovery mechanics between expeditions.
        
        This is where we'd handle:
        - Spell recovery rolls
        - Character revival/replacement
        - Healing (already done in reset)
        """
        # For MVP, we'll just clear disabled spells
        # In full version, roll for each spell recovery
        for member in party.members:
            if hasattr(member, 'disabled_spells'):
                member.disabled_spells.clear()
    
    def _process_expedition_results(self, results: List[ExpeditionResult]):
        """
        Process expedition results for rewards, rankings, etc.
        
        In full version this would:
        - Update guild treasuries
        - Award magic items
        - Update leaderboards
        - Trigger viewer payouts
        """
        print("\n--- Expedition Results ---")
        for result in sorted(results, key=lambda r: r.gold_found, reverse=True):
            status = "WIPED" if result.wiped else "RETREATED" if result.retreated else "COMPLETED"
            print(f"{result.guild_name}: {status} - "
                  f"Floors: {result.floors_cleared}, "
                  f"Rooms: {result.rooms_cleared}, "
                  f"Gold: {result.gold_found}")
    
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
    
    def _print_schedule(self):
        """Print the expedition schedule for the next 24 hours"""
        print("\n--- Upcoming Expedition Schedule ---")
        
        # Get the job to check if it uses timezone
        job = self.scheduler.get_job("expedition_job")
        if job and job.next_run_time:
            # Use appropriate timezone handling
            from datetime import timezone
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
            from datetime import timezone
            now = datetime.now(timezone.utc) if next_time.tzinfo else datetime.now()
            return next_time - now
        return None


# Test the scheduler
if __name__ == "__main__":
    print("Testing Expedition Scheduler")
    print("="*60)
    
    # Create some test guilds
    from models.character import Character
    from models.party import Party
    
    # Guild 1: Brave Companions
    party1 = Party(
        guild_id=1,
        guild_name="Brave Companions",
        members=[
            Character("Aldric", CharacterRole.STRIKER, 1, might=15, grit=12, wit=8, luck=10),
            Character("Lyra", CharacterRole.BURGLAR, 1, might=9, grit=10, wit=11, luck=15),
            Character("Elara", CharacterRole.SUPPORT, 1, might=8, grit=11, wit=15, luck=12),
            Character("Magnus", CharacterRole.CONTROLLER, 1, might=9, grit=10, wit=14, luck=13)
        ]
    )
    
    # Guild 2: Iron Wolves
    party2 = Party(
        guild_id=2,
        guild_name="Iron Wolves",
        members=[
            Character("Grunk", CharacterRole.STRIKER, 2, might=16, grit=13, wit=7, luck=9),
            Character("Shadow", CharacterRole.BURGLAR, 2, might=10, grit=9, wit=10, luck=16),
            Character("Mystic", CharacterRole.SUPPORT, 2, might=7, grit=10, wit=16, luck=11),
            Character("Void", CharacterRole.CONTROLLER, 2, might=8, grit=11, wit=15, luck=12)
        ]
    )
    
    # Create scheduler with short interval for testing
    scheduler = ExpeditionScheduler(
        interval_minutes=5,  # Every 2 minutes for testing
        tick_duration=2    # Fast ticks for testing
    )
    
    # Register guilds
    scheduler.register_guild(party1)
    scheduler.register_guild(party2)
    
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
