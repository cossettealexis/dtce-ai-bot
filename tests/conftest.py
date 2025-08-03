"""
Pytest configuration and fixtures.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from dtce_ai_bot.config.settings import get_settings


@pytest.fixture
def settings():
    """Get test settings."""
    return get_settings()


@pytest.fixture
def mock_azure_search_client():
    """Mock Azure Search client."""
    mock = AsyncMock()
    mock.search_documents = AsyncMock()
    return mock


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    mock = AsyncMock()
    mock.generate_response = AsyncMock()
    return mock


@pytest.fixture
def mock_sharepoint_client():
    """Mock SharePoint client."""
    mock = AsyncMock()
    mock.list_files = AsyncMock()
    return mock


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
