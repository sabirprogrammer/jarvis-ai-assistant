"""
Tests for the plugin system functionality.
"""
import pytest
from unittest.mock import MagicMock, patch
import asyncio
from datetime import datetime

from plugins.base_plugin import BasePlugin, PluginManager
from plugins.example_plugin import JokePlugin, TimePlugin, CalculatorPlugin

@pytest.mark.plugin
class TestBasePlugin:
    """Test suite for BasePlugin class."""

    @pytest.mark.asyncio
    async def test_plugin_initialization(self, assistant):
        """Test plugin initialization."""
        class TestPlugin(BasePlugin):
            async def initialize(self):
                self.register_command("test", "Test command")
                return True
                
            async def process_command(self, command, context=None):
                return {"success": True, "message": "Test response"}

        plugin = TestPlugin(assistant)
        assert await plugin.initialize()
        assert plugin.name == "TestPlugin"
        assert len(plugin.get_commands()) == 1

    @pytest.mark.asyncio
    async def test_command_registration(self, assistant):
        """Test command registration functionality."""
        plugin = BasePlugin(assistant)
        plugin.register_command("test_pattern", "Test description")
        
        commands = plugin.get_commands()
        assert "test_pattern" in commands
        assert commands["test_pattern"] == "Test description"

    @pytest.mark.asyncio
    async def test_command_validation(self, assistant):
        """Test command validation."""
        class ValidationPlugin(BasePlugin):
            async def initialize(self):
                self.register_command("hello.*", "Greeting command")
                self.register_command("bye.*", "Farewell command")
                return True
                
            async def process_command(self, command, context=None):
                return {"success": True}

        plugin = ValidationPlugin(assistant)
        await plugin.initialize()
        
        assert await plugin.validate_command("hello world")
        assert await plugin.validate_command("bye now")
        assert not await plugin.validate_command("invalid command")

    @pytest.mark.asyncio
    async def test_error_handling(self, assistant):
        """Test plugin error handling."""
        plugin = BasePlugin(assistant)
        error_response = await plugin.handle_error(Exception("Test error"))
        
        assert not error_response["success"]
        assert "Test error" in error_response["message"]
        assert "error" in error_response

@pytest.mark.plugin
class TestPluginManager:
    """Test suite for PluginManager class."""

    @pytest.mark.asyncio
    async def test_plugin_loading(self, assistant):
        """Test plugin loading functionality."""
        manager = PluginManager(assistant)
        
        # Test loading valid plugin
        assert await manager.load_plugin(JokePlugin)
        assert "JokePlugin" in manager.plugins
        
        # Test loading same plugin twice
        assert await manager.load_plugin(JokePlugin)
        
        # Test loading invalid plugin
        class InvalidPlugin:
            pass
            
        with pytest.raises(Exception):
            await manager.load_plugin(InvalidPlugin)

    @pytest.mark.asyncio
    async def test_plugin_activation(self, assistant):
        """Test plugin activation and deactivation."""
        manager = PluginManager(assistant)
        await manager.load_plugin(TimePlugin)
        
        # Test activation
        assert await manager.activate_plugin("TimePlugin")
        assert "TimePlugin" in manager.active_plugins
        
        # Test deactivation
        assert await manager.deactivate_plugin("TimePlugin")
        assert "TimePlugin" not in manager.active_plugins
        
        # Test invalid plugin activation
        assert not await manager.activate_plugin("NonexistentPlugin")

    @pytest.mark.asyncio
    async def test_command_processing(self, assistant):
        """Test command processing through plugin manager."""
        manager = PluginManager(assistant)
        
        # Load and activate calculator plugin
        await manager.load_plugin(CalculatorPlugin)
        await manager.activate_plugin("CalculatorPlugin")
        
        # Test valid calculation
        response = await manager.process_command("calculate 5 + 3")
        assert response["success"]
        assert "8" in response["message"]
        
        # Test invalid calculation
        response = await manager.process_command("calculate 5 / 0")
        assert not response["success"]
        assert "divide by zero" in response["message"]

    @pytest.mark.asyncio
    async def test_plugin_info(self, assistant):
        """Test plugin information retrieval."""
        manager = PluginManager(assistant)
        await manager.load_plugin(JokePlugin)
        await manager.activate_plugin("JokePlugin")
        
        plugins = manager.get_available_plugins()
        assert len(plugins) > 0
        
        plugin_info = plugins[0]
        assert "name" in plugin_info
        assert "version" in plugin_info
        assert "description" in plugin_info
        assert "active" in plugin_info

@pytest.mark.plugin
class TestBuiltinPlugins:
    """Test suite for built-in plugins."""

    @pytest.mark.asyncio
    async def test_joke_plugin(self, assistant):
        """Test JokePlugin functionality."""
        plugin = JokePlugin(assistant)
        await plugin.initialize()
        
        # Test joke command
        response = await plugin.process_command("tell me a joke")
        assert response["success"]
        assert response["type"] == "joke"
        assert isinstance(response["message"], str)
        assert response["message"] in plugin.jokes

    @pytest.mark.asyncio
    async def test_time_plugin(self, assistant):
        """Test TimePlugin functionality."""
        plugin = TimePlugin(assistant)
        await plugin.initialize()
        
        # Test time command
        response = await plugin.process_command("what's the time")
        assert response["success"]
        assert response["type"] == "time"
        assert "current time" in response["message"].lower()
        
        # Test date command
        response = await plugin.process_command("what's today's date")
        assert response["success"]
        assert response["type"] == "date"
        assert "date" in response["message"].lower()

    @pytest.mark.asyncio
    async def test_calculator_plugin(self, assistant):
        """Test CalculatorPlugin functionality."""
        plugin = CalculatorPlugin(assistant)
        await plugin.initialize()
        
        test_cases = [
            ("calculate 5 + 3", 8),
            ("what's 10 - 4", 6),
            ("calculate 6 * 7", 42),
            ("what's 15 / 3", 5),
        ]
        
        for command, expected in test_cases:
            response = await plugin.process_command(command)
            assert response["success"]
            assert response["type"] == "calculation"
            assert str(expected) in response["message"]

@pytest.mark.integration
class TestPluginIntegration:
    """Test suite for plugin integration."""

    @pytest.mark.asyncio
    async def test_multiple_plugins(self, assistant):
        """Test multiple plugins working together."""
        # Load all plugins
        for plugin_class in [JokePlugin, TimePlugin, CalculatorPlugin]:
            await assistant.plugin_manager.load_plugin(plugin_class)
            await assistant.plugin_manager.activate_plugin(plugin_class.__name__)
        
        # Test each plugin's commands
        commands = [
            "tell me a joke",
            "what's the time",
            "calculate 10 + 5"
        ]
        
        for command in commands:
            response = await assistant.process_command(command)
            assert response["success"]

    @pytest.mark.asyncio
    async def test_plugin_conflicts(self, assistant):
        """Test handling of plugin command conflicts."""
        class ConflictPlugin1(BasePlugin):
            async def initialize(self):
                self.register_command("test", "Test command 1")
                return True
                
            async def process_command(self, command, context=None):
                return {"success": True, "message": "Response 1"}

        class ConflictPlugin2(BasePlugin):
            async def initialize(self):
                self.register_command("test", "Test command 2")
                return True
                
            async def process_command(self, command, context=None):
                return {"success": True, "message": "Response 2"}

        # Load conflicting plugins
        await assistant.plugin_manager.load_plugin(ConflictPlugin1)
        await assistant.plugin_manager.load_plugin(ConflictPlugin2)
        await assistant.plugin_manager.activate_plugin("ConflictPlugin1")
        await assistant.plugin_manager.activate_plugin("ConflictPlugin2")
        
        # First matching plugin should handle the command
        response = await assistant.process_command("test")
        assert response["success"]
        assert response["message"] == "Response 1"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
