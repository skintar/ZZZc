"""Shared test fixtures and utilities."""

import pytest
import tempfile
import os
from unittest.mock import Mock
from pathlib import Path

@pytest.fixture
def temp_dir():
    """Provides a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def mock_character_service():
    """Mock CharacterService for testing."""
    from services import CharacterService
    service = Mock(spec=CharacterService)
    service.get_characters_count.return_value = 5
    return service

@pytest.fixture
def sample_characters():
    """Sample character data for testing."""
    return [
        {"name": "Test Character 1", "image_path": "test1.png"},
        {"name": "Test Character 2", "image_path": "test2.png"},
        {"name": "Test Character 3", "image_path": "test3.png"},
        {"name": "Test Character 4", "image_path": "test4.png"},
        {"name": "Test Character 5", "image_path": "test5.png"},
    ]

@pytest.fixture
def test_config():
    """Test configuration."""
    from config import BotConfig
    return BotConfig(
        api_token="test_token_123456789",
        characters_dir="test_characters",
        log_level="DEBUG",
        max_comparisons=10,
        flood_delay=0.1,
        backup_interval=60,
        max_backups=3
    )

@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment variables."""
    os.environ["BOT_API_TOKEN"] = "test_token_123456789"
    yield
    # Cleanup after test
    if "BOT_API_TOKEN" in os.environ:
        del os.environ["BOT_API_TOKEN"]