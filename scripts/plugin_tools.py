#!/usr/bin/env python3
"""
Plugin development tools for Jarvis AI Assistant.
This script provides utilities for creating, testing, and managing plugins.
"""

import os
import sys
import argparse
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import logging
import re
from datetime import datetime
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
PLUGINS_DIR = PROJECT_ROOT / "plugins"
PLUGIN_TEMPLATE = """\"\"\"
{plugin_name} plugin for Jarvis AI Assistant.
Created: {creation_date}
Author: {author}
Description: {description}
\"\"\"

from typing import Dict, Optional
from plugins.base_plugin import BasePlugin

class {class_name}(BasePlugin):
    \"\"\"
    {plugin_name} plugin implementation.
    
    This plugin {description_lower}
    \"\"\"
    
    async def initialize(self) -> bool:
        \"\"\"Initialize the plugin.\"\"\"
        self.name = "{plugin_name}"
        self.description = "{description}"
        self.version = "{version}"
        
        # Register command patterns
        self.register_command(
            "{command_pattern}",
            "Example command pattern"
        )
        
        return True
    
    async def process_command(self, command: str, context: Optional[Dict] = None) -> Dict:
        \"\"\"
        Process a command.
        
        Args:
            command: The command to process
            context: Optional context dictionary
            
        Returns:
            Dict containing the response
        \"\"\"
        try:
            # Add your command processing logic here
            return {
                "success": True,
                "message": "Command processed successfully",
                "type": self.name.lower()
            }
            
        except Exception as e:
            return self.handle_error(e)
"""

PLUGIN_TEST_TEMPLATE = """\"\"\"
Tests for {plugin_name} plugin.
\"\"\"

import pytest
from unittest.mock import MagicMock, patch
from plugins.{plugin_file} import {class_name}

@pytest.mark.plugin
class Test{class_name}:
    \"\"\"Test suite for {plugin_name} plugin.\"\"\"
    
    @pytest.fixture
    def plugin(self, assistant):
        \"\"\"Create plugin instance for testing.\"\"\"
        return {class_name}(assistant)
    
    @pytest.mark.asyncio
    async def test_initialization(self, plugin):
        \"\"\"Test plugin initialization.\"\"\"
        assert await plugin.initialize()
        assert plugin.name == "{plugin_name}"
        assert plugin.version == "{version}"
        
        # Verify command registration
        commands = plugin.get_commands()
        assert "{command_pattern}" in commands
    
    @pytest.mark.asyncio
    async def test_command_processing(self, plugin):
        \"\"\"Test command processing.\"\"\"
        await plugin.initialize()
        
        # Test successful command
        response = await plugin.process_command("{command_pattern}")
        assert response["success"]
        assert response["type"] == plugin.name.lower()
        
        # Test invalid command
        response = await plugin.process_command("invalid command")
        assert not response["success"]
    
    @pytest.mark.asyncio
    async def test_error_handling(self, plugin):
        \"\"\"Test error handling.\"\"\"
        await plugin.initialize()
        
        # Simulate error in processing
        with patch.object(plugin, 'process_command', side_effect=Exception("Test error")):
            response = await plugin.process_command("{command_pattern}")
            assert not response["success"]
            assert "Test error" in response["message"]
"""

class PluginTools:
    """Plugin development tools."""
    
    def __init__(self):
        """Initialize plugin tools."""
        self.plugins_dir = PLUGINS_DIR
        self.plugins_dir.mkdir(exist_ok=True)
    
    def create_plugin(self, args: argparse.Namespace) -> bool:
        """Create a new plugin."""
        try:
            # Generate plugin filename and class name
            plugin_file = f"{args.name.lower().replace(' ', '_')}.py"
            class_name = ''.join(word.capitalize() for word in args.name.split())
            if not class_name.endswith('Plugin'):
                class_name += 'Plugin'
            
            # Create plugin file
            plugin_path = self.plugins_dir / plugin_file
            if plugin_path.exists() and not args.force:
                logger.error(f"Plugin file already exists: {plugin_path}")
                return False
            
            # Format plugin content
            plugin_content = PLUGIN_TEMPLATE.format(
                plugin_name=args.name,
                class_name=class_name,
                description=args.description,
                description_lower=args.description.lower(),
                version=args.version,
                command_pattern=args.command_pattern,
                creation_date=datetime.now().strftime("%Y-%m-%d"),
                author=args.author
            )
            
            # Write plugin file
            plugin_path.write_text(plugin_content)
            logger.info(f"Created plugin file: {plugin_path}")
            
            # Create test file
            if not args.no_tests:
                test_path = PROJECT_ROOT / "tests" / f"test_{plugin_file}"
                test_content = PLUGIN_TEST_TEMPLATE.format(
                    plugin_name=args.name,
                    plugin_file=plugin_file[:-3],
                    class_name=class_name,
                    version=args.version,
                    command_pattern=args.command_pattern
                )
                test_path.write_text(test_content)
                logger.info(f"Created test file: {test_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating plugin: {e}")
            return False
    
    def list_plugins(self) -> List[Dict]:
        """List all available plugins."""
        plugins = []
        for plugin_file in self.plugins_dir.glob("*.py"):
            if plugin_file.name != "__init__.py":
                try:
                    content = plugin_file.read_text()
                    # Extract metadata using regex
                    name_match = re.search(r'self\.name = "(.*?)"', content)
                    desc_match = re.search(r'self\.description = "(.*?)"', content)
                    ver_match = re.search(r'self\.version = "(.*?)"', content)
                    
                    plugins.append({
                        "file": plugin_file.name,
                        "name": name_match.group(1) if name_match else "Unknown",
                        "description": desc_match.group(1) if desc_match else "No description",
                        "version": ver_match.group(1) if ver_match else "0.0.0"
                    })
                except Exception as e:
                    logger.warning(f"Error reading plugin {plugin_file}: {e}")
        
        return plugins
    
    def validate_plugin(self, plugin_file: Path) -> Dict:
        """Validate a plugin file."""
        results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            content = plugin_file.read_text()
            
            # Check for required attributes
            required_attrs = ["name", "description", "version"]
            for attr in required_attrs:
                if f"self.{attr}" not in content:
                    results["errors"].append(f"Missing required attribute: {attr}")
            
            # Check for initialize method
            if "async def initialize" not in content:
                results["errors"].append("Missing initialize method")
            
            # Check for process_command method
            if "async def process_command" not in content:
                results["errors"].append("Missing process_command method")
            
            # Check for command registration
            if "register_command" not in content:
                results["warnings"].append("No commands registered")
            
            # Check for proper error handling
            if "handle_error" not in content:
                results["warnings"].append("No error handling implemented")
            
            results["valid"] = len(results["errors"]) == 0
            
        except Exception as e:
            results["valid"] = False
            results["errors"].append(f"Error validating plugin: {e}")
        
        return results

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Jarvis AI Assistant Plugin Tools")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Create plugin command
    create_parser = subparsers.add_parser("create", help="Create a new plugin")
    create_parser.add_argument("name", help="Plugin name")
    create_parser.add_argument("description", help="Plugin description")
    create_parser.add_argument(
        "--version",
        default="0.1.0",
        help="Plugin version"
    )
    create_parser.add_argument(
        "--author",
        default=os.environ.get("USER", "Unknown"),
        help="Plugin author"
    )
    create_parser.add_argument(
        "--command-pattern",
        default="example.*",
        help="Initial command pattern"
    )
    create_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing plugin"
    )
    create_parser.add_argument(
        "--no-tests",
        action="store_true",
        help="Skip test file creation"
    )
    
    # List plugins command
    list_parser = subparsers.add_parser("list", help="List available plugins")
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    
    # Validate plugin command
    validate_parser = subparsers.add_parser("validate", help="Validate a plugin")
    validate_parser.add_argument(
        "plugin",
        help="Plugin file to validate"
    )
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    tools = PluginTools()
    
    if args.command == "create":
        success = tools.create_plugin(args)
        sys.exit(0 if success else 1)
        
    elif args.command == "list":
        plugins = tools.list_plugins()
        if args.json:
            print(json.dumps(plugins, indent=2))
        else:
            print("\nAvailable Plugins:")
            for plugin in plugins:
                print(f"\n{plugin['name']} (v{plugin['version']})")
                print(f"File: {plugin['file']}")
                print(f"Description: {plugin['description']}")
        
    elif args.command == "validate":
        plugin_path = Path(args.plugin)
        if not plugin_path.exists():
            logger.error(f"Plugin file not found: {plugin_path}")
            sys.exit(1)
        
        results = tools.validate_plugin(plugin_path)
        print(f"\nValidation results for {plugin_path.name}:")
        print(f"Valid: {'Yes' if results['valid'] else 'No'}")
        
        if results["errors"]:
            print("\nErrors:")
            for error in results["errors"]:
                print(f"- {error}")
        
        if results["warnings"]:
            print("\nWarnings:")
            for warning in results["warnings"]:
                print(f"- {warning}")
        
        sys.exit(0 if results["valid"] else 1)
    
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
