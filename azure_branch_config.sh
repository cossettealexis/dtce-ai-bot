#!/bin/bash
# Azure Git Configuration Script
# This shows the commands you can run in Azure's Kudu console or SSH

# Navigate to repository
cd /home/site/repository

# Set the default branch to fresh-start
git symbolic-ref HEAD refs/heads/fresh-start

# Pull the latest changes from fresh-start branch
git pull origin fresh-start

echo "Azure deployment now configured to use fresh-start branch"
