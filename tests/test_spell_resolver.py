import random
import pytest
from unittest.mock import Mock, patch

from models.character import Character, CharacterRole
from models.spell import SPELLS_BY_NAME, SpellType, TargetType
from simulation.spell_resolver import SpellResolver, SpellResult
from simulation.debuff_system import DebuffManager, DebuffType, Debuff


# === FIXTURES AND HELPERS ===

@pytest.fixture
def rng():
    return random.Random(123)


@pytest.fixture
def resolver(rng):
    return SpellResolver(rng)


@pytest.fixture
def support_char():
    # A support character with known spells and good grit/wit
    return Character(
        name="Lyria",
        role=CharacterRole.SUPPORT,
        guild_id=1,
        grit=12,
        wit=9,
        luck=6,
        known_spells=["Mend Wounds", "Sanctuary Pulse", "Ward of Vitality"]
    )


@pytest.fixture
def wounded_ally():
    c = Character(name="Wounded", role=CharacterRole.STRIKER, guild_id=1, grit=10)
    c.current_hp = 2  # Critically wounded
    return c


@pytest.fixture
def healthy_ally():
    return Character(name="Healthy", role=CharacterRole.BURGLAR, guild_id=1, grit=10)


@pytest.fixture
def dummy_enemy():
    class DummyEnemy:
        def __init__(self):
            self.name = "Goblin"
            self.hp = 10
            self.current_hp = 10
            self.debuff_manager = None

        def take_damage(self, dmg):
            self.current_hp -= dmg

    return DummyEnemy()


# === TESTS ===

def test_spell_selection_prioritizes_critically_wounded(resolver, support_char, wounded_ally, healthy_ally):
    party = [support_char, wounded_ally, healthy_ally]
    enemies = []

    selected_spell = resolver.select_spell_for_character(support_char, party, enemies, floor_level=1)
    assert selected_spell == "Mend Wounds"


def test_target_selection_picks_most_wounded(resolver, support_char, wounded_ally, healthy_ally):
    spell = SPELLS_BY_NAME["Mend Wounds"]
    party = [support_char, wounded_ally, healthy_ally]
    target = resolver.select_target_for_spell(spell, support_char, party, [])
    assert target.name == "Wounded"


def test_cast_healing_spell_success(resolver, support_char, wounded_ally):
    """Test successful healing spell with guaranteed success roll"""
    spell_name = "Mend Wounds"
    pre_hp = wounded_ally.current_hp

    # Mock the RNG to guarantee success (roll 15 on d20)
    with patch.object(resolver.rng, 'randint') as mock_randint:
        def mock_rolls(low, high):
            if low == 1 and high == 20:  # Spell roll
                return 15  # Good roll for spell success
            elif low == 1 and high == 4:  # Healing roll (1d4)
                return 3   # Good healing roll
            else:
                return 5   # Default for other rolls
        
        mock_randint.side_effect = mock_rolls

        result = resolver.cast_spell(
            caster=support_char,
            spell_name=spell_name,
            target=wounded_ally,
            floor_level=1
        )

    # Verify success
    assert result.result in [SpellResult.SUCCESS, SpellResult.CRITICAL_SUCCESS]
    assert result.spell_name == spell_name
    assert result.caster == support_char.name
    assert result.target == wounded_ally.name
    assert result.healing_done > 0
    assert wounded_ally.current_hp > pre_hp
    assert "healing" in result.description.lower()

    # Verify the math worked
    # Character has wit=9 (mod +3) + grit=12 (mod +4) = +7 total
    # Roll 15 + 7 = 22 vs DC 11 = success
    assert result.roll >= 11  # Should have beaten the DC


def test_cast_healing_spell_failure(resolver, support_char, wounded_ally):
    """Test healing spell failure with guaranteed bad roll"""
    spell_name = "Mend Wounds"
    pre_hp = wounded_ally.current_hp

    # Mock the RNG to guarantee failure (roll 1 on d20, but not crit fail)
    with patch.object(resolver.rng, 'randint') as mock_randint:
        mock_randint.return_value = 2  # Low roll that will fail after modifiers

        result = resolver.cast_spell(
            caster=support_char,
            spell_name=spell_name,
            target=wounded_ally,
            floor_level=1
        )

    # Verify failure (but not critical failure)
    assert result.result == SpellResult.FAILURE
    assert result.healing_done == 0
    assert wounded_ally.current_hp == pre_hp  # No healing occurred
    assert "fails to cast" in result.description.lower()


def test_cast_healing_spell_critical_failure(resolver, support_char, wounded_ally):
    """Test critical failure disables spell"""
    spell_name = "Mend Wounds"
    
    # Ensure spell is not already disabled
    if spell_name in support_char.disabled_spells:
        support_char.disabled_spells.remove(spell_name)

    # Mock the RNG to guarantee critical failure (natural 1)
    with patch.object(resolver.rng, 'randint') as mock_randint:
        mock_randint.return_value = 1  # Natural 1 = critical failure

        result = resolver.cast_spell(
            caster=support_char,
            spell_name=spell_name,
            target=wounded_ally,
            floor_level=1
        )

    # Verify critical failure
    assert result.result == SpellResult.CRITICAL_FAILURE
    assert spell_name in support_char.disabled_spells
    assert "critically fails" in result.description.lower()
    assert "disabled" in result.description.lower()


def test_cast_spell_fails_if_disabled(resolver, support_char, wounded_ally):
    """Test that disabled spells cannot be cast"""
    support_char.disabled_spells.append("Mend Wounds")

    result = resolver.cast_spell(
        caster=support_char,
        spell_name="Mend Wounds",
        target=wounded_ally,
        floor_level=1
    )

    assert result.result == SpellResult.SPELL_DISABLED
    assert "cannot cast" in result.description.lower()


def test_debuff_spell_applies_correctly(resolver, rng, dummy_enemy):
    """Test debuff spell with guaranteed success"""
    # Import at module level to avoid import issues
    from simulation.debuff_system import DebuffManager
    
    # Create a controller with Mindshatter
    caster = Character(
        name="Aeria",
        role=CharacterRole.CONTROLLER,
        guild_id=2,
        wit=12,  # +4 modifier
        luck=12, # +4 modifier
        known_spells=["Mindshatter"]
    )

    # Ensure enemy has a debuff manager
    dummy_enemy.debuff_manager = DebuffManager()

    # Mock for guaranteed success
    # Mindshatter: DC 12 (10 base + 1 floor + 1 enemy level)
    # Controller has wit+luck = +8 bonus, so roll 5+ succeeds
    with patch.object(resolver.rng, 'randint') as mock_randint:
        def mock_rolls(low, high):
            if low == 1 and high == 20:  # Spell roll
                return 10  # 10 + 8 bonus = 18 vs DC 12 = success
            else:
                return 2   # Duration rolls
        
        mock_randint.side_effect = mock_rolls

        result = resolver.cast_spell(
            caster=caster,
            spell_name="Mindshatter",
            target=dummy_enemy,
            floor_level=1,
            enemy_level=1
        )

    assert result.result in [SpellResult.SUCCESS, SpellResult.CRITICAL_SUCCESS]
    assert result.debuff_applied == DebuffType.STUNNED.value
    
    # Check that a debuff was actually applied
    active_debuffs = dummy_enemy.debuff_manager.get_active_debuffs()
    assert len(active_debuffs) > 0, "No debuffs were applied"
    
    # Check that it's a stun debuff by comparing string values
    stun_debuff = active_debuffs[0]
    assert stun_debuff.debuff_type.value == "stunned"
    assert stun_debuff.duration_remaining > 0
    
    # Test debuff manager functionality by checking if character would be stunned
    print("Active debuffs:", dummy_enemy.debuff_manager.active_debuffs)
    assert dummy_enemy.debuff_manager.is_stunned()


def test_buff_spell_applies_shield(resolver, support_char, healthy_ally):
    """Test shield buff with guaranteed success"""
    # Mock for guaranteed success
    with patch.object(resolver.rng, 'randint') as mock_randint:
        mock_randint.return_value = 15  # High roll for guaranteed success

        result = resolver.cast_spell(
            caster=support_char,
            spell_name="Ward of Vitality",
            target=healthy_ally,
            floor_level=1
        )

    assert result.result in [SpellResult.SUCCESS, SpellResult.CRITICAL_SUCCESS]
    assert "shield" in result.description.lower()
    assert healthy_ally.damage_shield > 0


def test_critical_success_enhances_effects(resolver, support_char, wounded_ally):
    """Test that critical success (natural 20) enhances spell effects"""
    spell_name = "Mend Wounds"
    pre_hp = wounded_ally.current_hp

    # Mock natural 20 for critical success
    with patch.object(resolver.rng, 'randint') as mock_randint:
        def mock_rolls(low, high):
            if low == 1 and high == 20:  # First call is spell roll
                return 20  # Natural 20 = critical success
            elif low == 1 and high == 4:  # Healing die
                return 2   # Base healing
            else:
                return 3   # Other rolls
        
        mock_randint.side_effect = mock_rolls

        result = resolver.cast_spell(
            caster=support_char,
            spell_name=spell_name,
            target=wounded_ally,
            floor_level=1
        )

    assert result.result == SpellResult.CRITICAL_SUCCESS
    assert result.roll == 20
    # Critical success should enhance healing (double or +4, whichever is better)
    # Base: 2 (die) + 4 (grit) = 6, enhanced = max(12, 10) = 12
    assert result.healing_done >= 10  # Should be enhanced
    assert "CRITICAL" in result.description


# === INTEGRATION TESTS ===

def test_spell_resolver_with_multiple_spells(resolver, support_char):
    """Test that resolver can handle characters with multiple spells"""
    # Create party with various conditions
    wounded1 = Character("Wounded1", CharacterRole.STRIKER, 1)
    wounded1.current_hp = 3
    
    wounded2 = Character("Wounded2", CharacterRole.BURGLAR, 1) 
    wounded2.current_hp = 1
    
    healthy = Character("Healthy", CharacterRole.CONTROLLER, 1)
    
    party = [support_char, wounded1, wounded2, healthy]
    
    # Should prioritize most critically wounded
    selected_spell = resolver.select_spell_for_character(support_char, party, [], floor_level=1)
    
    # Should select a healing spell for the wounded allies
    assert selected_spell in ["Mend Wounds", "Sanctuary Pulse"]
    
    # Should target the most wounded ally
    if selected_spell == "Mend Wounds":
        spell = SPELLS_BY_NAME[selected_spell]
        target = resolver.select_target_for_spell(spell, support_char, party, [])
        assert target.name == "Wounded2"  # Most wounded


def test_no_valid_targets_returns_none(resolver, support_char):
    """Test behavior when no valid targets exist"""
    # Healing spell with no wounded allies
    healthy_party = [
        Character("Healthy1", CharacterRole.STRIKER, 1),
        Character("Healthy2", CharacterRole.BURGLAR, 1)
    ]
    
    spell = SPELLS_BY_NAME["Mend Wounds"]
    target = resolver.select_target_for_spell(spell, support_char, healthy_party, [])
    
    # Should return None since no one needs healing
    assert target is None
