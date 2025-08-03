# 🚀 GitHub Setup Guide for DTCE AI Teams Bot

## Quick Setup Commands

```bash
# 1. Initialize Git repository
git init

# 2. Add all files
git add .

# 3. Create initial commit
git commit -m "Initial commit: DTCE AI Teams Bot with restructured architecture"

# 4. Add GitHub remote (replace with your actual GitHub repo URL)
git remote add origin https://github.com/YOUR_USERNAME/dtce-ai-bot.git

# 5. Push to GitHub
git branch -M main
git push -u origin main
```

## Detailed Steps

### Step 1: Create GitHub Repository

1. Go to [GitHub.com](https://github.com)
2. Click the "+" icon → "New repository"
3. Repository settings:
   - **Name**: `dtce-ai-bot`
   - **Description**: "Internal AI assistant Teams bot for DTCE engineering files"
   - **Visibility**: Private (recommended for internal tools)
   - **Don't initialize** with README, .gitignore, or license (we already have these)

### Step 2: Initialize Local Git Repository

```bash
# Initialize Git in your project directory
git init

# Configure Git (if not already done globally)
git config user.name "Your Name"
git config user.email "your.email@dtce.com"
```

### Step 3: Prepare Files for Commit

```bash
# Check what files will be committed
git status

# Add all files to staging
git add .

# Check what's staged
git diff --cached --name-only
```

### Step 4: Create Initial Commit

```bash
git commit -m "feat: initial DTCE AI Teams Bot implementation

- Restructured project following Python best practices
- Microsoft Teams bot with adaptive cards
- Azure Cognitive Search integration
- OpenAI-powered responses
- SharePoint/Graph API integration
- Comprehensive testing framework
- Modern packaging with pyproject.toml
- Docker deployment configuration"
```

### Step 5: Connect to GitHub

```bash
# Add remote origin (replace with your actual repo URL)
git remote add origin https://github.com/YOUR_USERNAME/dtce-ai-bot.git

# Set main branch and push
git branch -M main
git push -u origin main
```

## Repository Configuration

### Branch Protection (Recommended)

1. Go to repository Settings → Branches
2. Add rule for `main` branch:
   - ✅ Require pull request reviews
   - ✅ Require status checks to pass
   - ✅ Require branches to be up to date

### GitHub Actions (Optional)

Create `.github/workflows/ci.yml` for automated testing:

```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, '3.10', '3.11']

    steps:
    - uses: actions/checkout@v3
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v3
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-dev.txt
    
    - name: Lint with flake8
      run: |
        flake8 dtce_ai_bot/ tests/
    
    - name: Format check with black
      run: |
        black --check dtce_ai_bot/ tests/
    
    - name: Type check with mypy
      run: |
        mypy dtce_ai_bot/
    
    - name: Test with pytest
      run: |
        pytest tests/ -v --cov=dtce_ai_bot
```

### Environment Variables Setup

1. Go to repository Settings → Secrets and variables → Actions
2. Add repository secrets for deployment:
   - `AZURE_STORAGE_CONNECTION_STRING`
   - `AZURE_SEARCH_SERVICE_NAME`
   - `AZURE_SEARCH_ADMIN_KEY`
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_API_KEY`
   - `MICROSOFT_APP_ID`
   - `MICROSOFT_APP_PASSWORD`
   - etc.

## Repository Structure for GitHub

Your repository will have this structure:

```
dtce-ai-bot/
├── 📄 README.md                   # Project documentation
├── 📄 LICENSE                     # License file
├── 📄 .gitignore                  # Git ignore rules
├── 📄 .env.example                # Environment template
├── 📄 requirements.txt            # Dependencies
├── 📄 requirements-dev.txt        # Dev dependencies
├── 📄 pyproject.toml              # Modern Python config
├── 📄 setup.py                    # Package setup
├── 📄 Makefile                    # Development commands
├── 📄 app.py                      # Application entry point
├── 📁 .github/                    # GitHub configuration
│   └── workflows/                 # GitHub Actions
├── 📁 dtce_ai_bot/                # Main package
├── 📁 tests/                      # Test suite
├── 📁 docs/                       # Documentation
├── 📁 deployment/                 # Deployment configs
├── 📁 scripts/                    # Utility scripts
└── 📁 teams-app/                  # Teams app package
```

## GitHub Features to Use

### Issues and Project Management
- Create issue templates for bugs and features
- Use GitHub Projects for sprint planning
- Set up labels for issue categorization

### Pull Request Template
Create `.github/pull_request_template.md`:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings
```

### GitHub Pages (Optional)
Set up GitHub Pages for documentation hosting.

## Next Steps After GitHub Setup

1. **Team Access**: Add team members as collaborators
2. **Branch Strategy**: Set up develop/feature branch workflow  
3. **CI/CD**: Configure automated testing and deployment
4. **Documentation**: Keep README and docs updated
5. **Releases**: Use GitHub releases for version management

## Security Considerations

- ✅ Never commit secrets or API keys
- ✅ Use `.env.example` for environment templates
- ✅ Set repository to private for internal tools
- ✅ Enable GitHub security features (Dependabot, code scanning)
- ✅ Use GitHub secrets for CI/CD credentials
