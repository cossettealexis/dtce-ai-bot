#!/usr/bin/env python3
"""
Clean up project structure by organizing scattered files into logical directories.
"""

import os
import shutil
from pathlib import Path


def clean_project_structure():
    """Reorganize files into a cleaner structure."""
    
    print("🧹 Cleaning up project structure...")
    print("="*50)
    
    # Create clean directory structure
    directories = {
        "docs": ["GITHUB_SETUP.md", "RESTRUCTURE_COMPLETE.md", "instructions.txt"],
        "tools": ["reorganize.py", "connect-to-github.sh", "github-setup.sh"],
        "config": [".env.example", ".pre-commit-config.yaml"],
    }
    
    # Move files to appropriate directories
    for directory, files in directories.items():
        os.makedirs(directory, exist_ok=True)
        
        for file in files:
            if os.path.exists(file):
                destination = os.path.join(directory, file.lstrip('.'))
                print(f"📁 Moving {file} → {destination}")
                shutil.move(file, destination)
    
    # Remove unnecessary files
    files_to_remove = ["project.json"]
    for file in files_to_remove:
        if os.path.exists(file):
            print(f"🗑️  Removing {file}")
            os.remove(file)
    
    print("\n✅ Project structure cleaned!")


if __name__ == "__main__":
    clean_project_structure()
