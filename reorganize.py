#!/usr/bin/env python3
"""
Project Reorganization Script

Reorganizes the DTCE AI Bot project structure to follow Python best practices
and modern software engineering principles.
"""

import os
import shutil
from pathlib import Path
import subprocess


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"🔧 {title}")
    print('='*60)


def reorganize_source_files():
    """Move and reorganize source files to proper structure."""
    print_header("REORGANIZING SOURCE FILES")
    
    # Source files mapping: old_path -> new_path
    file_moves = {
        # Move existing src files to proper locations
        "src/models.py": "dtce_ai_bot/models/legacy_models.py",
        "src/azure_blob_client.py": "dtce_ai_bot/integrations/azure/blob_client.py",
        "src/azure_search_client.py": "dtce_ai_bot/integrations/azure/search_client.py", 
        "src/azure_openai_client.py": "dtce_ai_bot/integrations/azure/openai_client.py",
        "src/sharepoint_client.py": "dtce_ai_bot/integrations/microsoft/sharepoint_client.py",
        "src/document_processor.py": "dtce_ai_bot/services/document_processor.py",
        
        # Move config
        "config.py": "dtce_ai_bot/config/legacy_config.py",
        
        # Move tests
        "test_azure.py": "tests/integration/test_azure_services.py",
        "test_sharepoint.py": "tests/integration/test_sharepoint.py",
        
        # Move deployment and scripts
        "deploy.py": "deployment/deploy.py",
        "setup_teams.py": "scripts/setup_teams.py",
        "start.sh": "scripts/start.sh",
        
        # Move main to legacy
        "main.py": "scripts/legacy_main.py",
    }
    
    # Create directories and move files
    for old_path, new_path in file_moves.items():
        old_file = Path(old_path)
        new_file = Path(new_path)
        
        if old_file.exists():
            # Create parent directory if it doesn't exist
            new_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Move file
            print(f"📁 Moving {old_path} → {new_path}")
            shutil.move(str(old_file), str(new_file))
        else:
            print(f"⚠️  File not found: {old_path}")
    
    # Clean up empty src directory
    src_dir = Path("src")
    if src_dir.exists() and not any(src_dir.iterdir()):
        print(f"🗑️  Removing empty directory: src/")
        src_dir.rmdir()


def create_test_structure():
    """Create proper test directory structure."""
    print_header("CREATING TEST STRUCTURE")
    
    test_dirs = [
        "tests/unit/bot",
        "tests/unit/services", 
        "tests/unit/integrations/azure",
        "tests/unit/integrations/microsoft",
        "tests/unit/models",
        "tests/integration/azure",
        "tests/integration/microsoft",
        "tests/e2e",
        "tests/fixtures"
    ]
    
    for test_dir in test_dirs:
        Path(test_dir).mkdir(parents=True, exist_ok=True)
        print(f"📁 Created: {test_dir}/")
        
        # Create __init__.py files
        init_file = Path(test_dir) / "__init__.py"
        if not init_file.exists():
            init_file.write_text("# Test module\n")


def create_test_files():
    """Create basic test files."""
    print_header("CREATING TEST FILES")
    
    # conftest.py for pytest configuration
    conftest_content = '''"""
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
'''
    
    (Path("tests") / "conftest.py").write_text(conftest_content)
    print("✅ Created tests/conftest.py")
    
    # Example unit test
    unit_test_content = '''"""
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
'''
    
    (Path("tests/unit/bot") / "test_teams_bot.py").write_text(unit_test_content)
    print("✅ Created tests/unit/bot/test_teams_bot.py")


def create_documentation_structure():
    """Create documentation directory structure."""
    print_header("CREATING DOCUMENTATION STRUCTURE")
    
    docs_dirs = [
        "docs/api",
        "docs/deployment",
        "docs/development", 
        "docs/architecture",
        "docs/images"
    ]
    
    for docs_dir in docs_dirs:
        Path(docs_dir).mkdir(parents=True, exist_ok=True)
        print(f"📁 Created: {docs_dir}/")


def create_development_files():
    """Create development configuration files."""
    print_header("CREATING DEVELOPMENT FILES")
    
    # Makefile for common development tasks
    makefile_content = '''# DTCE AI Bot Development Makefile

.PHONY: help install install-dev test lint format clean run docker-build docker-run

help: ## Show this help message
\t@echo 'Usage: make [target]'
\t@echo ''
\t@echo 'Targets:'
\t@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \\033[36m%-15s\\033[0m %s\\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install production dependencies
\tpip install -e .

install-dev: ## Install development dependencies
\tpip install -e ".[dev]"
\tpre-commit install

test: ## Run tests
\tpytest tests/ -v

test-cov: ## Run tests with coverage
\tpytest tests/ -v --cov=dtce_ai_bot --cov-report=html --cov-report=term

lint: ## Run linting
\tflake8 dtce_ai_bot/ tests/
\tmypy dtce_ai_bot/

format: ## Format code
\tblack dtce_ai_bot/ tests/
\tisort dtce_ai_bot/ tests/

format-check: ## Check code formatting
\tblack --check dtce_ai_bot/ tests/
\tisort --check-only dtce_ai_bot/ tests/

clean: ## Clean build artifacts
\trm -rf build/ dist/ *.egg-info/
\tfind . -type d -name __pycache__ -delete
\tfind . -type f -name "*.pyc" -delete

run: ## Run the application
\tpython app.py

run-dev: ## Run in development mode
\tuvicorn dtce_ai_bot.core.app:create_app --reload --host 0.0.0.0 --port 8000

docker-build: ## Build Docker image
\tdocker build -t dtce-ai-bot .

docker-run: ## Run Docker container
\tdocker run -p 8000:8000 --env-file .env dtce-ai-bot

deploy-prep: ## Prepare for deployment
\tpython deployment/deploy.py
'''
    
    Path("Makefile").write_text(makefile_content)
    print("✅ Created Makefile")
    
    # Pre-commit configuration
    precommit_content = '''repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: debug-statements

  - repo: https://github.com/psf/black
    rev: 23.9.1
    hooks:
      - id: black
        language_version: python3

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
        additional_dependencies: [flake8-docstrings]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.6.1
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
'''
    
    Path(".pre-commit-config.yaml").write_text(precommit_content)
    print("✅ Created .pre-commit-config.yaml")


def update_gitignore():
    """Update .gitignore with comprehensive rules."""
    print_header("UPDATING .GITIGNORE")
    
    gitignore_additions = '''
# Additional Python ignores
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
cover/

# Documentation
docs/_build/

# Jupyter Notebook
.ipynb_checkpoints

# IPython
profile_default/
ipython_config.py

# Environments
.env.local
.env.development
.env.test
.env.production

# Azure
.azure/

# Logs
logs/
*.log

# Deployment
deployment.zip
teams-app/*.zip

# OS
.DS_Store
Thumbs.db

# Local development
local_*
temp/
tmp/
'''
    
    with open(".gitignore", "a") as f:
        f.write(gitignore_additions)
    
    print("✅ Updated .gitignore")


def create_new_requirements():
    """Create updated requirements.txt."""
    print_header("CREATING REQUIREMENTS FILES")
    
    # Basic requirements.txt
    requirements_content = '''# DTCE AI Bot Requirements
# Generated from pyproject.toml

fastapi>=0.104.1
uvicorn>=0.24.0
python-multipart>=0.0.6
botbuilder-core>=4.15.0
botbuilder-schema>=4.15.0
botbuilder-integration-aiohttp>=4.15.0
aiohttp>=3.8.5
aiohttp-cors>=0.7.0
msal>=1.25.0
requests>=2.31.0
azure-storage-blob>=12.19.0
azure-search-documents>=11.4.0
azure-cognitiveservices-language-textanalytics>=5.3.0
openai>=1.3.7
python-docx>=1.1.0
PyPDF2>=3.0.1
openpyxl>=3.1.2
python-dotenv>=1.0.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
structlog>=23.2.0
rich>=13.7.0
'''
    
    Path("requirements.txt").write_text(requirements_content)
    print("✅ Created requirements.txt")
    
    # Development requirements
    dev_requirements_content = '''# Development Requirements
# Install with: pip install -r requirements-dev.txt

-r requirements.txt

pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
black>=23.9.0
isort>=5.12.0
flake8>=6.1.0
mypy>=1.6.0
pre-commit>=3.5.0
'''
    
    Path("requirements-dev.txt").write_text(dev_requirements_content)
    print("✅ Created requirements-dev.txt")


def main():
    """Main reorganization function."""
    print("🏗️  DTCE AI Bot Project Reorganization")
    print("="*50)
    print("Reorganizing project structure to follow Python best practices...")
    
    # Execute reorganization steps
    reorganize_source_files()
    create_test_structure()
    create_test_files()
    create_documentation_structure() 
    create_development_files()
    update_gitignore()
    create_new_requirements()
    
    print_header("REORGANIZATION COMPLETED")
    print("""
✅ Project successfully reorganized!

NEW STRUCTURE:
├── dtce_ai_bot/           # Main package
│   ├── core/             # Application core
│   ├── bot/              # Teams bot implementation  
│   ├── services/         # Business logic
│   ├── integrations/     # External service clients
│   ├── models/           # Data models
│   ├── config/           # Configuration
│   └── utils/            # Utilities
├── tests/                # Test suite
├── docs/                 # Documentation
├── deployment/           # Deployment configs
├── scripts/              # Utility scripts
├── pyproject.toml        # Modern Python config
├── setup.py             # Package setup
├── Makefile             # Development commands
└── app.py               # Application entry point

NEXT STEPS:
1. Install in development mode: make install-dev
2. Run tests: make test
3. Format code: make format
4. Run application: make run
5. Update imports in moved files to match new structure

The project now follows modern Python packaging standards!
""")


if __name__ == "__main__":
    main()
