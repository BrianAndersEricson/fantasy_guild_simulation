"""
Flask application for viewing Fantasy Guild Manager expeditions.
This provides the web interface for watching live expeditions and reviewing past runs.
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime
from pathlib import Path

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for future API calls

# Database configuration
DB_PATH = Path(__file__).parent.parent / "fantasy_guild_test.db"


def get_db_connection():
    """Create a database connection with row factory for dict-like access"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn


@app.route('/')
def index():
    """Main page showing current/recent expeditions"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get the most recent expedition
        current_expedition = cursor.execute("""
            SELECT * FROM expeditions 
            ORDER BY start_time DESC 
            LIMIT 1
        """).fetchone()
        
        # Get participating guilds for current expedition
        if current_expedition:
            guilds = cursor.execute("""
                SELECT 
                    g.id, g.name, g.motto,
                    er.floors_cleared, er.rooms_cleared, er.gold_found,
                    er.survivors, er.retreated, er.wiped
                FROM guilds g
                JOIN expedition_results er ON g.id = er.guild_id
                WHERE er.expedition_id = ?
                ORDER BY er.floors_cleared DESC, er.gold_found DESC
            """, (current_expedition['id'],)).fetchall()
        else:
            guilds = []
        
        # Get recent expeditions for history
        recent_expeditions = cursor.execute("""
            SELECT 
                e.id, e.expedition_number, e.start_time, e.status,
                COUNT(er.id) as guild_count,
                SUM(er.gold_found) as total_gold
            FROM expeditions e
            LEFT JOIN expedition_results er ON e.id = er.expedition_id
            GROUP BY e.id
            ORDER BY e.start_time DESC
            LIMIT 10
        """).fetchall()
        
        conn.close()
        
        return render_template('index.html',
                             current_expedition=current_expedition,
                             guilds=guilds,
                             recent_expeditions=recent_expeditions)
                             
    except Exception as e:
        app.logger.error(f"Error in index route: {e}")
        return f"Database error: {e}", 500


@app.route('/expedition/<int:expedition_id>')
def view_expedition(expedition_id):
    """View a specific expedition with event replay capability"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get expedition details
        expedition = cursor.execute("""
            SELECT * FROM expeditions WHERE id = ?
        """, (expedition_id,)).fetchone()
        
        if not expedition:
            return "Expedition not found", 404
        
        # Get all guilds that participated with their characters
        guilds = cursor.execute("""
            SELECT 
                g.id, g.name, g.motto,
                er.floors_cleared, er.rooms_cleared, er.gold_found,
                er.survivors, er.retreated, er.wiped
            FROM guilds g
            JOIN expedition_results er ON g.id = er.guild_id
            WHERE er.expedition_id = ?
            ORDER BY er.floors_cleared DESC, er.gold_found DESC
        """, (expedition_id,)).fetchall()
        
        # Get character data for each guild
        guild_data = []
        for guild in guilds:
            guild_dict = dict(guild)
            
            # Get the party members that participated in this expedition
            # We need to get their state at the START of the expedition
            characters = cursor.execute("""
                SELECT DISTINCT
                    c.id, c.name, c.role, c.might, c.grit, c.wit, c.luck, c.max_hp
                FROM characters c
                JOIN event_log e ON e.details LIKE '%"' || c.name || '"%'
                WHERE e.guild_id = ? AND e.expedition_id = ?
                ORDER BY 
                    CASE c.role 
                        WHEN 'striker' THEN 1 
                        WHEN 'burglar' THEN 2 
                        WHEN 'support' THEN 3 
                        WHEN 'controller' THEN 4 
                    END
                LIMIT 4
            """, (guild['id'], expedition_id)).fetchall()
            
            # If we can't find characters from events, get the current roster
            if not characters:
                characters = cursor.execute("""
                    SELECT id, name, role, might, grit, wit, luck, max_hp
                    FROM characters
                    WHERE guild_id = ?
                    ORDER BY 
                        CASE role 
                            WHEN 'striker' THEN 1 
                            WHEN 'burglar' THEN 2 
                            WHEN 'support' THEN 3 
                            WHEN 'controller' THEN 4 
                        END
                    LIMIT 4
                """, (guild['id'],)).fetchall()
            
            guild_dict['characters'] = [dict(char) for char in characters]
            guild_data.append(guild_dict)
        
        conn.close()
        
        return render_template('expedition.html',
                             expedition=expedition,
                             guilds=guild_data)
                             
    except Exception as e:
        app.logger.error(f"Error viewing expedition {expedition_id}: {e}")
        return f"Error loading expedition: {e}", 500


@app.route('/api/expedition/<int:expedition_id>/events')
def get_expedition_events(expedition_id):
    """API endpoint to fetch all events for an expedition (for replay)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all events for this expedition
        events = cursor.execute("""
            SELECT 
                id, guild_id, guild_name, event_type, 
                description, priority, details, tick_number
            FROM event_log
            WHERE expedition_id = ?
            ORDER BY tick_number, id
        """, (expedition_id,)).fetchall()
        
        # Convert to list of dicts and parse JSON details
        event_list = []
        for event in events:
            event_dict = dict(event)
            if event_dict['details']:
                try:
                    event_dict['details'] = json.loads(event_dict['details'])
                except:
                    event_dict['details'] = {}
            event_list.append(event_dict)
        
        conn.close()
        
        return jsonify({
            'expedition_id': expedition_id,
            'event_count': len(event_list),
            'events': event_list
        })
        
    except Exception as e:
        app.logger.error(f"Error fetching events for expedition {expedition_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/guilds')
def guild_list():
    """Show all guilds with their overall statistics and rosters"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get all guilds with statistics
        guilds = cursor.execute("""
            SELECT
                g.*,
                COUNT(DISTINCT er.expedition_id) as expeditions_participated,
                COALESCE(SUM(er.gold_found), 0) as total_gold_from_expeditions,
                COALESCE(AVG(er.floors_cleared), 0) as avg_floors_cleared
            FROM guilds g
            LEFT JOIN expedition_results er ON g.id = er.guild_id
            WHERE g.is_active = 1
            GROUP BY g.id
            ORDER BY g.treasury DESC
        """).fetchall()

        # Convert to list of dicts and add character data
        guild_list = []
        total_fallen = 0
        
        for guild in guilds:
            guild_dict = dict(guild)
            
            # Get active (living) members
            active_members = cursor.execute("""
                SELECT id, name, role, might, grit, wit, luck, max_hp, times_downed
                FROM characters
                WHERE guild_id = ? AND is_alive = 1 AND is_available = 1
                ORDER BY
                    CASE role
                        WHEN 'striker' THEN 1
                        WHEN 'burglar' THEN 2
                        WHEN 'support' THEN 3
                        WHEN 'controller' THEN 4
                    END
            """, (guild['id'],)).fetchall()
            
            guild_dict['active_members'] = [dict(member) for member in active_members]
            
            # Get fallen heroes
            fallen_heroes = cursor.execute("""
                SELECT name, role, death_date
                FROM characters
                WHERE guild_id = ? AND is_alive = 0
                ORDER BY death_date DESC
                LIMIT 20
            """, (guild['id'],)).fetchall()
            
            guild_dict['fallen_heroes'] = [dict(hero) for hero in fallen_heroes]
            total_fallen += len(fallen_heroes)
            
            guild_list.append(guild_dict)

        conn.close()

        return render_template('guilds.html', 
                             guilds=guild_list,
                             total_fallen=total_fallen)

    except Exception as e:
        app.logger.error(f"Error in guild list: {e}")
        return f"Error loading guilds: {e}", 500

@app.route('/guild/<int:guild_id>')
def guild_detail(guild_id):
    """Show detailed information about a specific guild"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get guild info
        guild = cursor.execute("""
            SELECT * FROM guilds WHERE id = ?
        """, (guild_id,)).fetchone()
        
        if not guild:
            return "Guild not found", 404
        
        # Get current roster (living characters)
        living_characters = cursor.execute("""
            SELECT * FROM characters 
            WHERE guild_id = ? AND is_alive = 1
            ORDER BY role, name
        """, (guild_id,)).fetchall()
        
        # Get fallen heroes
        dead_characters = cursor.execute("""
            SELECT * FROM characters 
            WHERE guild_id = ? AND is_alive = 0
            ORDER BY death_date DESC
        """, (guild_id,)).fetchall()
        
        # Get recent expedition results
        recent_results = cursor.execute("""
            SELECT 
                er.*, e.expedition_number, e.start_time
            FROM expedition_results er
            JOIN expeditions e ON er.expedition_id = e.id
            WHERE er.guild_id = ?
            ORDER BY e.start_time DESC
            LIMIT 10
        """, (guild_id,)).fetchall()
        
        conn.close()
        
        return render_template('guild_detail.html',
                             guild=guild,
                             living_characters=living_characters,
                             dead_characters=dead_characters,
                             recent_results=recent_results)
                             
    except Exception as e:
        app.logger.error(f"Error viewing guild {guild_id}: {e}")
        return f"Error loading guild: {e}", 500


@app.route('/api/current-expedition/status')
def current_expedition_status():
    """API endpoint for getting current expedition status (for live updates)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get the most recent running expedition
        expedition = cursor.execute("""
            SELECT * FROM expeditions 
            WHERE status = 'running'
            ORDER BY start_time DESC 
            LIMIT 1
        """).fetchone()
        
        if not expedition:
            # No running expedition, get the most recent one
            expedition = cursor.execute("""
                SELECT * FROM expeditions 
                ORDER BY start_time DESC 
                LIMIT 1
            """).fetchone()
        
        if expedition:
            # Get latest events for each guild
            latest_events = cursor.execute("""
                SELECT 
                    guild_id, guild_name, 
                    MAX(tick_number) as latest_tick,
                    COUNT(*) as event_count
                FROM event_log
                WHERE expedition_id = ?
                GROUP BY guild_id, guild_name
            """, (expedition['id'],)).fetchall()
            
            expedition_dict = dict(expedition)
            expedition_dict['guilds'] = [dict(e) for e in latest_events]
            
            conn.close()
            return jsonify(expedition_dict)
        else:
            conn.close()
            return jsonify({'error': 'No expeditions found'}), 404
            
    except Exception as e:
        app.logger.error(f"Error getting current status: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Development server configuration
    app.run(debug=True, host='0.0.0.0', port=5000)
