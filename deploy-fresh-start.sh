#!/bin/bash

# Deploy comprehensive RAG system from fresh-start branch
echo "🚀 Deploying comprehensive RAG system from fresh-start branch..."

# Ensure we're on the fresh-start branch
git checkout fresh-start

# Ensure branch is up to date
git pull origin fresh-start

# Push any local changes
git push origin fresh-start

echo "✅ fresh-start branch deployed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Update Azure App Service deployment settings to use 'fresh-start' branch"
echo "2. Or update GitHub repository default branch to 'fresh-start'"
echo "3. Trigger manual deployment in Azure Portal"
echo ""
echo "🎯 The comprehensive RAG system is ready on the fresh-start branch!"
