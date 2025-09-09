"""Tests for models module."""

import pytest
import tempfile
import os
from models import Character, SimpleTransitiveSession, RankingEntry


class TestCharacter:
    """Test Character class."""
    
    def test_valid_character_creation(self):
        """Test creating valid character."""
        char = Character(name="Test Character", image_path="test.png")
        assert char.name == "Test Character"
        assert char.image_path == "test.png"
    
    def test_empty_name_validation(self):
        """Test validation of empty character name."""
        with pytest.raises(ValueError, match="Character name cannot be empty"):
            Character(name="", image_path="test.png")
        
        with pytest.raises(ValueError, match="Character name cannot be empty"):
            Character(name="   ", image_path="test.png")
    
    def test_empty_image_path_validation(self):
        """Test validation of empty image path."""
        with pytest.raises(ValueError, match="Character image path cannot be empty"):
            Character(name="Test", image_path="")
        
        with pytest.raises(ValueError, match="Character image path cannot be empty"):
            Character(name="Test", image_path="   ")


class TestRankingEntry:
    """Test RankingEntry class."""
    
    def test_ranking_entry_creation(self):
        """Test creating ranking entry."""
        entry = RankingEntry(
            place=1,
            character_name="Test Character",
            rating=1500.0,
            wins=10,
            comparisons=15
        )
        assert entry.place == 1
        assert entry.character_name == "Test Character"
        assert entry.rating == 1500.0
        assert entry.wins == 10
        assert entry.comparisons == 15
    
    def test_ranking_entry_str(self):
        """Test string representation of ranking entry."""
        entry = RankingEntry(
            place=1,
            character_name="Test Character", 
            rating=1500.0,
            wins=10,
            comparisons=15
        )
        expected = "1. Test Character — 1500 очков (10 побед из 15)"
        assert str(entry) == expected


class TestSimpleTransitiveSession:
    """Test SimpleTransitiveSession class."""
    
    def test_session_creation(self):
        """Test creating new session."""
        session = SimpleTransitiveSession(characters_count=5, max_comparisons=10)
        assert session.characters_count == 5
        assert session.max_comparisons == 10
        assert session.comparisons_made == 0
        assert not session.is_completed
    
    def test_session_with_invalid_characters_count(self):
        """Test session creation with invalid characters count."""
        # Testing through the constructor - should handle gracefully
        session = SimpleTransitiveSession(characters_count=1, max_comparisons=10)
        # The session should still be created but may not function properly
        assert session.characters_count == 1
    
    def test_get_current_pair(self):
        """Test getting current comparison pair."""
        session = SimpleTransitiveSession(characters_count=3, max_comparisons=5)
        pair = session.get_current_pair()
        
        if pair:  # May be None if no pairs available
            assert len(pair) == 2
            assert 0 <= pair[0] < 3
            assert 0 <= pair[1] < 3
            assert pair[0] != pair[1]
    
    def test_record_choice_valid(self):
        """Test recording valid choice."""
        session = SimpleTransitiveSession(characters_count=3, max_comparisons=5)
        pair = (0, 1)
        winner = 0
        
        initial_comparisons = session.comparisons_made
        session.record_choice(pair, winner)
        
        assert session.comparisons_made == initial_comparisons + 1
        assert pair in session.choice_history or (pair[1], pair[0]) in session.choice_history
    
    def test_record_choice_invalid_winner(self):
        """Test recording choice with invalid winner."""
        session = SimpleTransitiveSession(characters_count=3, max_comparisons=5)
        pair = (0, 1)
        invalid_winner = 2  # Not in pair
        
        with pytest.raises(ValueError, match="winner must be one of pair"):
            session.record_choice(pair, invalid_winner)
    
    def test_record_choice_none_pair(self):
        """Test recording choice with None pair."""
        session = SimpleTransitiveSession(characters_count=3, max_comparisons=5)
        
        # Should handle gracefully without raising exception
        session.record_choice(None, 0)
        assert session.comparisons_made == 0
    
    def test_session_completion(self):
        """Test session completion conditions."""
        session = SimpleTransitiveSession(characters_count=3, max_comparisons=1)
        
        # Complete one comparison
        pair = (0, 1)
        session.record_choice(pair, 0)
        
        # Should be completed due to max_comparisons limit
        assert session.is_completed
    
    def test_calculate_scores(self):
        """Test score calculation."""
        session = SimpleTransitiveSession(characters_count=3, max_comparisons=5)
        
        # Add some comparisons
        session.record_choice((0, 1), 0)  # 0 beats 1
        session.record_choice((1, 2), 1)  # 1 beats 2
        
        scores = session.calculate_scores(3)
        
        assert len(scores) == 3
        assert all(isinstance(score, tuple) and len(score) == 2 for score in scores)
        assert all(isinstance(score[0], (int, float)) and isinstance(score[1], int) for score in scores)
    
    def test_undo_last_choice(self):
        """Test undoing last choice."""
        session = SimpleTransitiveSession(characters_count=3, max_comparisons=5)
        
        # Record a choice
        pair = (0, 1)
        session.record_choice(pair, 0)
        initial_comparisons = session.comparisons_made
        
        # Undo the choice
        success = session.undo_last_choice()
        
        assert success is True
        assert session.comparisons_made == initial_comparisons - 1
    
    def test_undo_empty_history(self):
        """Test undoing when no choices made."""
        session = SimpleTransitiveSession(characters_count=3, max_comparisons=5)
        
        success = session.undo_last_choice()
        assert success is False
    
    def test_learned_preferences_validation(self):
        """Test learned preferences validation."""
        session = SimpleTransitiveSession(characters_count=3, max_comparisons=5)
        
        # Test valid preference retrieval
        pref = session.get_learned_preference(0, 1)
        assert 0.0 <= pref <= 1.0
        
        # Test invalid indices
        pref_invalid = session.get_learned_preference(5, 1)  # Out of range
        assert pref_invalid == 0.5  # Should return neutral
        
        pref_same = session.get_learned_preference(1, 1)  # Same character
        assert pref_same == 0.5  # Should return neutral