"""
Pytest configuration and fixtures.
"""
import os
import sys
import pytest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
import yaml

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

from core.assistant import Assistant
from utils.db_manager import db_manager

@pytest.fixture(scope="session")
def app():
    """Create QApplication instance for UI tests."""
    app = QApplication([])
    yield app
    app.quit()

@pytest.fixture
def assistant():
    """Create Assistant instance for testing."""
    # Load test configuration
    config_path = Path(project_root) / "config" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Override settings for testing
    config["development"]["debug_mode"] = True
    config["database"]["sqlite"]["path"] = ":memory:"
    
    # Create assistant instance
    assistant = Assistant(config)
    yield assistant
    assistant.shutdown()

@pytest.fixture
def db():
    """Create in-memory database for testing."""
    # Configure database for testing
    db_manager.initialize(":memory:")
    yield db_manager
    db_manager.close()

@pytest.fixture
def temp_dir(tmp_path):
    """Create temporary directory for file operations."""
    return tmp_path

@pytest.fixture
def mock_config(temp_dir):
    """Create mock configuration for testing."""
    config = {
        "openai": {
            "api_key": "test-key",
            "model": "gpt-3.5-turbo"
        },
        "development": {
            "debug_mode": True
        },
        "database": {
            "type": "sqlite",
            "sqlite": {
                "path": ":memory:"
            }
        }
    }
    
    config_path = temp_dir / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    
    return config

@pytest.fixture
def mock_plugin():
    """Create mock plugin for testing."""
    from plugins.base_plugin import BasePlugin
    
    class MockPlugin(BasePlugin):
        async def initialize(self):
            self.name = "MockPlugin"
            self.description = "Test plugin"
            return True
            
        async def process_command(self, command, context=None):
            return {
                "success": True,
                "message": "Mock response"
            }
    
    return MockPlugin

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_weather_api():
    """Mock weather API responses."""
    class MockWeatherResponse:
        def __init__(self):
            self.data = {
                "temperature": {"current": 20, "min": 15, "max": 25},
                "condition": {"description": "Clear sky", "code": 800},
                "humidity": 65,
                "wind": {"speed": 5.5, "direction": "NE"},
                "pressure": 1015
            }
            
        async def get_weather(self, city):
            return self.data
            
    return MockWeatherResponse()

@pytest.fixture
def mock_news_api():
    """Mock news API responses."""
    class MockNewsResponse:
        def __init__(self):
            self.articles = [
                {
                    "title": "Test Article 1",
                    "description": "Test Description 1",
                    "url": "http://test1.com",
                    "published_at": "2023-01-01T12:00:00Z"
                },
                {
                    "title": "Test Article 2",
                    "description": "Test Description 2",
                    "url": "http://test2.com",
                    "published_at": "2023-01-01T13:00:00Z"
                }
            ]
            
        async def get_headlines(self):
            return self.articles
            
    return MockNewsResponse()

@pytest.fixture
def mock_system_stats():
    """Mock system monitoring stats."""
    class MockSystemStats:
        def __init__(self):
            self.stats = {
                "cpu_percent": 25.5,
                "memory_percent": 45.2,
                "disk_usage": [
                    {
                        "device": "/dev/sda1",
                        "mountpoint": "/",
                        "total": 1000000,
                        "used": 500000,
                        "free": 500000,
                        "percent": 50.0
                    }
                ],
                "network": {
                    "bytes_sent": 1000,
                    "bytes_recv": 2000
                }
            }
            
        async def get_status(self):
            return self.stats
            
    return MockSystemStats()

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: mark test as slow")
    config.addinivalue_line("markers", "integration: mark as integration test")
    config.addinivalue_line("markers", "ui: mark as UI test")
    config.addinivalue_line("markers", "network: mark as requiring network")
    config.addinivalue_line("markers", "plugin: mark as plugin test")
    config.addinivalue_line("markers", "service: mark as service test")
    config.addinivalue_line("markers", "core: mark as core functionality test")
    config.addinivalue_line("markers", "utils: mark as utility test")

def pytest_collection_modifyitems(config, items):
    """Modify test items based on markers and configuration."""
    # Skip slow tests unless explicitly requested
    if not config.getoption("--runslow"):
        skip_slow = pytest.mark.skip(reason="need --runslow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
    
    # Skip network tests if offline mode
    if config.getoption("--offline"):
        skip_network = pytest.mark.skip(reason="test requires network access")
        for item in items:
            if "network" in item.keywords:
                item.add_marker(skip_network)

def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )
    parser.addoption(
        "--offline", action="store_true", default=False, help="run in offline mode"
    )
