#!/usr/bin/env python3
"""
Documentation build script for Jarvis AI Assistant.
This script automates the process of building documentation using Sphinx.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
BUILD_DIR = DOCS_DIR / "_build"
SOURCE_DIR = DOCS_DIR
STATIC_DIR = DOCS_DIR / "_static"
TEMPLATE_DIR = DOCS_DIR / "_templates"

def setup_directories() -> None:
    """Create necessary directories for documentation."""
    try:
        # Create directories if they don't exist
        STATIC_DIR.mkdir(parents=True, exist_ok=True)
        TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info("Documentation directories created successfully")
    except Exception as e:
        logger.error(f"Error creating directories: {e}")
        sys.exit(1)

def clean_build() -> None:
    """Clean the build directory."""
    try:
        if BUILD_DIR.exists():
            shutil.rmtree(BUILD_DIR)
            logger.info("Build directory cleaned")
    except Exception as e:
        logger.error(f"Error cleaning build directory: {e}")
        sys.exit(1)

def run_command(command: List[str], cwd: Path = None) -> Tuple[bool, str]:
    """Run a command and return its success status and output."""
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            check=True,
            capture_output=True,
            text=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr
    except Exception as e:
        return False, str(e)

def check_dependencies() -> bool:
    """Check if required dependencies are installed."""
    required_packages = [
        "sphinx",
        "sphinx-rtd-theme",
        "sphinx-autodoc-typehints",
        "sphinx-copybutton",
        "myst-parser"
    ]
    
    for package in required_packages:
        success, output = run_command(["pip", "show", package])
        if not success:
            logger.error(f"Missing required package: {package}")
            logger.info(f"Install using: pip install {package}")
            return False
    
    return True

def build_documentation(format_: str = "html", clean: bool = True) -> bool:
    """Build the documentation in the specified format."""
    try:
        if clean:
            clean_build()
        
        # Build API documentation
        logger.info("Generating API documentation...")
        success, output = run_command(
            ["sphinx-apidoc", "-o", str(SOURCE_DIR), str(PROJECT_ROOT)],
            cwd=PROJECT_ROOT
        )
        if not success:
            logger.error(f"Error generating API documentation: {output}")
            return False
        
        # Build documentation in specified format
        logger.info(f"Building {format_} documentation...")
        success, output = run_command(
            ["sphinx-build", "-b", format_, str(SOURCE_DIR), str(BUILD_DIR / format_)],
            cwd=PROJECT_ROOT
        )
        if not success:
            logger.error(f"Error building documentation: {output}")
            return False
        
        logger.info(f"Documentation built successfully in {BUILD_DIR / format_}")
        return True
        
    except Exception as e:
        logger.error(f"Error building documentation: {e}")
        return False

def create_custom_templates() -> None:
    """Create custom Sphinx templates."""
    module_template = """
{{- fullname | escape | underline}}

.. automodule:: {{ fullname }}
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
"""
    
    template_path = TEMPLATE_DIR / "custom-module-template.rst"
    template_path.write_text(module_template)
    logger.info("Custom templates created")

def copy_static_files() -> None:
    """Copy static files to documentation directory."""
    try:
        # Copy logo
        logo_source = PROJECT_ROOT / "assets" / "logo.png"
        if logo_source.exists():
            shutil.copy(logo_source, STATIC_DIR / "logo.png")
        
        # Copy favicon
        favicon_source = PROJECT_ROOT / "assets" / "favicon.ico"
        if favicon_source.exists():
            shutil.copy(favicon_source, STATIC_DIR / "favicon.ico")
        
        logger.info("Static files copied successfully")
    except Exception as e:
        logger.error(f"Error copying static files: {e}")

def main():
    """Main function to build documentation."""
    parser = argparse.ArgumentParser(description="Build Jarvis AI Assistant documentation")
    parser.add_argument(
        "--format",
        choices=["html", "pdf", "epub"],
        default="html",
        help="Output format for documentation"
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Don't clean build directory before building"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check documentation for warnings/errors without building"
    )
    
    args = parser.parse_args()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Setup directories
    setup_directories()
    
    # Create custom templates
    create_custom_templates()
    
    # Copy static files
    copy_static_files()
    
    if args.check:
        # Run sphinx-build in nitpicky mode with warnings as errors
        success, output = run_command([
            "sphinx-build", "-b", "html", "-nW", "--keep-going",
            str(SOURCE_DIR), str(BUILD_DIR / "html")
        ])
        if not success:
            logger.error("Documentation check failed:")
            print(output)
            sys.exit(1)
        logger.info("Documentation check passed")
    else:
        # Build documentation
        if not build_documentation(args.format, not args.no_clean):
            sys.exit(1)
    
    logger.info("Documentation build process completed")

if __name__ == "__main__":
    main()
