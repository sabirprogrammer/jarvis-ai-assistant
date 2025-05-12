"""
Tests for UI components (main window, settings dialog, plugin manager).
"""
import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QMessageBox,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt6.QtTest import QTest

from ui.main_window import MainWindow
from ui.settings_dialog import SettingsDialog
from ui.plugin_manager_dialog import PluginManagerDialog

@pytest.mark.ui
class TestMainWindow:
    """Test suite for MainWindow."""

    @pytest.fixture
    def main_window(self, app, assistant):
        """Create main window instance."""
        window = MainWindow(assistant, {})
        window.show()
        return window

    def test_window_initialization(self, main_window):
        """Test window initialization and basic properties."""
        assert main_window.windowTitle() == "Jarvis AI Assistant"
        assert main_window.assistant is not None
        assert main_window.chat_history is not None
        assert main_window.input_text is not None
        assert main_window.send_button is not None
        assert main_window.mic_button is not None

    def test_chat_interaction(self, main_window):
        """Test chat interface interaction."""
        # Test message input
        test_message = "Hello, Assistant!"
        QTest.keyClicks(main_window.input_text, test_message)
        assert main_window.input_text.toPlainText() == test_message

        # Test send button
        with patch.object(main_window, '_send_message') as mock_send:
            QTest.mouseClick(main_window.send_button, Qt.MouseButton.LeftButton)
            mock_send.assert_called_once()

    def test_message_display(self, main_window):
        """Test message display in chat history."""
        # Add user message
        main_window._add_message("Test message", is_user=True)
        
        # Add assistant message
        main_window._add_message("Test response", is_user=False)
        
        # Verify messages are displayed
        history_text = main_window.chat_history.toPlainText()
        assert "Test message" in history_text
        assert "Test response" in history_text

    def test_voice_interaction(self, main_window):
        """Test voice interaction buttons."""
        # Test mic button toggle
        assert not main_window.mic_button.isChecked()
        QTest.mouseClick(main_window.mic_button, Qt.MouseButton.LeftButton)
        assert main_window.mic_button.isChecked()

        # Test mic button style changes
        assert "background-color: #dc3545" in main_window.mic_button.styleSheet()

    def test_menu_actions(self, main_window):
        """Test menu bar actions."""
        # Test settings action
        with patch.object(main_window, '_show_settings') as mock_settings:
            main_window.action_settings.trigger()
            mock_settings.assert_called_once()

        # Test plugin manager action
        with patch.object(main_window, '_show_plugin_manager') as mock_plugin:
            main_window.action_plugins.trigger()
            mock_plugin.assert_called_once()

@pytest.mark.ui
class TestSettingsDialog:
    """Test suite for SettingsDialog."""

    @pytest.fixture
    def settings_dialog(self, app):
        """Create settings dialog instance."""
        dialog = SettingsDialog()
        dialog.show()
        return dialog

    def test_dialog_initialization(self, settings_dialog):
        """Test dialog initialization and basic properties."""
        assert settings_dialog.windowTitle() == "Settings"
        assert settings_dialog.openai_key is not None
        assert settings_dialog.theme is not None
        assert settings_dialog.font_family is not None

    def test_settings_loading(self, settings_dialog, mock_config):
        """Test settings loading."""
        settings_dialog.load_settings()
        
        # Verify loaded values
        assert settings_dialog.theme.currentText() == "Light"
        assert settings_dialog.font_family.currentText() == "Segoe UI"
        assert settings_dialog.speech_rate.value() == 150

    def test_settings_saving(self, settings_dialog):
        """Test settings saving."""
        # Modify settings
        settings_dialog.theme.setCurrentText("Dark")
        settings_dialog.font_size.setValue(12)
        
        with patch('builtins.open', create=True) as mock_open:
            settings_dialog.save_settings()
            mock_open.assert_called()

    def test_api_key_handling(self, settings_dialog):
        """Test API key input handling."""
        # Test key masking
        test_key = "sk-test123"
        settings_dialog.openai_key.setText(test_key)
        assert settings_dialog.openai_key.echoMode() == settings_dialog.openai_key.EchoMode.Password
        assert settings_dialog.openai_key.text() == test_key

@pytest.mark.ui
class TestPluginManagerDialog:
    """Test suite for PluginManagerDialog."""

    @pytest.fixture
    def plugin_dialog(self, app, assistant):
        """Create plugin manager dialog instance."""
        dialog = PluginManagerDialog(assistant.plugin_manager)
        dialog.show()
        return dialog

    def test_dialog_initialization(self, plugin_dialog):
        """Test dialog initialization and basic properties."""
        assert plugin_dialog.windowTitle() == "Plugin Manager"
        assert plugin_dialog.plugin_table is not None
        assert plugin_dialog.details_text is not None
        assert plugin_dialog.commands_text is not None

    @pytest.mark.asyncio
    async def test_plugin_listing(self, plugin_dialog, mock_plugin):
        """Test plugin listing in table."""
        # Load a test plugin
        await plugin_dialog.plugin_manager.load_plugin(mock_plugin)
        await plugin_dialog.load_plugins()
        
        # Verify plugin is listed
        assert plugin_dialog.plugin_table.rowCount() > 0
        item = plugin_dialog.plugin_table.item(0, 0)
        assert item.text() == "MockPlugin"

    @pytest.mark.asyncio
    async def test_plugin_activation(self, plugin_dialog, mock_plugin):
        """Test plugin activation/deactivation."""
        # Load and select plugin
        await plugin_dialog.plugin_manager.load_plugin(mock_plugin)
        await plugin_dialog.load_plugins()
        
        # Test activation
        with patch.object(plugin_dialog, '_activate_plugin') as mock_activate:
            plugin_dialog.plugin_table.selectRow(0)
            button = plugin_dialog.plugin_table.cellWidget(0, 3).findChild(QPushButton)
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            mock_activate.assert_called_once()

    def test_plugin_details(self, plugin_dialog, mock_plugin):
        """Test plugin details display."""
        # Select plugin
        plugin_dialog.plugin_table.selectRow(0)
        
        # Verify details are displayed
        details_text = plugin_dialog.details_text.toPlainText()
        assert "MockPlugin" in details_text
        assert "Test plugin" in details_text

@pytest.mark.ui
class TestUIIntegration:
    """Test suite for UI component integration."""

    def test_settings_from_main(self, main_window):
        """Test settings dialog launch from main window."""
        with patch('ui.settings_dialog.SettingsDialog.exec') as mock_exec:
            main_window._show_settings()
            mock_exec.assert_called_once()

    def test_plugin_manager_from_main(self, main_window):
        """Test plugin manager launch from main window."""
        with patch('ui.plugin_manager_dialog.PluginManagerDialog.exec') as mock_exec:
            main_window._show_plugin_manager()
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_command_processing_flow(self, main_window):
        """Test complete command processing flow."""
        # Input command
        test_command = "tell me a joke"
        main_window.input_text.setPlainText(test_command)
        
        # Process command
        with patch.object(main_window.assistant, 'process_command') as mock_process:
            mock_process.return_value = {
                "success": True,
                "message": "Test response"
            }
            
            await main_window._process_command(test_command)
            
            # Verify command processing
            mock_process.assert_called_with(test_command)
            
            # Verify response display
            assert "Test response" in main_window.chat_history.toPlainText()

    def test_style_application(self, main_window):
        """Test style sheet application."""
        # Verify main window styling
        assert "QMainWindow" in main_window.styleSheet()
        
        # Verify chat history styling
        assert main_window.chat_history.styleSheet() != ""
        
        # Verify button styling
        assert main_window.send_button.styleSheet() != ""
        assert main_window.mic_button.styleSheet() != ""

if __name__ == "__main__":
    pytest.main(["-v", __file__])
