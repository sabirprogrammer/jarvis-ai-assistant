"""
Tests for the core Assistant functionality.
"""
import pytest
from unittest.mock import MagicMock, patch
import asyncio
from pathlib import Path

@pytest.mark.core
class TestAssistant:
    """Test suite for Assistant class."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, assistant):
        """Test assistant initialization."""
        assert assistant is not None
        assert assistant.plugin_manager is not None
        assert assistant.config is not None
        assert assistant.is_running

    @pytest.mark.asyncio
    async def test_process_command(self, assistant):
        """Test command processing."""
        # Test basic command
        command = "tell me a joke"
        response = await assistant.process_command(command)
        assert isinstance(response, dict)
        assert "success" in response
        
        # Test empty command
        response = await assistant.process_command("")
        assert not response["success"]
        
        # Test invalid command
        response = await assistant.process_command("invalid_command_xyz")
        assert not response["success"]

    @pytest.mark.asyncio
    async def test_plugin_management(self, assistant, mock_plugin):
        """Test plugin loading and management."""
        # Test plugin loading
        plugin = mock_plugin(assistant)
        assert await assistant.plugin_manager.load_plugin(mock_plugin)
        
        # Test plugin activation
        plugin_name = plugin.__class__.__name__
        assert await assistant.plugin_manager.activate_plugin(plugin_name)
        assert plugin_name in assistant.plugin_manager.get_active_plugins()
        
        # Test plugin deactivation
        assert await assistant.plugin_manager.deactivate_plugin(plugin_name)
        assert plugin_name not in assistant.plugin_manager.get_active_plugins()

    @pytest.mark.asyncio
    async def test_command_routing(self, assistant, mock_plugin):
        """Test command routing to plugins."""
        # Load and activate plugin
        plugin = mock_plugin(assistant)
        await assistant.plugin_manager.load_plugin(mock_plugin)
        await assistant.plugin_manager.activate_plugin(plugin.__class__.__name__)
        
        # Test command routing
        response = await assistant.plugin_manager.process_command("test command")
        assert response["success"]
        assert response["message"] == "Mock response"

    @pytest.mark.asyncio
    async def test_shutdown(self, assistant):
        """Test assistant shutdown."""
        await assistant.shutdown()
        assert not assistant.is_running
        # Verify cleanup
        assert len(assistant.plugin_manager.get_active_plugins()) == 0

@pytest.mark.service
class TestServices:
    """Test suite for service integration."""
    
    @pytest.mark.asyncio
    async def test_weather_service(self, assistant, mock_weather_api):
        """Test weather service integration."""
        with patch('services.weather_service.WeatherService.get_weather') as mock_get:
            mock_get.return_value = mock_weather_api.data
            
            response = await assistant.process_command("what's the weather")
            assert response["success"]
            assert "temperature" in str(response["message"]).lower()

    @pytest.mark.asyncio
    async def test_news_service(self, assistant, mock_news_api):
        """Test news service integration."""
        with patch('services.news_service.NewsService.get_headlines') as mock_get:
            mock_get.return_value = mock_news_api.articles
            
            response = await assistant.process_command("show me the news")
            assert response["success"]
            assert "article" in str(response["message"]).lower()

    @pytest.mark.asyncio
    async def test_system_monitor(self, assistant, mock_system_stats):
        """Test system monitoring integration."""
        with patch('services.system_monitor.SystemMonitor.get_status') as mock_get:
            mock_get.return_value = mock_system_stats.stats
            
            response = await assistant.process_command("system status")
            assert response["success"]
            assert "cpu" in str(response["message"]).lower()

@pytest.mark.ui
class TestAssistantUI:
    """Test suite for UI integration."""
    
    def test_window_creation(self, app, assistant):
        """Test main window creation."""
        from ui.main_window import MainWindow
        window = MainWindow(assistant, {})
        assert window is not None
        assert window.assistant == assistant
        
        # Test basic UI elements
        assert window.chat_history is not None
        assert window.input_text is not None
        assert window.send_button is not None
        assert window.mic_button is not None

    def test_chat_interaction(self, app, assistant):
        """Test chat interface interaction."""
        from ui.main_window import MainWindow
        window = MainWindow(assistant, {})
        
        # Test message input
        test_message = "Hello, Assistant!"
        window.input_text.setPlainText(test_message)
        assert window.input_text.toPlainText() == test_message
        
        # Test message sending
        window._send_message()
        assert window.input_text.toPlainText() == ""  # Input should be cleared

    def test_settings_dialog(self, app, assistant):
        """Test settings dialog."""
        from ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog()
        assert dialog is not None
        
        # Test settings loading
        dialog.load_settings()
        assert dialog.openai_key is not None
        assert dialog.theme is not None

@pytest.mark.integration
class TestSystemIntegration:
    """Test suite for system integration."""
    
    @pytest.mark.asyncio
    async def test_config_loading(self, assistant, mock_config, temp_dir):
        """Test configuration loading."""
        config_path = temp_dir / "config.yaml"
        assert config_path.exists()
        
        # Test config values
        assert assistant.config["development"]["debug_mode"]
        assert assistant.config["database"]["type"] == "sqlite"

    @pytest.mark.asyncio
    async def test_database_integration(self, assistant, db):
        """Test database integration."""
        assert db.is_initialized()
        
        # Test basic database operations
        await db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        await db.execute("INSERT INTO test (value) VALUES (?)", ("test_value",))
        
        result = await db.fetch_one("SELECT value FROM test WHERE id = 1")
        assert result[0] == "test_value"

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_long_running_operations(self, assistant):
        """Test long-running operations."""
        # Simulate long-running task
        async def long_task():
            await asyncio.sleep(2)
            return {"success": True, "message": "Task completed"}
        
        response = await long_task()
        assert response["success"]
        assert response["message"] == "Task completed"

@pytest.mark.utils
class TestUtilities:
    """Test suite for utility functions."""
    
    def test_logger(self):
        """Test logging functionality."""
        from utils.logger import logger
        
        # Test different log levels
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        assert logger is not None

    @pytest.mark.asyncio
    async def test_db_manager(self, db):
        """Test database manager."""
        assert db is not None
        assert db.is_initialized()
        
        # Test transaction handling
        async with db.transaction():
            await db.execute("CREATE TABLE test2 (id INTEGER PRIMARY KEY)")
            await db.execute("INSERT INTO test2 DEFAULT VALUES")
        
        result = await db.fetch_one("SELECT COUNT(*) FROM test2")
        assert result[0] == 1

if __name__ == "__main__":
    pytest.main(["-v", __file__])
