An automated dungeon crawling simulation where guilds explore procedurally generated dungeons on a schedule.

## Overview
- Expeditions run automatically every hour
- Multiple guilds explore the same dungeon simultaneously  
- Viewers watch live updates and bet on outcomes
- No direct player control during expeditions

## Running the Simulation
```bash
python main.py

# Running Tests
python -m pytest tests/

# Development Setup

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install Dependencies
pip install -r requirements.txt

# Running the simulation
python scheduler/expedition_scheduler.py

# Resetting the simulation
python database/reset_database.py

# Checking DB Status
python database/reset_database.py --status
```

Fantasy Guild Manager — Complete Game Loop with All Mechanics (so far)

1. Dungeon Setup
1.1 Determine number of rooms per floor:
Rooms = 5 + 1d4
1.2 Current floor difficulty:
Floor Level = Number of floors completed + 1
1.3 Party starts with full HP and all spells enabled (unless disabled from previous expedition)

2. Party Selection
2.1 Select guild
2.2 Choose party members: 1 Striker, 1 Scout, 1 Support, 1 Controller
2.3 Apply any equipped magic items to stats

3. For Each Room, Repeat the Following Steps

3.1 Determine Room Contents
For last room of floor: Always Boss + Treasure (difficulty = Floor Level + 1)
For other rooms: Roll 1d100:

1–40: Combat encounter + Treasure
41–70: Trap + Treasure
71–94: Combat + Trap + Treasure
95–99: Boss + Treasure (difficulty = Floor Level + 1)
100: Healing fountain (Heals all wounds and de-buffs, resets downed tracker for Morale)

Generate Enemies (if combat/boss):

Regular combat: 1d4 + Floor Level enemies
Boss room: 1d4 + Floor Level + 1 enemies (boss counts as one)

For each enemy, determine type (Check floor and roll 1d4):
Tier 1 Enemies (Floors 1–2)
1) Giant Rat
HP: Floor × 5 + 1d4
AC: 10 + Floor Level
Damage: 1d4 + Floor Level
Special: On hit, roll 1d4. If result ≥ 3, target is Poisoned for 1d4 actions.

2) Slime
HP: Floor × 5 + 1d4
AC: (10 + Floor Level) – 1 (sluggish)
Damage: 1d4 + Floor Level
Special: On hit, roll 1d4. If result ≥ 3, target is Slowed for 1d4 actions.

3) Giant Bat
HP: Floor × 5 + 1d4
AC: (10 + Floor Level) + 2 (flying)
Damage: 1d4 + Floor Level
Special: None

4) Cave Beetle
HP: Floor × 5 + 1d4
AC: (10 + Floor Level) + 1 (hard shell)
Damage: 1d4 + Floor Level
Special: None

Tier 2 Enemies (Floors 3–4)
1) Skeleton
HP: Floor × 5 + 1d6
AC: (10 + Floor Level) + 2 (bones deflect blows)
Damage: 1d6 + Floor Level
Special: None

2) Zombie
HP: Floor × 5 + 1d6
AC: (10 + Floor Level) – 1 (slow)
Damage: 1d6 + Floor Level
Special: On hit, roll 1d4. If result ≥ 3, target is Weakened for 1d4 rounds.

3) Carrion Crow Swarm
HP: Floor × 5 + 1d6
AC: (10 + Floor Level) + 1 (hard to hit swarm)
Damage: 1d6 + Floor Level
Special: On hit, roll 1d4. If result ≥ 3, target is Blinded for 1d4 actions.

4) Spitting Spider
HP: Floor × 5 + 1d6
AC: 10 + Floor Level
Damage: 1d6 + Floor Level
Special: On hit, roll 1d4. If result ≥ 3, target is Poisoned for 1d4 actions.

Tier 3 Enemies (Floors 5–6)
1) Ghoul
HP: Floor × 5 + 1d8
AC: 10 + Floor Level
Damage: 1d8 + Floor Level
Special: On hit, roll 1d4. If result ≥ 3, target is Stunned (skip next turn).

2) Shadow Hound
HP: Floor × 5 + 1d8
AC: (10 + Floor Level) + 1 (shadowy form)
Damage: 1d8 + Floor Level
Special: On hit, roll 1d4. If result ≥ 3, target is Frightened for 1d4 actions.

3) Venomous Snake
HP: Floor × 5 + 1d8
AC: (10 + Floor Level) + 1 (quick strikes)
Damage: 1d8 + Floor Level
Special: On hit, roll 1d4. If result ≥ 3, target is Poisoned for 1d4 actions.

4) Animated Armor
HP: Floor × 5 + 1d8
AC: (10 + Floor Level) + 2 (metal plates)
Damage: 1d8 + Floor Level
Special: None


Tier 4 Enemies (Floors 7–8)
1) Bone Golem
HP: Floor × 5 + 2d4
AC: (10 + Floor Level/2) + 2 (reinforced bones)
Damage: 2d4 + Floor Level/2
Special: None

2) Dire Wolf
HP: Floor × 5 + 2d4
AC: 10 + Floor Level/2
Damage: 2d4 + Floor Level/2
Special: On hit, roll 1d4. If result ≥ 3, target is Frightened for 1d4 actions.

3) Plague Bear
HP: Floor × 5 + 2d4
AC: 10 + Floor Level/2
Damage: 2d4 + Floor Level/2
Special: On hit, roll 1d4. If result ≥ 3, target is Poisoned for 1d4 actions.

4) Gargoyle
HP: Floor × 5 + 2d4
AC: (10 + Floor Level/2) + 2 (stone hide and flying)
Damage: 2d4 + Floor Level/2
Special: None

Tier 5 Enemies (Floors 9–10)
1) Wraith
HP: Floor × 5 + 1d10
AC: (10 + Floor Level/2) + 2 (incorporeal)
Damage: 1d10 + Floor Level/2
Special: On hit, roll 1d4. If result ≥ 3, target is Cursed for 1d4 actions.

2) Revenant
HP: Floor × 5 + 1d10
AC: 10 + Floor Level/2
Damage: 1d10 + Floor Level/2
Special: On hit, roll 1d4. If result ≥ 3, target is Stunned (skip next turn).

3) Hell Hound
HP: Floor × 5 + 1d10
AC: 10 + Floor Level/2
Damage: 1d10 + Floor Level/2
Special: On hit, roll 1d4. If result ≥ 3, target is Burned (treat as Poisoned: -2 all rolls, 1 damage/round, 1d4 actions).

4) Stone Titan

HP: Floor × 5 + 1d10
AC: (10 + Floor Level/2) + 2 (massive stone body)
Damage: 1d10 + Floor Level/2
Special: None

Base Enemy Stats:
HP = Floor Level × 5 + 5
AC = 10 + Floor Level
Damage = 1d4 + Floor Level (increases by die type each 2 levels)

Boss Modifiers:

HP × 2
AC and Damage + 1
Roll 1d4 for special ability:

Rage: +2 damage when below half HP
Summon: Call 1d4 minions when first hitting half HP
Aura: All enemies get +1 to rolls
Regenerate: Heal 1d4 HP per round

3.2 Trap Resolution (if present)
Detection Check:
Trap Roll = 1d20 + Scout's LUCK
Trap DC = 10 + Floor Level
Resolution:

If Trap Roll = 1:

Trap triggers
Trap Damage = 1d6 × Floor Level to Scout
Roll 1d8 for debuff type:

Poisoned: -2 all rolls, 1 damage/round, 1d4 actions
Weakened: -2 MIGHT rolls, 1d4 rounds
Slowed: -2 initiative, no reactions, 1d4 actions
Stunned: Skip next turn
Confused: 50% hit random ally, 1d4 actions
Cursed: -2 LUCK rolls, 1d4 actions
Blinded: -4 attack rolls, 1d4 actions
Frightened: -2 all rolls vs enemies, 1d4 actions


If Trap Roll = 20:

Trap disarmed
Scout gains advantage on next roll


If 2-19 and Roll < DC:

Trap triggers
Trap Damage = 1d6 × Floor Level to random party member


If 2-19 and Roll ≥ DC:

Trap disarmed




3.3 Combat Resolution (if present)
Initiative: Roll 1d20 + GRIT for each combatant (Slowed: -2, Boots of Speed: auto-first)
Each Round:
Status Effect Updates (start of round):

Reduce all effect durations by 1
Apply recurring damage (Poisoned: 1 damage)
Remove expired effects

Character Turns (in initiative order):
A) Striker/Scout Basic Attack:

Attack Roll = 1d20 + MIGHT
Target AC = Enemy AC (or choose target based on tactical rules)

Attack Resolution:

If Roll = 20:

Automatic hit
Damage = Max die + 1 die roll + MIGHT

Striker: 8 + 1d8 + MIGHT
Scout: 6 + 1d6 + MIGHT




If Roll = 1: Automatic miss
If Roll + MIGHT ≥ Target AC:

Hit, normal damage

Striker: 1d8 + MIGHT
Scout: 1d6 + MIGHT




Otherwise: Miss

B) Support/Controller Spell Casting:
Spell Selection Priority:

If any ally poisoned AND have cure (Revitalize): Cast it
If any ally HP < 50% AND have heal: Cast heal
If all healthy:

Support: Cast buff on unbuffed ally
Controller: Cast damage/disable on enemy


If no useful spells: Basic attack (1d4 + MIGHT damage)

Spell Roll:

Spell Roll = 1d20 + WIT
Spell DC = 10 + Floor Level (or +1 for boss)

Spell Resolution:

If Roll = 1:

Spell fails
Spell is disabled for expedition


If Roll = 20:

Spell succeeds
Caster gains advantage on next spell


If Roll + WIT ≥ DC:

Apply spell effect (see spell list)


Otherwise: Spell fails

Enemy Turns:
Enemy Action (each enemy):

If Mage type and 1d6 ≥ 4: Cast random control spell
Otherwise: Attack

Enemy Attack:

Attack Roll = 1d20 + Enemy MIGHT
Target = Random living party member
Target AC = 10 + Target's GRIT (+2 if Shielded)

Damage:

If Roll + MIGHT ≥ Target AC:

Damage = Enemy damage die + Enemy MIGHT
If target HP ≤ 0: Target is downed



Boss Special Abilities (if applicable):

Rage: Check if below half HP
Summon: Check if first time below half HP
Aura: Apply +1 to all enemy rolls
Regenerate: Heal 1d4 HP

Continue rounds until victory or retreat

3.4 Treasure Resolution (if present)
Treasure Check:
Treasure Roll = 1d20 + Scout's LUCK
Treasure DC = 10 + Floor Level (+1 for boss room)
Results:

If Roll = 20:

Gold = Floor Level × 1d20
Roll 1d20 for magic item rarity:

1-12: Common (roll 1d10 on common table)
13-18: Uncommon (roll 1d8 on uncommon table)
19-20: Rare (roll 1d6 on rare table)




If Roll + LUCK ≥ DC:

Gold = Floor Level × 1d20


Otherwise: No treasure found


3.5 Room Completion
Update Stats:

Add gold to expedition total
Update damage dealt/taken
Count downed characters
Count disabled spells


3.6 Morale Check
Calculate Morale Threshold:
Morale = 0 + (Total Missing HP) + (5 × Disabled Spells) + (20 × Downed Allies) + (10 x Total Times Character Downed)
Morale Roll:

Normal room: Roll 1d100
Floor completion: Roll 2d100, take lower (disadvantage)

Result:

If Roll ≥ Morale: Continue expedition
If Roll < Morale: Retreat immediately


4. Proceed or Retreat

If Morale passed AND rooms remain on floor: Go to next room (return to 3.1)
If Morale passed AND floor complete:

Floor Level + 1
Generate new floor
Return to 3.1


If Morale failed OR party wiped: End expedition


5. End of Expedition
5.1 Final Tallies:

Total gold found
Magic items found (unidentified)
Floors cleared
Rooms cleared
Monsters defeated

5.2 Recovery Phase:
HP Recovery: All characters restored to full HP
Spell Recovery: For each disabled spell, roll 1d6:

1-2: Remains disabled next expedition
3-6: Spell recovered

Downed Character Recovery: For each downed character, roll 1d6:

1: Permanent -1 to random stat (roll 1d4: 1=MIGHT, 2=GRIT, 3=WIT, 4=LUCK)
2-3: Miss next expedition
4-6: Full recovery

Status Effects: All debuffs removed
5.3 Gold Distribution:

Guild Treasury: 50% of total gold
Party Members: 50% split equally (downed get half share)

5.4 Magic Item Identification:

Cost: 50 gold per item
Alternative: Use unidentified (25% chance cursed on equip)

5.5 Update Statistics:

Individual character stats
Guild totals
Success rate
Viewer sponsorship payouts


6. Between Expeditions

Equip identified magic items
Select party for next expedition
Disabled spells remain disabled as determined
Injured characters sit out as determined


