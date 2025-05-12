from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import asyncio

from utils.logger import logger

class BasePlugin(ABC):
    """
    Base class for all Jarvis AI Assistant plugins.
    Plugins must inherit from this class and implement required methods.
    """

    def __init__(self, assistant):
        """
        Initialize the plugin
        
        Args:
            assistant: Reference to the main Assistant instance
        """
        self.assistant = assistant
        self.name = self.__class__.__name__
        self.description = "Base plugin class"
        self.version = "1.0.0"
        self.author = "Unknown"
        self.commands = {}
        self.is_active = False

    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the plugin. Must be implemented by subclasses.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        pass

    @abstractmethod
    async def process_command(self, command: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a command. Must be implemented by subclasses.
        
        Args:
            command: The command to process
            context: Optional context information
            
        Returns:
            dict: Response containing at least 'success' and 'message' keys
        """
        pass

    async def shutdown(self):
        """Clean shutdown of the plugin"""
        try:
            self.is_active = False
            logger.info(f"Plugin {self.name} shutdown complete")
        except Exception as e:
            logger.error(f"Error during plugin shutdown: {str(e)}")

    def get_commands(self) -> Dict[str, str]:
        """
        Get list of commands supported by this plugin
        
        Returns:
            dict: Dictionary of command patterns and their descriptions
        """
        return self.commands

    def get_info(self) -> Dict[str, str]:
        """
        Get plugin information
        
        Returns:
            dict: Plugin metadata
        """
        return {
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'author': self.author,
            'commands': len(self.commands)
        }

    def register_command(self, pattern: str, description: str):
        """
        Register a new command pattern
        
        Args:
            pattern: Regular expression pattern for the command
            description: Description of what the command does
        """
        self.commands[pattern] = description

    async def validate_command(self, command: str) -> bool:
        """
        Check if a command is supported by this plugin
        
        Args:
            command: Command to validate
            
        Returns:
            bool: True if command is supported, False otherwise
        """
        try:
            for pattern in self.commands.keys():
                if pattern.lower() in command.lower():
                    return True
            return False
        except Exception as e:
            logger.error(f"Error validating command: {str(e)}")
            return False

    async def handle_error(self, error: Exception) -> Dict[str, Any]:
        """
        Handle plugin errors
        
        Args:
            error: The exception that occurred
            
        Returns:
            dict: Error response
        """
        error_msg = str(error)
        logger.error(f"Plugin {self.name} error: {error_msg}")
        return {
            'success': False,
            'message': f"Plugin error: {error_msg}",
            'error': error_msg
        }

class PluginManager:
    """
    Manages loading, registration, and execution of plugins
    """

    def __init__(self, assistant):
        """
        Initialize the plugin manager
        
        Args:
            assistant: Reference to the main Assistant instance
        """
        self.assistant = assistant
        self.plugins = {}
        self.active_plugins = set()

    async def load_plugin(self, plugin_class) -> bool:
        """
        Load and initialize a plugin
        
        Args:
            plugin_class: The plugin class to load
            
        Returns:
            bool: True if plugin loaded successfully, False otherwise
        """
        try:
            # Create plugin instance
            plugin = plugin_class(self.assistant)
            
            # Initialize plugin
            if await plugin.initialize():
                self.plugins[plugin.name] = plugin
                logger.info(f"Plugin {plugin.name} loaded successfully")
                return True
            else:
                logger.error(f"Failed to initialize plugin {plugin.name}")
                return False
                
        except Exception as e:
            logger.error(f"Error loading plugin: {str(e)}")
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a plugin
        
        Args:
            plugin_name: Name of the plugin to unload
            
        Returns:
            bool: True if plugin unloaded successfully, False otherwise
        """
        try:
            if plugin_name in self.plugins:
                plugin = self.plugins[plugin_name]
                await plugin.shutdown()
                del self.plugins[plugin_name]
                if plugin_name in self.active_plugins:
                    self.active_plugins.remove(plugin_name)
                logger.info(f"Plugin {plugin_name} unloaded successfully")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error unloading plugin: {str(e)}")
            return False

    async def activate_plugin(self, plugin_name: str) -> bool:
        """
        Activate a loaded plugin
        
        Args:
            plugin_name: Name of the plugin to activate
            
        Returns:
            bool: True if plugin activated successfully, False otherwise
        """
        try:
            if plugin_name in self.plugins:
                self.plugins[plugin_name].is_active = True
                self.active_plugins.add(plugin_name)
                logger.info(f"Plugin {plugin_name} activated")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error activating plugin: {str(e)}")
            return False

    async def deactivate_plugin(self, plugin_name: str) -> bool:
        """
        Deactivate a plugin
        
        Args:
            plugin_name: Name of the plugin to deactivate
            
        Returns:
            bool: True if plugin deactivated successfully, False otherwise
        """
        try:
            if plugin_name in self.plugins:
                self.plugins[plugin_name].is_active = False
                self.active_plugins.remove(plugin_name)
                logger.info(f"Plugin {plugin_name} deactivated")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deactivating plugin: {str(e)}")
            return False

    async def process_command(self, command: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a command through appropriate plugins
        
        Args:
            command: The command to process
            context: Optional context information
            
        Returns:
            dict: Response from the plugin that handled the command
        """
        try:
            # Try each active plugin
            for plugin_name in self.active_plugins:
                plugin = self.plugins[plugin_name]
                if await plugin.validate_command(command):
                    return await plugin.process_command(command, context)
            
            # No plugin could handle the command
            return {
                'success': False,
                'message': "No plugin available to handle this command"
            }
            
        except Exception as e:
            logger.error(f"Error processing command through plugins: {str(e)}")
            return {
                'success': False,
                'message': f"Plugin error: {str(e)}"
            }

    def get_active_plugins(self) -> List[str]:
        """
        Get list of active plugin names
        
        Returns:
            list: Names of active plugins
        """
        return list(self.active_plugins)

    def get_available_plugins(self) -> List[Dict[str, Any]]:
        """
        Get information about all available plugins
        
        Returns:
            list: List of plugin information dictionaries
        """
        return [
            {
                **plugin.get_info(),
                'active': plugin.name in self.active_plugins
            }
            for plugin in self.plugins.values()
        ]

    def get_plugin_commands(self) -> Dict[str, Dict[str, str]]:
        """
        Get all commands from active plugins
        
        Returns:
            dict: Dictionary of plugin names and their commands
        """
        return {
            plugin_name: self.plugins[plugin_name].get_commands()
            for plugin_name in self.active_plugins
        }

    async def shutdown(self):
        """Clean shutdown of all plugins"""
        try:
            for plugin in self.plugins.values():
                await plugin.shutdown()
            self.plugins.clear()
            self.active_plugins.clear()
            logger.info("All plugins shutdown complete")
        except Exception as e:
            logger.error(f"Error during plugin shutdown: {str(e)}")
