#!/usr/bin/env python3
"""
Development environment setup script for Jarvis AI Assistant.
This script automates the setup of a development environment with all necessary
dependencies, tools, and configurations.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
import logging
import json
import shutil
import venv
from typing import Dict, List, Optional, Tuple
import pkg_resources
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
VENV_DIR = PROJECT_ROOT / ".venv"
REQUIREMENTS = {
    "core": PROJECT_ROOT / "requirements.txt",
    "dev": PROJECT_ROOT / "requirements-dev.txt",
    "docs": PROJECT_ROOT / "requirements-docs.txt",
    "test": PROJECT_ROOT / "requirements-test.txt"
}

class DevEnvironment:
    """Development environment setup utility class."""
    
    def __init__(self):
        """Initialize development environment setup."""
        self.system = platform.system().lower()
        self.is_windows = self.system == "windows"
        self.python_version = self._get_python_version()
    
    def _get_python_version(self) -> Tuple[int, int]:
        """Get Python version."""
        return sys.version_info[:2]
    
    def _run_command(self, command: List[str], **kwargs) -> subprocess.CompletedProcess:
        """Run a command and handle its output."""
        try:
            return subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                **kwargs
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(command)}")
            logger.error(f"Error output: {e.stderr}")
            raise
    
    def check_system_dependencies(self) -> bool:
        """Check system dependencies."""
        logger.info("Checking system dependencies...")
        
        dependencies = {
            "git": "Git version control",
            "python3": "Python interpreter",
            "pip": "Python package installer",
            "node": "Node.js runtime (for documentation)",
            "npm": "Node.js package manager"
        }
        
        missing = []
        for cmd, desc in dependencies.items():
            try:
                self._run_command([cmd, "--version"])
                logger.info(f"✓ {desc} found")
            except (subprocess.CalledProcessError, FileNotFoundError):
                missing.append(f"✗ {desc} not found")
        
        if missing:
            logger.error("Missing dependencies:")
            for msg in missing:
                logger.error(msg)
            return False
        
        return True
    
    def create_virtual_environment(self) -> bool:
        """Create Python virtual environment."""
        try:
            logger.info("Creating virtual environment...")
            
            if VENV_DIR.exists():
                logger.warning("Virtual environment already exists")
                return True
            
            venv.create(VENV_DIR, with_pip=True)
            
            # Get path to Python executable in venv
            if self.is_windows:
                python_path = VENV_DIR / "Scripts" / "python.exe"
            else:
                python_path = VENV_DIR / "bin" / "python"
            
            # Upgrade pip
            self._run_command([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])
            
            logger.info("Virtual environment created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error creating virtual environment: {e}")
            return False
    
    def install_requirements(self, dev: bool = True) -> bool:
        """Install project requirements."""
        try:
            logger.info("Installing project requirements...")
            
            # Get path to pip in venv
            if self.is_windows:
                pip_path = VENV_DIR / "Scripts" / "pip.exe"
            else:
                pip_path = VENV_DIR / "bin" / "pip"
            
            # Install core requirements
            self._run_command([
                str(pip_path), "install", "-r", str(REQUIREMENTS["core"])
            ])
            
            if dev:
                # Install development requirements
                for req_file in ["dev", "docs", "test"]:
                    if REQUIREMENTS[req_file].exists():
                        self._run_command([
                            str(pip_path), "install", "-r", str(REQUIREMENTS[req_file])
                        ])
            
            logger.info("Requirements installed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error installing requirements: {e}")
            return False
    
    def setup_git_hooks(self) -> bool:
        """Set up Git hooks."""
        try:
            logger.info("Setting up Git hooks...")
            
            # Install pre-commit
            if self.is_windows:
                pre_commit = VENV_DIR / "Scripts" / "pre-commit.exe"
            else:
                pre_commit = VENV_DIR / "bin" / "pre-commit"
            
            self._run_command([str(pre_commit), "install"])
            self._run_command([str(pre_commit), "install-hooks"])
            
            logger.info("Git hooks set up successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up Git hooks: {e}")
            return False
    
    def setup_database(self) -> bool:
        """Set up development database."""
        try:
            logger.info("Setting up development database...")
            
            # Get path to Python in venv
            if self.is_windows:
                python_path = VENV_DIR / "Scripts" / "python.exe"
            else:
                python_path = VENV_DIR / "bin" / "python"
            
            # Initialize database
            self._run_command([
                str(python_path),
                str(PROJECT_ROOT / "scripts" / "db_manager.py"),
                "init"
            ])
            
            logger.info("Database set up successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up database: {e}")
            return False
    
    def setup_ide_config(self) -> bool:
        """Set up IDE configuration."""
        try:
            logger.info("Setting up IDE configuration...")
            
            vscode_dir = PROJECT_ROOT / ".vscode"
            vscode_dir.mkdir(exist_ok=True)
            
            # Create settings.json
            settings = {
                "python.defaultInterpreterPath": str(
                    VENV_DIR / ("Scripts" if self.is_windows else "bin") / "python"
                ),
                "python.linting.enabled": True,
                "python.linting.pylintEnabled": True,
                "python.linting.flake8Enabled": True,
                "python.formatting.provider": "black",
                "python.testing.pytestEnabled": True,
                "editor.formatOnSave": True,
                "editor.rulers": [88, 100],
                "files.trimTrailingWhitespace": True,
                "files.insertFinalNewline": True
            }
            
            with open(vscode_dir / "settings.json", "w") as f:
                json.dump(settings, f, indent=4)
            
            # Create launch.json
            launch = {
                "version": "0.2.0",
                "configurations": [
                    {
                        "name": "Python: Current File",
                        "type": "python",
                        "request": "launch",
                        "program": "${file}",
                        "console": "integratedTerminal"
                    },
                    {
                        "name": "Python: Main Application",
                        "type": "python",
                        "request": "launch",
                        "program": "main.py",
                        "console": "integratedTerminal"
                    }
                ]
            }
            
            with open(vscode_dir / "launch.json", "w") as f:
                json.dump(launch, f, indent=4)
            
            logger.info("IDE configuration set up successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up IDE configuration: {e}")
            return False
    
    def setup_documentation(self) -> bool:
        """Set up documentation generation."""
        try:
            logger.info("Setting up documentation...")
            
            # Get path to Python in venv
            if self.is_windows:
                python_path = VENV_DIR / "Scripts" / "python.exe"
            else:
                python_path = VENV_DIR / "bin" / "python"
            
            # Generate initial documentation
            self._run_command([
                str(python_path),
                str(PROJECT_ROOT / "scripts" / "build_docs.py")
            ])
            
            logger.info("Documentation set up successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up documentation: {e}")
            return False

def main():
    """Main function."""
    env = DevEnvironment()
    
    # Check system dependencies
    if not env.check_system_dependencies():
        sys.exit(1)
    
    # Create virtual environment
    if not env.create_virtual_environment():
        sys.exit(1)
    
    # Install requirements
    if not env.install_requirements():
        sys.exit(1)
    
    # Set up Git hooks
    if not env.setup_git_hooks():
        sys.exit(1)
    
    # Set up database
    if not env.setup_database():
        sys.exit(1)
    
    # Set up IDE configuration
    if not env.setup_ide_config():
        sys.exit(1)
    
    # Set up documentation
    if not env.setup_documentation():
        sys.exit(1)
    
    logger.info("\nDevelopment environment setup completed successfully!")
    logger.info("\nNext steps:")
    logger.info("1. Activate the virtual environment:")
    if env.is_windows:
        logger.info("   .venv\\Scripts\\activate")
    else:
        logger.info("   source .venv/bin/activate")
    logger.info("2. Start coding!")
    logger.info("3. Run tests: pytest")
    logger.info("4. Build docs: python scripts/build_docs.py")

if __name__ == "__main__":
    main()
