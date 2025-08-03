"""
Unit tests for DTCE Teams Bot.
"""

import pytest
from unittest.mock import AsyncMock

from dtce_ai_bot.bot.teams_bot import DTCETeamsBot


class TestDTCETeamsBot:
    """Test cases for DTCETeamsBot."""
    
    @pytest.fixture
    def bot(self, mock_azure_search_client, mock_openai_client):
        """Create bot instance for testing."""
        return DTCETeamsBot(
            conversation_state=AsyncMock(),
            user_state=AsyncMock(),
            search_client=mock_azure_search_client,
            openai_client=mock_openai_client
        )
    
    def test_bot_initialization(self, bot):
        """Test bot initializes correctly."""
        assert bot is not None
        assert hasattr(bot, 'search_client')
        assert hasattr(bot, 'openai_client')
    
    # TODO: Add more specific tests
