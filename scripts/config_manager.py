#!/usr/bin/env python3
"""
Configuration management tools for Jarvis AI Assistant.
This script provides utilities for managing configuration across different
environments, validating settings, and generating configuration templates.
"""

import os
import sys
import argparse
from pathlib import Path
import logging
import json
import yaml
from typing import Dict, List, Optional, Any
import secrets
import string
from datetime import datetime
import shutil
from dataclasses import dataclass, field
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_TEMPLATE = {
    "environment": "development",
    "debug": True,
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": "logs/jarvis.log",
        "max_size": 10485760,  # 10MB
        "backup_count": 5
    },
    "database": {
        "type": "sqlite",
        "sqlite": {
            "path": "data/jarvis.db"
        }
    },
    "api": {
        "openai": {
            "api_key": "",
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens": 150
        },
        "google": {
            "client_id": "",
            "client_secret": "",
            "project_id": ""
        },
        "weather": {
            "api_key": "",
            "units": "metric"
        }
    },
    "ui": {
        "theme": "light",
        "font_family": "Segoe UI",
        "font_size": 10,
        "window": {
            "width": 800,
            "height": 600,
            "title": "Jarvis AI Assistant"
        }
    },
    "speech": {
        "language": "en-US",
        "rate": 150,
        "volume": 1.0,
        "voice": "default"
    },
    "plugins": {
        "enabled": True,
        "directory": "plugins",
        "auto_load": True
    },
    "security": {
        "encryption_key": "",
        "token_expiry": 3600,
        "max_login_attempts": 3
    },
    "system": {
        "cpu_threshold": 80,
        "memory_threshold": 80,
        "update_interval": 60
    }
}

@dataclass
class ConfigValidator:
    """Configuration validation rules and schemas."""
    
    required_fields: Dict[str, type] = field(default_factory=lambda: {
        "environment": str,
        "debug": bool,
        "logging.level": str,
        "database.type": str,
        "api.openai.api_key": str,
        "ui.theme": str,
        "plugins.enabled": bool
    })
    
    value_constraints: Dict[str, List[str]] = field(default_factory=lambda: {
        "environment": ["development", "testing", "production"],
        "logging.level": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        "database.type": ["sqlite"],
        "ui.theme": ["light", "dark"]
    })
    
    numeric_ranges: Dict[str, tuple] = field(default_factory=lambda: {
        "ui.font_size": (8, 24),
        "speech.rate": (50, 300),
        "speech.volume": (0.0, 1.0),
        "system.cpu_threshold": (0, 100),
        "system.memory_threshold": (0, 100)
    })

class ConfigManager:
    """Configuration management utility class."""
    
    def __init__(self):
        """Initialize configuration manager."""
        self.config_dir = CONFIG_DIR
        self.config_dir.mkdir(exist_ok=True)
        self.validator = ConfigValidator()
    
    def _generate_secret(self, length: int = 32) -> str:
        """Generate a secure random secret."""
        alphabet = string.ascii_letters + string.digits + string.punctuation
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get nested dictionary value using dot notation."""
        keys = path.split('.')
        value = data
        for key in keys:
            value = value.get(key)
            if value is None:
                return None
        return value
    
    def _set_nested_value(self, data: Dict, path: str, value: Any) -> None:
        """Set nested dictionary value using dot notation."""
        keys = path.split('.')
        current = data
        for key in keys[:-1]:
            current = current.setdefault(key, {})
        current[keys[-1]] = value
    
    def create_config(self, environment: str, output: Optional[Path] = None) -> Path:
        """Create a new configuration file."""
        try:
            config = CONFIG_TEMPLATE.copy()
            config["environment"] = environment
            
            # Generate secrets
            config["security"]["encryption_key"] = self._generate_secret()
            
            # Adjust settings based on environment
            if environment == "production":
                config["debug"] = False
                config["logging"]["level"] = "WARNING"
            elif environment == "testing":
                config["database"]["sqlite"]["path"] = ":memory:"
            
            # Save configuration
            if output is None:
                output = self.config_dir / f"config.{environment}.yaml"
            
            with open(output, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Created configuration file: {output}")
            return output
            
        except Exception as e:
            logger.error(f"Error creating configuration: {e}")
            raise
    
    def validate_config(self, config_file: Path) -> List[str]:
        """Validate configuration file."""
        errors = []
        
        try:
            with open(config_file) as f:
                config = yaml.safe_load(f)
            
            # Check required fields and types
            for field, field_type in self.validator.required_fields.items():
                value = self._get_nested_value(config, field)
                if value is None:
                    errors.append(f"Missing required field: {field}")
                elif not isinstance(value, field_type):
                    errors.append(
                        f"Invalid type for {field}: expected {field_type.__name__}, "
                        f"got {type(value).__name__}"
                    )
            
            # Check value constraints
            for field, valid_values in self.validator.value_constraints.items():
                value = self._get_nested_value(config, field)
                if value is not None and value not in valid_values:
                    errors.append(
                        f"Invalid value for {field}: {value}. "
                        f"Must be one of: {', '.join(valid_values)}"
                    )
            
            # Check numeric ranges
            for field, (min_val, max_val) in self.validator.numeric_ranges.items():
                value = self._get_nested_value(config, field)
                if value is not None:
                    try:
                        num_value = float(value)
                        if not min_val <= num_value <= max_val:
                            errors.append(
                                f"Value for {field} must be between {min_val} and {max_val}"
                            )
                    except ValueError:
                        errors.append(f"Invalid numeric value for {field}: {value}")
            
            return errors
            
        except Exception as e:
            return [f"Error validating configuration: {e}"]
    
    def merge_configs(self, base_file: Path, override_file: Path) -> Dict:
        """Merge two configuration files."""
        try:
            with open(base_file) as f:
                base_config = yaml.safe_load(f)
            
            with open(override_file) as f:
                override_config = yaml.safe_load(f)
            
            def deep_merge(base: Dict, override: Dict) -> Dict:
                """Recursively merge two dictionaries."""
                merged = base.copy()
                for key, value in override.items():
                    if (
                        key in merged and
                        isinstance(merged[key], dict) and
                        isinstance(value, dict)
                    ):
                        merged[key] = deep_merge(merged[key], value)
                    else:
                        merged[key] = value
                return merged
            
            return deep_merge(base_config, override_config)
            
        except Exception as e:
            logger.error(f"Error merging configurations: {e}")
            raise
    
    def update_config(self, config_file: Path, updates: Dict) -> bool:
        """Update configuration values."""
        try:
            with open(config_file) as f:
                config = yaml.safe_load(f)
            
            # Apply updates
            for path, value in updates.items():
                self._set_nested_value(config, path, value)
            
            # Validate updated config
            errors = self.validate_config(config_file)
            if errors:
                logger.error("Validation errors:")
                for error in errors:
                    logger.error(f"- {error}")
                return False
            
            # Backup existing config
            backup_file = config_file.with_suffix(f".bak.{int(time.time())}")
            shutil.copy2(config_file, backup_file)
            
            # Save updated config
            with open(config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Updated configuration file: {config_file}")
            logger.info(f"Backup created: {backup_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return False
    
    def show_config(self, config_file: Path, format: str = "yaml") -> None:
        """Display configuration contents."""
        try:
            with open(config_file) as f:
                config = yaml.safe_load(f)
            
            if format == "json":
                print(json.dumps(config, indent=2))
            else:
                print(yaml.dump(config, default_flow_style=False, sort_keys=False))
            
        except Exception as e:
            logger.error(f"Error displaying configuration: {e}")
            raise

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Jarvis AI Assistant Configuration Manager"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Create config command
    create_parser = subparsers.add_parser("create", help="Create configuration")
    create_parser.add_argument(
        "environment",
        choices=["development", "testing", "production"],
        help="Target environment"
    )
    create_parser.add_argument(
        "--output",
        type=Path,
        help="Output file path"
    )
    
    # Validate config command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration")
    validate_parser.add_argument(
        "config_file",
        type=Path,
        help="Configuration file to validate"
    )
    
    # Merge configs command
    merge_parser = subparsers.add_parser("merge", help="Merge configurations")
    merge_parser.add_argument(
        "base_file",
        type=Path,
        help="Base configuration file"
    )
    merge_parser.add_argument(
        "override_file",
        type=Path,
        help="Override configuration file"
    )
    merge_parser.add_argument(
        "--output",
        type=Path,
        help="Output file path"
    )
    
    # Update config command
    update_parser = subparsers.add_parser("update", help="Update configuration")
    update_parser.add_argument(
        "config_file",
        type=Path,
        help="Configuration file to update"
    )
    update_parser.add_argument(
        "updates",
        help="Updates in key=value format (dot notation for nested keys)",
        nargs="+"
    )
    
    # Show config command
    show_parser = subparsers.add_parser("show", help="Show configuration")
    show_parser.add_argument(
        "config_file",
        type=Path,
        help="Configuration file to show"
    )
    show_parser.add_argument(
        "--format",
        choices=["yaml", "json"],
        default="yaml",
        help="Output format"
    )
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    manager = ConfigManager()
    
    try:
        if args.command == "create":
            config_file = manager.create_config(args.environment, args.output)
            logger.info(f"Configuration created: {config_file}")
        
        elif args.command == "validate":
            errors = manager.validate_config(args.config_file)
            if errors:
                logger.error("Validation errors:")
                for error in errors:
                    logger.error(f"- {error}")
                sys.exit(1)
            logger.info("Configuration is valid")
        
        elif args.command == "merge":
            merged = manager.merge_configs(args.base_file, args.override_file)
            if args.output:
                with open(args.output, 'w') as f:
                    yaml.dump(merged, f, default_flow_style=False, sort_keys=False)
                logger.info(f"Merged configuration saved to: {args.output}")
            else:
                print(yaml.dump(merged, default_flow_style=False, sort_keys=False))
        
        elif args.command == "update":
            updates = {}
            for update in args.updates:
                key, value = update.split('=', 1)
                # Try to parse value as JSON for proper typing
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
                updates[key] = value
            
            success = manager.update_config(args.config_file, updates)
            sys.exit(0 if success else 1)
        
        elif args.command == "show":
            manager.show_config(args.config_file, args.format)
        
        else:
            parser.print_help()
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
