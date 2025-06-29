/**
 * Expedition Replay System
 * Handles loading and playing back expedition events with visual updates
 * Updated to work with the new enemy system and event types
 */

class ExpeditionReplay {
    constructor(expeditionId, expeditionData) {
        this.expeditionId = expeditionId;
        this.expeditionData = expeditionData;
        this.events = [];
        this.currentEventIndex = 0;
        this.isPlaying = false;
        this.playbackSpeed = 1;
        this.playbackInterval = null;

        // Game state
        this.guildStates = {};
        this.currentFloor = 1;
        this.currentRoom = 1;
        this.combatState = {
            active: false,
            enemies: {},  // Changed to object to track by name
            enemyCounter: 0
        };
    }

    async initialize() {
        await this.loadEvents();
        this.initializeGuildStates();
        this.setupControls();
    }

    async loadEvents() {
        try {
            const response = await fetch(`/api/expedition/${this.expeditionId}/events`);
            const data = await response.json();
            this.events = data.events;
            console.log(`Loaded ${this.events.length} events`);

            // Clear loading message
            document.getElementById('event-entries').innerHTML = '';

            // Auto-play if live
            if (this.expeditionData.status === 'running') {
                setTimeout(() => this.togglePlayback(), 500);
            }
        } catch (error) {
            console.error('Error loading events:', error);
            document.getElementById('event-entries').innerHTML =
                '<div class="alert alert-error">Failed to load expedition events</div>';
        }
    }

    initializeGuildStates() {
        // Initialize from template data (passed from server)
        Object.keys(window.guildData).forEach(guildId => {
            const guild = window.guildData[guildId];
            this.guildStates[guildId] = {
                name: guild.name,
                gold: 0,
                floors: 0,
                rooms: 0,
                characters: guild.characters.map(char => ({
                    ...char,
                    current_hp: char.max_hp,  // Start at full HP
                    debuffs: []  // Track active debuffs
                }))
            };

            // Create character displays
            this.createGuildDisplay(guildId);
        });
    }

    createGuildDisplay(guildId) {
        const partyDiv = document.getElementById(`guild-${guildId}-party`);
        if (!partyDiv) return;

        partyDiv.innerHTML = '';
        const guild = this.guildStates[guildId];

        guild.characters.forEach(char => {
            const safeCharId = this.getSafeCharId(char.name);
            const memberDiv = document.createElement('div');
            memberDiv.className = 'party-member';
            memberDiv.id = `guild-${guildId}-${safeCharId}`;
            memberDiv.innerHTML = `
                <div>
                    <div class="member-name">${char.name}</div>
                    <div class="member-role">${char.role}</div>
                    <div class="member-debuffs" id="debuffs-${guildId}-${char.id}"></div>
                </div>
                <div>
                    <div class="member-hp" id="hp-${guildId}-${char.id}">${char.current_hp}/${char.max_hp}</div>
                    <div class="hp-bar">
                        <div class="hp-fill" id="hp-bar-${guildId}-${char.id}" style="width: 100%"></div>
                    </div>
                </div>
            `;
            partyDiv.appendChild(memberDiv);
        });

        // Initialize gold and floor displays
        this.updateGuildStats(guildId);
    }

    setupControls() {
        // Play/Pause button
        window.togglePlayback = () => this.togglePlayback();
        window.restartReplay = () => this.restart();
        window.updatePlaybackSpeed = () => {
            this.playbackSpeed = parseFloat(document.getElementById('speed-select').value);
            if (this.isPlaying) {
                this.pause();
                this.play();
            }
        };
    }

    togglePlayback() {
        if (this.isPlaying) {
            this.pause();
        } else {
            this.play();
        }
    }

    play() {
        this.isPlaying = true;
        document.getElementById('play-button').style.display = 'none';
        document.getElementById('pause-button').style.display = 'inline-block';

        this.playbackInterval = setInterval(() => {
            if (this.currentEventIndex < this.events.length) {
                try {
                    this.processEvent(this.events[this.currentEventIndex]);
                    this.currentEventIndex++;
                } catch (error) {
                    console.error('Error processing event:', error, this.events[this.currentEventIndex]);
                    this.currentEventIndex++;
                }
            } else {
                this.pause();
                console.log('Replay complete');
            }
        }, 2000 / this.playbackSpeed);
    }

    pause() {
        this.isPlaying = false;
        document.getElementById('play-button').style.display = 'inline-block';
        document.getElementById('pause-button').style.display = 'none';

        if (this.playbackInterval) {
            clearInterval(this.playbackInterval);
            this.playbackInterval = null;
        }
    }

    restart() {
        this.pause();
        this.currentEventIndex = 0;
        this.currentFloor = 1;
        this.currentRoom = 1;
        this.combatState = { active: false, enemies: {}, enemyCounter: 0 };

        document.getElementById('event-entries').innerHTML = '';
        this.initializeGuildStates();
        this.updateRoomDisplay();
    }

    processEvent(event) {
        this.addEventToLog(event);

        // Route to appropriate handler based on new event types
        const handlers = {
            // Expedition flow
            'expedition_start': () => this.handleExpeditionStart(event),
            'expedition_retreat': () => this.handleExpeditionEnd(event),
            'expedition_complete': () => this.handleExpeditionEnd(event),
            'expedition_wipe': () => this.handleExpeditionWipe(event),
            
            // Dungeon navigation
            'floor_enter': () => this.handleFloorEnter(event),
            'room_enter': () => this.handleRoomEnter(event),
            'room_complete': () => this.handleRoomComplete(event),
            
            // Combat events
            'combat_start': () => this.handleCombatStart(event),
            'combat_end': () => this.handleCombatEnd(event),
            'enemy_appears': () => this.handleEnemyAppears(event),
            'enemy_defeated': () => this.handleEnemyDefeated(event),
            'boss_ability_triggered': () => this.handleBossAbility(event),
            
            // Attack events
            'attack_hit': () => this.handleAttackHit(event),
            'attack_miss': () => {}, // Just log, no special handling
            'attack_critical': () => this.handleAttackHit(event), // Handle like hit but with more damage
            
            // Spell events
            'spell_cast': () => this.handleSpellCast(event),
            'spell_fail': () => {}, // Just log
            'character_healed': () => this.handleCharacterHealed(event),
            
            // Status effects
            'debuff_applied': () => this.handleDebuffApplied(event),
            'debuff_expired': () => this.handleDebuffExpired(event),
            'status_damage': () => this.handleStatusDamage(event),
            
            // Character status
            'character_unconscious': () => this.handleCharacterDowned(event),
            'character_dies': () => this.handleCharacterDeath(event),
            
            // Traps and treasure
            'trap_triggered': () => this.handleTrapTriggered(event),
            'trap_detected': () => {}, // Just log
            'treasure_found': () => this.handleTreasureFound(event),
            
            // Morale
            'morale_check': () => this.handleMoraleCheck(event),
        };

        const handler = handlers[event.event_type];
        if (handler) {
            handler();
        } else {
            console.log('Unhandled event type:', event.event_type);
        }
    }

    // === Event Handlers ===

    handleExpeditionStart(event) {
        console.log('Expedition starting for', event.guild_name);
    }

    handleExpeditionEnd(event) {
        const guildPanel = document.getElementById(`guild-${event.guild_id}-panel`);
        if (guildPanel) {
            if (event.event_type === 'expedition_retreat') {
                guildPanel.style.borderColor = '#ff9800';
            } else if (event.event_type === 'expedition_complete') {
                guildPanel.style.borderColor = 'var(--ff-green)';
            }
        }
    }

    handleExpeditionWipe(event) {
        const guildPanel = document.getElementById(`guild-${event.guild_id}-panel`);
        if (guildPanel) {
            guildPanel.style.opacity = '0.5';
            guildPanel.style.borderColor = 'var(--ff-red)';
        }
    }

    handleFloorEnter(event) {
        if (event.details && event.details.floor) {
            this.currentFloor = event.details.floor;
            document.getElementById('floor-indicator').textContent = `Floor ${this.currentFloor}`;
            this.currentRoom = 0;
            this.updateRoomDisplay();
        }
    }

    handleRoomEnter(event) {
        if (event.details && event.details.room) {
            this.currentRoom = event.details.room;
            this.updateRoomDisplay();
        }
    }

    handleRoomComplete(event) {
        const guildId = event.guild_id;
        const guild = this.guildStates[guildId];
        if (guild) {
            guild.rooms++;
        }
    }

    handleCombatStart(event) {
        this.combatState.active = true;
        this.combatState.enemies = {};
        this.combatState.enemyCounter = 0;
        
        const combatDiv = document.getElementById('combat-display');
        combatDiv.classList.add('active');
        
        // Clear enemy display
        const enemyGroup = document.getElementById('enemy-group');
        enemyGroup.innerHTML = '';
    }

    handleEnemyAppears(event) {
        if (!event.details || !event.details.enemy) return;
        
        const enemyName = event.details.enemy;
        const isBoss = event.details.is_boss || false;
        
        // Create enemy in state
        const enemy = {
            name: enemyName,
            displayId: this.combatState.enemyCounter++,
            alive: true,
            isBoss: isBoss
        };
        
        this.combatState.enemies[enemyName] = enemy;
        
        // Create enemy display
        const enemyGroup = document.getElementById('enemy-group');
        const enemyDiv = document.createElement('div');
        enemyDiv.className = 'enemy-sprite';
        enemyDiv.id = `enemy-${enemy.displayId}`;
        enemyDiv.innerHTML = `
            ${isBoss ? '👺' : '👹'}
            <div class="enemy-name">${enemyName}</div>
        `;
        
        if (isBoss) {
            enemyDiv.classList.add('boss');
        }
        
        enemyGroup.appendChild(enemyDiv);
    }

    handleEnemyDefeated(event) {
        if (!event.details || !event.details.enemy) return;
        
        const enemyName = event.details.enemy;
        const enemy = this.combatState.enemies[enemyName];
        
        if (enemy) {
            enemy.alive = false;
            const enemyDiv = document.getElementById(`enemy-${enemy.displayId}`);
            if (enemyDiv) {
                enemyDiv.style.opacity = '0.3';
                enemyDiv.style.borderColor = 'var(--ff-silver)';
                enemyDiv.classList.add('defeated');
            }
        }
    }

    handleBossAbility(event) {
        // Add visual effect for boss abilities
        if (event.details && event.details.boss) {
            const bossName = event.details.boss;
            const enemy = this.combatState.enemies[bossName];
            
            if (enemy) {
                const enemyDiv = document.getElementById(`enemy-${enemy.displayId}`);
                if (enemyDiv) {
                    enemyDiv.style.animation = 'boss-ability 1s ease';
                    setTimeout(() => enemyDiv.style.animation = '', 1000);
                }
            }
        }
    }

    handleCombatEnd(event) {
        this.combatState.active = false;
        document.getElementById('combat-display').classList.remove('active');
        this.combatState.enemies = {};
    }

    handleAttackHit(event) {
        const details = event.details || {};
        const damage = details.damage || 0;
        
        // Check if this is an enemy attacking a character
        if (details.enemy === true && details.target) {
            // Enemy attacking character
            const targetChar = this.findCharacterByName(event.guild_id, details.target);
            if (targetChar && damage > 0) {
                this.damageCharacter(event.guild_id, targetChar, damage);
            }
        }
        // Check if confused attack (character hitting ally)
        else if (details.confused && details.target) {
            const targetChar = this.findCharacterByName(event.guild_id, details.target);
            if (targetChar && damage > 0) {
                this.damageCharacter(event.guild_id, targetChar, damage);
            }
        }
        // Otherwise it's a character attacking an enemy
        else if (details.target && damage > 0 && !details.enemy) {
            // Character attacking enemy - visual effect on enemy if they exist
            const enemy = this.combatState.enemies[details.target];
            if (enemy && enemy.alive) {
                const enemyDiv = document.getElementById(`enemy-${enemy.displayId}`);
                if (enemyDiv) {
                    enemyDiv.style.animation = 'damage-flash 0.5s ease';
                    setTimeout(() => enemyDiv.style.animation = '', 500);
                }
            }
        }
    }

    handleSpellCast(event) {
        const details = event.details || {};
        
        // Handle damage spells on enemies
        if (details.damage && details.target) {
            // Check if target is an enemy
            const enemy = this.combatState.enemies[details.target];
            if (enemy && enemy.alive) {
                // Visual effect on enemy
                const enemyDiv = document.getElementById(`enemy-${enemy.displayId}`);
                if (enemyDiv) {
                    enemyDiv.style.animation = 'spell-hit 0.5s ease';
                    setTimeout(() => enemyDiv.style.animation = '', 500);
                }
            }
        }
    }

    handleCharacterHealed(event) {
        const details = event.details || {};
        const targetName = details.target || details.character;
        const healing = details.healing || 0;
        
        if (targetName && healing > 0) {
            const targetChar = this.findCharacterByName(event.guild_id, targetName);
            if (targetChar) {
                targetChar.current_hp = Math.min(targetChar.max_hp, targetChar.current_hp + healing);
                this.updateCharacterHP(event.guild_id, targetChar);
                
                // Healing animation
                const safeCharId = this.getSafeCharId(targetChar.name);
                const memberElement = document.getElementById(`guild-${event.guild_id}-${safeCharId}`);
                if (memberElement) {
                    memberElement.style.animation = 'heal-flash 1s ease';
                    setTimeout(() => memberElement.style.animation = '', 1000);
                }
            }
        }
    }

    handleDebuffApplied(event) {
        const details = event.details || {};
        const targetName = details.target;
        const debuffType = details.debuff;
        const duration = details.duration || 0;
        
        if (targetName && debuffType) {
            const targetChar = this.findCharacterByName(event.guild_id, targetName);
            if (targetChar) {
                // Add debuff to character
                targetChar.debuffs.push({
                    type: debuffType,
                    duration: duration
                });
                
                // Update debuff display
                this.updateCharacterDebuffs(event.guild_id, targetChar);
                
                // Visual effect
                const safeCharId = this.getSafeCharId(targetChar.name);
                const memberElement = document.getElementById(`guild-${event.guild_id}-${safeCharId}`);
                if (memberElement) {
                    memberElement.classList.add('debuffed');
                    setTimeout(() => memberElement.classList.remove('debuffed'), 500);
                }
            }
        }
    }

    handleDebuffExpired(event) {
        const details = event.details || {};
        const characterName = details.character;
        const debuffType = details.debuff;
        
        if (characterName && debuffType) {
            const character = this.findCharacterByName(event.guild_id, characterName);
            if (character) {
                // Remove the debuff
                character.debuffs = character.debuffs.filter(d => d.type !== debuffType);
                this.updateCharacterDebuffs(event.guild_id, character);
            }
        }
    }

    handleStatusDamage(event) {
        const details = event.details || {};
        const characterName = details.character || details.target;
        const damage = details.damage || 0;
        const source = details.source || 'status effect';
        
        if (characterName && damage > 0) {
            const character = this.findCharacterByName(event.guild_id, characterName);
            if (character) {
                this.damageCharacter(event.guild_id, character, damage);
                
                // Special effect for poison damage
                if (source === 'poison') {
                    const safeCharId = this.getSafeCharId(character.name);
                    const memberElement = document.getElementById(`guild-${event.guild_id}-${safeCharId}`);
                    if (memberElement) {
                        memberElement.classList.add('poisoned');
                        setTimeout(() => memberElement.classList.remove('poisoned'), 500);
                    }
                }
            }
        }
    }

    handleCharacterDowned(event) {
        const characterName = event.details?.character;
        if (characterName) {
            const character = this.findCharacterByName(event.guild_id, characterName);
            if (character) {
                this.downCharacter(event.guild_id, character);
            }
        }
    }

    handleCharacterDeath(event) {
        const characterName = event.details?.character;
        if (characterName) {
            const character = this.findCharacterByName(event.guild_id, characterName);
            if (character) {
                this.downCharacter(event.guild_id, character);
                
                // Add death marker
                const safeCharId = this.getSafeCharId(character.name);
                const memberElement = document.getElementById(`guild-${event.guild_id}-${safeCharId}`);
                if (memberElement) {
                    memberElement.classList.add('permanently-dead');
                }
            }
        }
    }

    handleTrapTriggered(event) {
        const details = event.details || {};
        const characterName = details.character || details.target;
        const damage = details.damage || 0;
        
        if (characterName && damage > 0) {
            const character = this.findCharacterByName(event.guild_id, characterName);
            if (character) {
                this.damageCharacter(event.guild_id, character, damage);
            }
        }
    }

    handleTreasureFound(event) {
        if (event.details && event.details.gold) {
            const guild = this.guildStates[event.guild_id];
            if (guild) {
                guild.gold += event.details.gold;
                this.updateGuildStats(event.guild_id);
                
                // Flash gold display
                const goldElement = document.getElementById(`guild-${event.guild_id}-gold`);
                if (goldElement) {
                    goldElement.style.animation = 'gold-flash 1s ease';
                    setTimeout(() => goldElement.style.animation = '', 1000);
                }
            }
        }
    }

    handleMoraleCheck(event) {
        if (event.details && event.details.success === false) {
            const guildPanel = document.getElementById(`guild-${event.guild_id}-panel`);
            if (guildPanel) {
                guildPanel.style.opacity = '0.7';
                guildPanel.style.borderColor = 'var(--ff-red)';
            }
        }
    }

    // === Helper Methods ===

    findCharacterByName(guildId, name) {
        const guild = this.guildStates[guildId];
        if (!guild) return null;

        return guild.characters.find(c =>
            c.name === name ||
            c.name.split(' ')[0] === name ||
            c.name.toLowerCase() === name.toLowerCase()
        );
    }

    damageCharacter(guildId, character, damage) {
        character.current_hp = Math.max(0, character.current_hp - damage);

        const safeCharId = this.getSafeCharId(character.name);

        // Flash animation
        const memberElement = document.getElementById(`guild-${guildId}-${safeCharId}`);
        if (memberElement) {
            memberElement.classList.add('damaged');
            setTimeout(() => memberElement.classList.remove('damaged'), 500);
        }

        // Update HP display
        this.updateCharacterHP(guildId, character);
    }

    downCharacter(guildId, character) {
        character.current_hp = 0;

        const safeCharId = this.getSafeCharId(character.name);
        const memberElement = document.getElementById(`guild-${guildId}-${safeCharId}`);
        if (memberElement) {
            memberElement.classList.add('dead');
        }

        this.updateCharacterHP(guildId, character);
    }

    updateCharacterHP(guildId, character) {
        const hpElement = document.getElementById(`hp-${guildId}-${character.id}`);
        if (hpElement) {
            hpElement.textContent = `${character.current_hp}/${character.max_hp}`;
        }

        const hpBar = document.getElementById(`hp-bar-${guildId}-${character.id}`);
        if (hpBar) {
            const hpPercent = (character.current_hp / character.max_hp) * 100;
            hpBar.style.width = `${hpPercent}%`;

            if (hpPercent <= 25) {
                hpBar.className = 'hp-fill critical';
            } else if (hpPercent <= 50) {
                hpBar.className = 'hp-fill low';
            } else {
                hpBar.className = 'hp-fill';
            }
        }
    }

    updateCharacterDebuffs(guildId, character) {
        const debuffElement = document.getElementById(`debuffs-${guildId}-${character.id}`);
        if (debuffElement) {
            const debuffIcons = {
                'poisoned': '☠️',
                'weakened': '💪',
                'slowed': '🐌',
                'stunned': '💫',
                'confused': '❓',
                'cursed': '🔮',
                'blinded': '👁️',
                'frightened': '😱'
            };
            
            const debuffText = character.debuffs
                .map(d => debuffIcons[d.type] || d.type)
                .join(' ');
            
            debuffElement.textContent = debuffText;
        }
    }

    updateGuildStats(guildId) {
        const guild = this.guildStates[guildId];
        if (!guild) return;

        const goldElement = document.getElementById(`guild-${guildId}-gold`);
        if (goldElement) {
            goldElement.textContent = guild.gold;
        }

        const floorsElement = document.getElementById(`guild-${guildId}-floors`);
        if (floorsElement) {
            floorsElement.textContent = guild.floors;
        }
    }

    updateRoomDisplay() {
        const roomMap = document.getElementById('room-map');
        roomMap.innerHTML = '';

        document.getElementById('combat-display').classList.remove('active');

        for (let i = 1; i <= 8; i++) {
            const room = document.createElement('div');
            room.className = 'room-node';

            if (i < this.currentRoom) {
                room.classList.add('cleared');
                room.innerHTML = '✓';
            } else if (i === this.currentRoom) {
                room.classList.add('current');
                room.innerHTML = '⚔️';
            } else {
                room.innerHTML = '?';
            }

            roomMap.appendChild(room);
        }
    }

    addEventToLog(event) {
        const logDiv = document.getElementById('event-entries');
        const entry = document.createElement('div');
        entry.className = `event-entry ${event.priority}`;

        const startTime = new Date(this.expeditionData.startTime);
        const eventTime = new Date(startTime.getTime() + (event.tick_number * 2000));
        const timeStr = eventTime.toLocaleTimeString();

        entry.innerHTML = `
            <span class="event-time">[${timeStr}]</span>
            <span class="event-guild">${event.guild_name}:</span>
            ${event.description}
        `;

        logDiv.appendChild(entry);

        // Smooth auto-scroll to bottom
        logDiv.scrollTo({
            top: logDiv.scrollHeight,
            behavior: 'smooth'
        });
    }

    getSafeCharId(name) {
        return name.toLowerCase().replace(/[^a-z0-9]/g, '-');
    }
}
