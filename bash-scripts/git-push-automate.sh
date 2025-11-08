#!/bin/bash

# Git Push Script

# Set the repository path
repository_path="/path/to/repository"

# Set the commit message
commit_message="Automated commit"

# Change to the repository directory
cd "$repository_path" || exit

# Add all modified and new files
git add -A

# Commit changes with the specified message
git commit -m "$commit_message"

# Push changes to the default branch (e.g., "main" or "master")
git push origin main
