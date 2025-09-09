"""Tests for configuration module."""

import pytest
import os
from config import BotConfig


class TestBotConfig:
    """Test BotConfig class."""
    
    def test_valid_config_creation(self):
        """Test creating valid configuration."""
        config = BotConfig(
            api_token="valid_token_123456789",
            max_comparisons=50,
            flood_delay=0.5
        )
        assert config.api_token == "valid_token_123456789"
        assert config.max_comparisons == 50
        assert config.flood_delay == 0.5
    
    def test_invalid_api_token(self):
        """Test invalid API token validation."""
        with pytest.raises(ValueError, match="Некорректный API токен"):
            BotConfig(api_token="short")
        
        with pytest.raises(ValueError, match="Некорректный API токен"):
            BotConfig(api_token="")
    
    def test_invalid_max_comparisons(self):
        """Test invalid max_comparisons validation."""
        with pytest.raises(ValueError, match="max_comparisons должно быть больше 0"):
            BotConfig(api_token="valid_token_123456789", max_comparisons=0)
        
        with pytest.raises(ValueError, match="max_comparisons должно быть больше 0"):
            BotConfig(api_token="valid_token_123456789", max_comparisons=-1)
    
    def test_invalid_flood_delay(self):
        """Test invalid flood_delay validation."""
        with pytest.raises(ValueError, match="flood_delay должно быть больше 0.1 секунды"):
            BotConfig(api_token="valid_token_123456789", flood_delay=0.05)
    
    def test_from_env_success(self, setup_test_env):
        """Test successful config loading from environment."""
        config = BotConfig.from_env()
        assert config.api_token == "test_token_123456789"
        assert config.characters_dir == "Персонажи"
        assert config.log_level == "INFO"
    
    def test_from_env_missing_token(self):
        """Test error when BOT_API_TOKEN is missing."""
        if "BOT_API_TOKEN" in os.environ:
            del os.environ["BOT_API_TOKEN"]
        
        with pytest.raises(ValueError, match="BOT_API_TOKEN environment variable is required"):
            BotConfig.from_env()
    
    def test_from_env_invalid_values(self):
        """Test error handling for invalid environment values."""
        os.environ["BOT_API_TOKEN"] = "test_token_123456789"
        os.environ["MAX_COMPARISONS"] = "invalid"
        
        with pytest.raises(ValueError, match="Invalid environment variable value"):
            BotConfig.from_env()
        
        # Cleanup
        del os.environ["MAX_COMPARISONS"]