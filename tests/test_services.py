"""Tests for services module."""

import pytest
import tempfile
import os
import json
from unittest.mock import Mock, patch, mock_open
from services import CharacterService, SessionService
from models import Character


class TestCharacterService:
    """Test CharacterService class."""
    
    def test_init_with_valid_directory(self, temp_dir):
        """Test initialization with valid directory."""
        service = CharacterService(temp_dir)
        assert service.characters_dir == temp_dir
    
    def test_validate_characters_directory_exists(self, temp_dir):
        """Test directory validation when directory exists."""
        service = CharacterService(temp_dir)
        assert service.validate_characters_directory() is True
    
    def test_validate_characters_directory_missing(self):
        """Test directory validation when directory missing."""
        service = CharacterService("nonexistent_directory")
        assert service.validate_characters_directory() is False
    
    def test_load_characters_from_files(self, temp_dir):
        """Test loading characters from PNG files."""
        # Create test PNG files
        test_files = ["char1.png", "char2.png", "char3.png"]
        for filename in test_files:
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, 'w') as f:
                f.write("fake png content")
        
        service = CharacterService(temp_dir)
        characters = service.characters
        
        assert len(characters) == 3
        assert all(isinstance(char, Character) for char in characters)
        character_names = [char.name for char in characters]
        assert "char1" in character_names
        assert "char2" in character_names
        assert "char3" in character_names
    
    def test_load_characters_fallback_to_default(self, temp_dir):
        """Test fallback to default character list when no files."""
        service = CharacterService(temp_dir)
        characters = service.characters
        
        # Should fallback to CHARACTER_NAMES from config
        assert len(characters) > 0
        # Characters should use default names from config
        from config import CHARACTER_NAMES
        expected_names = CHARACTER_NAMES
        actual_names = [char.name for char in characters]
        assert actual_names == expected_names
    
    def test_get_character_by_index_valid(self, temp_dir):
        """Test getting character by valid index."""
        service = CharacterService(temp_dir)
        char = service.get_character_by_index(0)
        assert char is not None
        assert isinstance(char, Character)
    
    def test_get_character_by_index_invalid(self, temp_dir):
        """Test getting character by invalid index."""
        service = CharacterService(temp_dir)
        char = service.get_character_by_index(-1)
        assert char is None
        
        char = service.get_character_by_index(1000)
        assert char is None
    
    def test_get_index_by_name(self, temp_dir):
        """Test getting index by character name."""
        # Create test PNG file
        test_file = os.path.join(temp_dir, "testchar.png")
        with open(test_file, 'w') as f:
            f.write("fake png content")
        
        service = CharacterService(temp_dir)
        index = service.get_index_by_name("testchar")
        assert index == 0
        
        # Test non-existent character
        index = service.get_index_by_name("nonexistent")
        assert index is None
    
    def test_get_characters_count(self, temp_dir):
        """Test getting characters count."""
        service = CharacterService(temp_dir)
        count = service.get_characters_count()
        assert isinstance(count, int)
        assert count > 0
    
    def test_reload_characters(self, temp_dir):
        """Test reloading characters."""
        service = CharacterService(temp_dir)
        initial_count = len(service.characters)
        
        # Add a new file
        new_file = os.path.join(temp_dir, "newchar.png")
        with open(new_file, 'w') as f:
            f.write("fake png content")
        
        reloaded_count = service.reload_characters()
        assert reloaded_count == 1  # Should have 1 character from the new file
        assert len(service.characters) == 1
    
    def test_validate_character_files(self, temp_dir):
        """Test validating character files."""
        # Create a PNG file that exists
        existing_file = os.path.join(temp_dir, "existing.png")
        with open(existing_file, 'w') as f:
            f.write("fake png content")
        
        service = CharacterService(temp_dir)
        missing_files = service.validate_character_files()
        
        # Should have missing files for default characters (except the one we created if it matches)
        assert isinstance(missing_files, list)


class TestSessionService:
    """Test SessionService class."""
    
    def test_init(self, mock_character_service):
        """Test SessionService initialization."""
        service = SessionService(mock_character_service)
        assert service.character_service == mock_character_service
        assert isinstance(service._sessions, dict)
        assert isinstance(service._global_stats, dict)
    
    @patch('builtins.open', mock_open(read_data='{"123": ["char1", "char2", "char3"]}'))
    @patch('os.path.exists', return_value=True)
    def test_load_global_stats_success(self, mock_exists, mock_character_service):
        """Test successful loading of global stats."""
        service = SessionService(mock_character_service)
        stats = service._load_global_stats()
        
        assert isinstance(stats, dict)
        assert 123 in stats  # Key should be converted to int
        assert stats[123] == ["char1", "char2", "char3"]
    
    @patch('builtins.open', mock_open(read_data='invalid json'))
    @patch('os.path.exists', return_value=True)
    def test_load_global_stats_corrupted_file(self, mock_exists, mock_character_service):
        """Test handling of corrupted global stats file."""
        with patch('shutil.copy2'):  # Mock the backup operation
            service = SessionService(mock_character_service)
            stats = service._load_global_stats()
            
            assert stats == {}  # Should return empty dict for corrupted file
    
    @patch('os.path.exists', return_value=False)
    def test_load_global_stats_no_file(self, mock_exists, mock_character_service):
        """Test loading when no global stats file exists."""
        service = SessionService(mock_character_service)
        stats = service._load_global_stats()
        assert stats == {}
    
    def test_create_session_valid(self, mock_character_service):
        """Test creating valid session."""
        service = SessionService(mock_character_service)
        
        with patch.object(service, '_save_sessions'):
            session = service.create_session(user_id=123, characters_count=5, max_comparisons=10)
        
        assert session is not None
        assert 123 in service._sessions
        assert service._sessions[123] == session
    
    def test_create_session_invalid_user_id(self, mock_character_service):
        """Test creating session with invalid user ID."""
        service = SessionService(mock_character_service)
        
        session = service.create_session(user_id=-1, characters_count=5)
        assert session is None
        
        session = service.create_session(user_id="invalid", characters_count=5)
        assert session is None
    
    def test_create_session_invalid_characters_count(self, mock_character_service):
        """Test creating session with invalid characters count."""
        service = SessionService(mock_character_service)
        
        session = service.create_session(user_id=123, characters_count=1)
        assert session is None
        
        session = service.create_session(user_id=123, characters_count=-5)
        assert session is None
    
    def test_create_session_invalid_max_comparisons(self, mock_character_service):
        """Test creating session with invalid max comparisons."""
        service = SessionService(mock_character_service)
        
        session = service.create_session(user_id=123, characters_count=5, max_comparisons=0)
        assert session is None
        
        session = service.create_session(user_id=123, characters_count=5, max_comparisons=-1)
        assert session is None
    
    def test_update_user_ranking_valid(self, mock_character_service):
        """Test updating user ranking with valid data."""
        service = SessionService(mock_character_service)
        
        with patch.object(service, '_save_global_stats'), \
             patch.object(service, '_normalize_full_ranking', return_value=["char1", "char2"]):
            service.update_user_ranking(123, ["char1", "char2"])
        
        assert 123 in service._global_stats
        assert service._global_stats[123] == ["char1", "char2"]
    
    def test_update_user_ranking_invalid_user_id(self, mock_character_service):
        """Test updating ranking with invalid user ID."""
        service = SessionService(mock_character_service)
        
        # Should handle gracefully without raising exception
        service.update_user_ranking(-1, ["char1", "char2"])
        service.update_user_ranking("invalid", ["char1", "char2"])
        
        # No entries should be added
        assert -1 not in service._global_stats
        assert "invalid" not in service._global_stats
    
    def test_update_user_ranking_invalid_data(self, mock_character_service):
        """Test updating ranking with invalid ranking data."""
        service = SessionService(mock_character_service)
        
        # Should handle gracefully without raising exception
        service.update_user_ranking(123, "not a list")
        service.update_user_ranking(123, None)
        
        # No entries should be added
        assert 123 not in service._global_stats
    
    def test_get_session_exists(self, mock_character_service):
        """Test getting existing session."""
        service = SessionService(mock_character_service)
        
        # Create a mock session
        mock_session = Mock()
        service._sessions[123] = mock_session
        
        session = service.get_session(123)
        assert session == mock_session
    
    def test_get_session_not_exists(self, mock_character_service):
        """Test getting non-existent session."""
        service = SessionService(mock_character_service)
        session = service.get_session(999)
        assert session is None
    
    def test_remove_session_exists(self, mock_character_service):
        """Test removing existing session."""
        service = SessionService(mock_character_service)
        
        # Add a session
        mock_session = Mock()
        service._sessions[123] = mock_session
        
        with patch.object(service, '_save_sessions'):
            service.remove_session(123)
        
        assert 123 not in service._sessions
    
    def test_remove_session_not_exists(self, mock_character_service):
        """Test removing non-existent session."""
        service = SessionService(mock_character_service)
        
        # Should handle gracefully without raising exception
        with patch.object(service, '_save_sessions'):
            service.remove_session(999)
    
    def test_normalize_full_ranking(self, mock_character_service):
        """Test normalizing full ranking."""
        # Setup mock character service
        mock_characters = [Mock(name=f"char{i}") for i in range(3)]
        mock_character_service.characters = mock_characters
        
        service = SessionService(mock_character_service)
        
        # Test partial ranking
        partial_ranking = ["char0", "char1"]
        normalized = service._normalize_full_ranking(partial_ranking)
        
        assert len(normalized) == 3  # Should include all characters
        assert "char0" in normalized
        assert "char1" in normalized
        assert "char2" in normalized
    
    def test_normalize_full_ranking_no_service(self):
        """Test normalizing ranking without character service."""
        service = SessionService(None)
        
        ranking = ["char1", "char2"] * 30  # Long list
        normalized = service._normalize_full_ranking(ranking)
        
        assert len(normalized) <= 50  # Should be limited to 50