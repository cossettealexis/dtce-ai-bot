#!/bin/bash
# GitHub Setup Script for DTCE AI Teams Bot

echo "🚀 Setting up DTCE AI Teams Bot on GitHub..."
echo "============================================="

# Check if remote already exists
if git remote get-url origin >/dev/null 2>&1; then
    echo "✅ Git remote 'origin' already configured"
    git remote -v
else
    echo "❌ No remote 'origin' found. Please add your GitHub repository URL:"
    echo "   git remote add origin https://github.com/YOUR_USERNAME/dtce-ai-bot.git"
    echo ""
    echo "Replace YOUR_USERNAME with your actual GitHub username"
fi

echo ""
echo "📋 Next Steps:"
echo "1. Create repository on GitHub.com:"
echo "   - Name: dtce-ai-bot"
echo "   - Description: Internal AI assistant Teams bot for DTCE engineering files"
echo "   - Visibility: Private (recommended)"
echo "   - Don't initialize with README, .gitignore, or license"
echo ""
echo "2. Add remote and push:"
echo "   git remote add origin https://github.com/YOUR_USERNAME/dtce-ai-bot.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "3. Configure repository settings:"
echo "   - Enable branch protection for main"
echo "   - Add team members as collaborators"
echo "   - Set up GitHub secrets for deployment"
echo ""
echo "✅ Project is ready for GitHub!"
echo "📁 Total files committed: $(git ls-files | wc -l)"
echo "📊 Latest commit: $(git log --oneline -1)"
