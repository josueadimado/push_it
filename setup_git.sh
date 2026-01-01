#!/bin/bash

# Quick Git Setup Script for Push-it
# Run this script to initialize git and prepare for GitHub push

echo "🚀 Setting up Git repository for Push-it..."

# Remove any existing lock files
rm -f .git/index.lock

# Initialize git (if not already done)
if [ ! -d ".git" ]; then
    echo "📦 Initializing git repository..."
    git init
    git branch -M main
fi

# Add all files
echo "📝 Adding files to git..."
git add .

# Create initial commit
echo "💾 Creating initial commit..."
git commit -m "Initial commit: Push-it influencer marketing platform

- Complete Django influencer marketing platform
- Brand and influencer dashboards
- Campaign management system
- Wallet and payment integration (Paystack)
- Multi-currency support
- Platform verification system
- Notification system
- Payment methods (Bank Transfer, Mobile Money)"

echo ""
echo "✅ Git repository initialized and committed!"
echo ""
echo "📋 Next steps:"
echo "1. Create a repository on GitHub: https://github.com/new"
echo "2. Run these commands (replace YOUR_USERNAME):"
echo ""
echo "   git remote add origin https://github.com/YOUR_USERNAME/push-it.git"
echo "   git push -u origin main"
echo ""
echo "📖 For detailed deployment instructions, see DEPLOYMENT_GUIDE.md"
