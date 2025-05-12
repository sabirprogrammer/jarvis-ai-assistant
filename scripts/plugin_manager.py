#!/usr/bin/env python3
"""
Plugin management tools for Jarvis AI Assistant.
This script provides utilities for managing plugins, including installation,
validation, and maintenance of plugins.
"""

import os
import sys
import argparse
from pathlib import Path
import logging
import json
import yaml
from typing import Dict, List, Optional, Set, Union, Type
import importlib
import inspect
import shutil
import zipfile
import tempfile
import hashlib
from datetime import datetime
import re
from dataclasses import dataclass
import pkg_resources
import requests
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
PLUGINS_DIR = PROJECT_ROOT / "plugins"
PLUGIN_CACHE_DIR = PROJECT_ROOT / ".plugin_cache"
PLUGIN_DATA_DIR = PROJECT_ROOT / "data" / "plugins"
REPORTS_DIR = PROJECT_ROOT / "reports" / "plugins"

@dataclass
class PluginMetadata:
    """Plugin metadata information."""
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str]
    entry_point: str
    config_schema: Optional[Dict] = None
    enabled: bool = True

class PluginManager:
    """Plugin management utility class."""
    
    def __init__(self):
        """Initialize plugin manager."""
        self.plugins_dir = PLUGINS_DIR
        self.cache_dir = PLUGIN_CACHE_DIR
        self.data_dir = PLUGIN_DATA_DIR
        self.reports_dir = REPORTS_DIR
        
        # Create necessary directories
        self.plugins_dir.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Load base plugin class
        sys.path.insert(0, str(PROJECT_ROOT))
        try:
            from plugins.base_plugin import BasePlugin
            self.base_plugin_class = BasePlugin
        except ImportError:
            logger.error("Could not load base plugin class")
            raise
        finally:
            sys.path.pop(0)
    
    def discover_plugins(self) -> Dict[str, PluginMetadata]:
        """Discover installed plugins."""
        plugins = {}
        
        for plugin_dir in self.plugins_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith("__"):
                metadata_file = plugin_dir / "plugin.yaml"
                if metadata_file.exists():
                    try:
                        with open(metadata_file) as f:
                            metadata = yaml.safe_load(f)
                        
                        plugins[plugin_dir.name] = PluginMetadata(
                            name=metadata["name"],
                            version=metadata["version"],
                            description=metadata.get("description", ""),
                            author=metadata.get("author", "Unknown"),
                            dependencies=metadata.get("dependencies", []),
                            entry_point=metadata["entry_point"],
                            config_schema=metadata.get("config_schema"),
                            enabled=metadata.get("enabled", True)
                        )
                    except Exception as e:
                        logger.warning(f"Error loading plugin {plugin_dir.name}: {e}")
        
        return plugins
    
    def validate_plugin(self, plugin_dir: Path) -> Dict:
        """Validate a plugin's structure and code."""
        results = {
            "valid": False,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Check plugin structure
            required_files = ["plugin.yaml", "__init__.py"]
            for file in required_files:
                if not (plugin_dir / file).exists():
                    results["errors"].append(f"Missing required file: {file}")
            
            # Load metadata
            metadata_file = plugin_dir / "plugin.yaml"
            if metadata_file.exists():
                try:
                    with open(metadata_file) as f:
                        metadata = yaml.safe_load(f)
                    
                    # Validate required fields
                    required_fields = ["name", "version", "entry_point"]
                    for field in required_fields:
                        if field not in metadata:
                            results["errors"].append(
                                f"Missing required metadata field: {field}"
                            )
                    
                    # Validate version format
                    if "version" in metadata:
                        try:
                            pkg_resources.parse_version(metadata["version"])
                        except Exception:
                            results["errors"].append("Invalid version format")
                    
                    # Check dependencies
                    if "dependencies" in metadata:
                        if not isinstance(metadata["dependencies"], list):
                            results["errors"].append(
                                "Dependencies must be a list"
                            )
                        else:
                            for dep in metadata["dependencies"]:
                                try:
                                    pkg_resources.Requirement.parse(dep)
                                except Exception:
                                    results["errors"].append(
                                        f"Invalid dependency format: {dep}"
                                    )
                    
                    # Validate config schema if present
                    if "config_schema" in metadata:
                        if not isinstance(metadata["config_schema"], dict):
                            results["errors"].append(
                                "Config schema must be a dictionary"
                            )
                
                except Exception as e:
                    results["errors"].append(f"Error parsing plugin.yaml: {e}")
            
            # Validate plugin code
            try:
                # Add plugin directory to path temporarily
                sys.path.insert(0, str(plugin_dir.parent))
                
                # Import plugin module
                module_name = plugin_dir.name
                if "entry_point" in metadata:
                    module_path = f"{module_name}.{metadata['entry_point']}"
                    module = importlib.import_module(module_path)
                    
                    # Find plugin class
                    plugin_class = None
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and
                            obj != self.base_plugin_class and
                            issubclass(obj, self.base_plugin_class)):
                            plugin_class = obj
                            break
                    
                    if not plugin_class:
                        results["errors"].append(
                            "No plugin class found inheriting from BasePlugin"
                        )
                    else:
                        # Check required methods
                        required_methods = ["initialize", "cleanup"]
                        for method in required_methods:
                            if not hasattr(plugin_class, method):
                                results["errors"].append(
                                    f"Missing required method: {method}"
                                )
                
            except Exception as e:
                results["errors"].append(f"Error validating plugin code: {e}")
            finally:
                sys.path.pop(0)
            
            results["valid"] = len(results["errors"]) == 0
            return results
            
        except Exception as e:
            results["errors"].append(f"Error validating plugin: {e}")
            return results
    
    def install_plugin(self, source: Union[str, Path]) -> bool:
        """Install a plugin from file or directory."""
        try:
            # Create temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Handle different source types
                if isinstance(source, str) and source.startswith(("http://", "https://")):
                    # Download from URL
                    response = requests.get(source, stream=True)
                    response.raise_for_status()
                    
                    plugin_file = temp_path / "plugin.zip"
                    with open(plugin_file, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                elif isinstance(source, (str, Path)):
                    # Copy from local path
                    source_path = Path(source)
                    if source_path.is_dir():
                        shutil.copytree(source_path, temp_path / source_path.name)
                        plugin_dir = temp_path / source_path.name
                    else:
                        shutil.copy2(source_path, temp_path / source_path.name)
                        plugin_file = temp_path / source_path.name
                        
                        # Extract if it's a zip file
                        if plugin_file.suffix == ".zip":
                            with zipfile.ZipFile(plugin_file) as zf:
                                zf.extractall(temp_path)
                
                # Find plugin directory
                plugin_dirs = [
                    d for d in temp_path.iterdir()
                    if d.is_dir() and (d / "plugin.yaml").exists()
                ]
                
                if not plugin_dirs:
                    raise ValueError("No valid plugin found in source")
                
                plugin_dir = plugin_dirs[0]
                
                # Validate plugin
                validation = self.validate_plugin(plugin_dir)
                if not validation["valid"]:
                    for error in validation["errors"]:
                        logger.error(f"Validation error: {error}")
                    return False
                
                # Load metadata
                with open(plugin_dir / "plugin.yaml") as f:
                    metadata = yaml.safe_load(f)
                
                # Check if plugin already exists
                target_dir = self.plugins_dir / plugin_dir.name
                if target_dir.exists():
                    # Check version
                    try:
                        with open(target_dir / "plugin.yaml") as f:
                            existing_metadata = yaml.safe_load(f)
                        
                        existing_version = pkg_resources.parse_version(
                            existing_metadata["version"]
                        )
                        new_version = pkg_resources.parse_version(
                            metadata["version"]
                        )
                        
                        if new_version <= existing_version:
                            logger.error(
                                f"Plugin {metadata['name']} version "
                                f"{metadata['version']} is not newer than "
                                f"existing version {existing_metadata['version']}"
                            )
                            return False
                        
                        # Backup existing plugin
                        backup_dir = self.cache_dir / f"{plugin_dir.name}_backup_{int(time.time())}"
                        shutil.copytree(target_dir, backup_dir)
                        
                    except Exception as e:
                        logger.warning(f"Error checking existing plugin: {e}")
                    
                    # Remove existing plugin
                    shutil.rmtree(target_dir)
                
                # Install plugin
                shutil.copytree(plugin_dir, target_dir)
                
                # Install dependencies
                if metadata.get("dependencies"):
                    logger.info("Installing plugin dependencies...")
                    subprocess.run([
                        sys.executable, "-m", "pip", "install",
                        *metadata["dependencies"]
                    ])
                
                logger.info(f"Plugin {metadata['name']} installed successfully")
                return True
            
        except Exception as e:
            logger.error(f"Error installing plugin: {e}")
            return False
    
    def uninstall_plugin(self, plugin_name: str) -> bool:
        """Uninstall a plugin."""
        try:
            plugin_dir = self.plugins_dir / plugin_name
            if not plugin_dir.exists():
                logger.error(f"Plugin {plugin_name} not found")
                return False
            
            # Backup plugin
            backup_dir = self.cache_dir / f"{plugin_name}_backup_{int(time.time())}"
            shutil.copytree(plugin_dir, backup_dir)
            
            # Remove plugin
            shutil.rmtree(plugin_dir)
            
            # Remove plugin data
            data_dir = self.data_dir / plugin_name
            if data_dir.exists():
                shutil.rmtree(data_dir)
            
            logger.info(f"Plugin {plugin_name} uninstalled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error uninstalling plugin: {e}")
            return False
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin."""
        try:
            plugin_dir = self.plugins_dir / plugin_name
            if not plugin_dir.exists():
                logger.error(f"Plugin {plugin_name} not found")
                return False
            
            metadata_file = plugin_dir / "plugin.yaml"
            with open(metadata_file) as f:
                metadata = yaml.safe_load(f)
            
            metadata["enabled"] = True
            
            with open(metadata_file, "w") as f:
                yaml.dump(metadata, f)
            
            logger.info(f"Plugin {plugin_name} enabled")
            return True
            
        except Exception as e:
            logger.error(f"Error enabling plugin: {e}")
            return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin."""
        try:
            plugin_dir = self.plugins_dir / plugin_name
            if not plugin_dir.exists():
                logger.error(f"Plugin {plugin_name} not found")
                return False
            
            metadata_file = plugin_dir / "plugin.yaml"
            with open(metadata_file) as f:
                metadata = yaml.safe_load(f)
            
            metadata["enabled"] = False
            
            with open(metadata_file, "w") as f:
                yaml.dump(metadata, f)
            
            logger.info(f"Plugin {plugin_name} disabled")
            return True
            
        except Exception as e:
            logger.error(f"Error disabling plugin: {e}")
            return False
    
    def generate_report(self) -> Path:
        """Generate plugin status report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f"plugin_report_{timestamp}.html"
        
        plugins = self.discover_plugins()
        
        content = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Plugin Status Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            ".section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f2f2f2; }",
            ".enabled { color: #4caf50; }",
            ".disabled { color: #f44336; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Plugin Status Report</h1>",
            f"<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
            
            "<div class='section'>",
            "<h2>Installed Plugins</h2>",
            "<table>",
            "<tr><th>Name</th><th>Version</th><th>Author</th><th>Status</th></tr>"
        ]
        
        for plugin in sorted(plugins.values(), key=lambda p: p.name):
            status_class = "enabled" if plugin.enabled else "disabled"
            status_text = "Enabled" if plugin.enabled else "Disabled"
            
            content.append(
                f"<tr><td>{plugin.name}</td><td>{plugin.version}</td>"
                f"<td>{plugin.author}</td>"
                f"<td class='{status_class}'>{status_text}</td></tr>"
            )
        
        content.extend([
            "</table>",
            "</div>"
        ])
        
        # Add plugin details
        for plugin in sorted(plugins.values(), key=lambda p: p.name):
            content.extend([
                "<div class='section'>",
                f"<h2>{plugin.name}</h2>",
                f"<p>{plugin.description}</p>",
                "<h3>Details</h3>",
                "<ul>",
                f"<li><strong>Version:</strong> {plugin.version}</li>",
                f"<li><strong>Author:</strong> {plugin.author}</li>",
                f"<li><strong>Entry Point:</strong> {plugin.entry_point}</li>"
            ])
            
            if plugin.dependencies:
                content.extend([
                    "<li><strong>Dependencies:</strong>",
                    "<ul>"
                ])
                for dep in plugin.dependencies:
                    content.append(f"<li>{dep}</li>")
                content.extend([
                    "</ul>",
                    "</li>"
                ])
            
            if plugin.config_schema:
                content.extend([
                    "<li><strong>Configuration Schema:</strong>",
                    "<pre>",
                    json.dumps(plugin.config_schema, indent=2),
                    "</pre>",
                    "</li>"
                ])
            
            content.extend([
                "</ul>",
                "</div>"
            ])
        
        content.extend([
            "</body>",
            "</html>"
        ])
        
        report_file.write_text("\n".join(content))
        return report_file

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Jarvis AI Assistant Plugin Manager"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List plugins command
    list_parser = subparsers.add_parser("list", help="List installed plugins")
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    
    # Install plugin command
    install_parser = subparsers.add_parser("install", help="Install plugin")
    install_parser.add_argument(
        "source",
        help="Plugin source (file, directory, or URL)"
    )
    
    # Uninstall plugin command
    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall plugin")
    uninstall_parser.add_argument(
        "name",
        help="Plugin name"
    )
    
    # Enable plugin command
    enable_parser = subparsers.add_parser("enable", help="Enable plugin")
    enable_parser.add_argument(
        "name",
        help="Plugin name"
    )
    
    # Disable plugin command
    disable_parser = subparsers.add_parser("disable", help="Disable plugin")
    disable_parser.add_argument(
        "name",
        help="Plugin name"
    )
    
    # Validate plugin command
    validate_parser = subparsers.add_parser("validate", help="Validate plugin")
    validate_parser.add_argument(
        "name",
        help="Plugin name"
    )
    
    # Generate report command
    subparsers.add_parser("report", help="Generate plugin status report")
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    manager = PluginManager()
    
    try:
        if args.command == "list":
            plugins = manager.discover_plugins()
            
            if args.json:
                print(json.dumps(
                    {name: vars(plugin) for name, plugin in plugins.items()},
                    indent=2
                ))
            else:
                if not plugins:
                    print("No plugins installed")
                else:
                    print("\nInstalled Plugins:")
                    for plugin in sorted(plugins.values(), key=lambda p: p.name):
                        status = "Enabled" if plugin.enabled else "Disabled"
                        print(f"\n{plugin.name} ({plugin.version}) - {status}")
                        print(f"Author: {plugin.author}")
                        print(f"Description: {plugin.description}")
                        if plugin.dependencies:
                            print("Dependencies:")
                            for dep in plugin.dependencies:
                                print(f"  - {dep}")
        
        elif args.command == "install":
            success = manager.install_plugin(args.source)
            sys.exit(0 if success else 1)
        
        elif args.command == "uninstall":
            success = manager.uninstall_plugin(args.name)
            sys.exit(0 if success else 1)
        
        elif args.command == "enable":
            success = manager.enable_plugin(args.name)
            sys.exit(0 if success else 1)
        
        elif args.command == "disable":
            success = manager.disable_plugin(args.name)
            sys.exit(0 if success else 1)
        
        elif args.command == "validate":
            plugin_dir = manager.plugins_dir / args.name
            if not plugin_dir.exists():
                logger.error(f"Plugin {args.name} not found")
                sys.exit(1)
            
            results = manager.validate_plugin(plugin_dir)
            
            if results["valid"]:
                logger.info("Plugin validation successful")
                sys.exit(0)
            else:
                logger.error("Plugin validation failed:")
                for error in results["errors"]:
                    logger.error(f"- {error}")
                for warning in results["warnings"]:
                    logger.warning(f"- {warning}")
                sys.exit(1)
        
        elif args.command == "report":
            report_file = manager.generate_report()
            logger.info(f"Report generated: {report_file}")
        
        else:
            parser.print_help()
            sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
