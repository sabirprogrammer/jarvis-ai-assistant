#!/usr/bin/env python3
"""
Git hooks setup script for Jarvis AI Assistant.
This script sets up custom Git hooks for maintaining code quality and consistency.
"""

import os
import sys
import stat
from pathlib import Path
import shutil
import subprocess
from typing import Dict, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
HOOKS_DIR = PROJECT_ROOT / ".git" / "hooks"
CUSTOM_HOOKS_DIR = PROJECT_ROOT / "scripts" / "git_hooks"

# Hook definitions
HOOKS: Dict[str, str] = {
    "pre-commit": """#!/bin/bash
set -e

echo "Running pre-commit checks..."

# Check for debug statements
echo "Checking for debug statements..."
! git diff --cached --name-only | xargs grep -l "import pdb" || (echo "Error: Found pdb imports" && exit 1)
! git diff --cached --name-only | xargs grep -l "breakpoint()" || (echo "Error: Found breakpoint() calls" && exit 1)

# Run code formatting
echo "Running code formatting..."
black --check .

# Run linting
echo "Running linters..."
flake8 .
pylint $(git ls-files '*.py')

# Run type checking
echo "Running type checking..."
mypy .

# Run tests
echo "Running tests..."
pytest tests/

# Check for large files
echo "Checking for large files..."
git diff --cached --name-only | while read file; do
    if [ -f "$file" ]; then
        size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null)
        if [ "$size" -gt 5242880 ]; then  # 5MB
            echo "Error: $file is too large ($size bytes)"
            exit 1
        fi
    fi
done

echo "All pre-commit checks passed!"
""",

    "pre-push": """#!/bin/bash
set -e

echo "Running pre-push checks..."

# Run full test suite
echo "Running full test suite..."
pytest tests/ --cov=. --cov-report=term-missing

# Check documentation build
echo "Checking documentation build..."
python scripts/build_docs.py --check

# Run security checks
echo "Running security checks..."
bandit -r .

echo "All pre-push checks passed!"
""",

    "commit-msg": """#!/bin/bash
set -e

# Get the commit message
commit_msg_file="$1"
commit_msg=$(cat "$commit_msg_file")

# Patterns for conventional commits
conventional_pattern="^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)(\([a-z]+\))?: .+"

if ! echo "$commit_msg" | grep -qE "$conventional_pattern"; then
    echo "Error: Commit message does not follow conventional commits format."
    echo "Format: <type>(<scope>): <description>"
    echo "Types: feat, fix, docs, style, refactor, test, chore, perf, ci, build, revert"
    echo "Example: feat(ui): add new settings dialog"
    exit 1
fi

# Check message length
if [ ${#commit_msg} -gt 72 ]; then
    echo "Error: Commit message is too long (max 72 characters)"
    exit 1
fi
""",

    "post-checkout": """#!/bin/bash
set -e

# Check if dependencies have changed
if [ -f "requirements.txt" ]; then
    if git diff --name-only $1 $2 | grep -q "requirements.txt"; then
        echo "Dependencies have changed. Running pip install..."
        pip install -r requirements.txt
    fi
fi

# Rebuild documentation if docs have changed
if git diff --name-only $1 $2 | grep -q "^docs/"; then
    echo "Documentation has changed. Rebuilding..."
    python scripts/build_docs.py
fi
""",

    "post-merge": """#!/bin/bash
set -e

# Check if dependencies have changed
if git diff --name-only HEAD@{1} HEAD | grep -q "requirements.txt"; then
    echo "Dependencies have changed. Running pip install..."
    pip install -r requirements.txt
fi

# Rebuild documentation if docs have changed
if git diff --name-only HEAD@{1} HEAD | grep -q "^docs/"; then
    echo "Documentation has changed. Rebuilding..."
    python scripts/build_docs.py
fi
"""
}

def check_git_repo() -> bool:
    """Check if current directory is a git repository."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError:
        return False

def create_hooks_directory() -> None:
    """Create hooks directory if it doesn't exist."""
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created hooks directory: {HOOKS_DIR}")

def install_hook(name: str, content: str) -> None:
    """Install a git hook with the given name and content."""
    hook_path = HOOKS_DIR / name
    try:
        # Write hook content
        hook_path.write_text(content)
        
        # Make hook executable
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)
        
        logger.info(f"Installed {name} hook")
    except Exception as e:
        logger.error(f"Error installing {name} hook: {e}")
        sys.exit(1)

def backup_existing_hooks() -> None:
    """Backup existing git hooks."""
    backup_dir = HOOKS_DIR.parent / "hooks.backup"
    if HOOKS_DIR.exists():
        try:
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            shutil.copytree(HOOKS_DIR, backup_dir)
            logger.info(f"Backed up existing hooks to {backup_dir}")
        except Exception as e:
            logger.error(f"Error backing up existing hooks: {e}")
            sys.exit(1)

def check_dependencies() -> bool:
    """Check if required dependencies are installed."""
    required_tools = [
        "black",
        "flake8",
        "pylint",
        "mypy",
        "pytest",
        "bandit"
    ]
    
    missing_tools = []
    for tool in required_tools:
        try:
            subprocess.run(
                [tool, "--version"],
                check=True,
                capture_output=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing_tools.append(tool)
    
    if missing_tools:
        logger.error("Missing required tools: " + ", ".join(missing_tools))
        logger.info("Install using: pip install " + " ".join(missing_tools))
        return False
    
    return True

def main():
    """Main function to set up git hooks."""
    # Check if we're in a git repository
    if not check_git_repo():
        logger.error("Not a git repository")
        sys.exit(1)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Backup existing hooks
    backup_existing_hooks()
    
    # Create hooks directory
    create_hooks_directory()
    
    # Install hooks
    for hook_name, hook_content in HOOKS.items():
        install_hook(hook_name, hook_content)
    
    logger.info("Git hooks setup completed successfully")
    logger.info("\nInstalled hooks:")
    for hook_name in HOOKS:
        logger.info(f"- {hook_name}")

if __name__ == "__main__":
    main()
