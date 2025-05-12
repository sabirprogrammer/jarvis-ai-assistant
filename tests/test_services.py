"""
Tests for service components (weather, news, system monitoring, etc.).
"""
import pytest
from unittest.mock import MagicMock, patch
import asyncio
from datetime import datetime, timedelta
import json

from services.weather_service import WeatherService
from services.news_service import NewsService
from services.system_monitor import SystemMonitor
from services.openai_service import OpenAIService
from services.google_service import GoogleService
from services.speech import SpeechService

@pytest.mark.service
class TestWeatherService:
    """Test suite for WeatherService."""

    @pytest.fixture
    def weather_config(self):
        return {
            "api_key": "test_key",
            "units": "metric",
            "update_interval": 1800
        }

    @pytest.mark.asyncio
    async def test_weather_fetch(self, weather_config, mock_weather_api):
        """Test weather data fetching."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.json = \
                asyncio.coroutine(lambda: mock_weather_api.data)
            
            service = WeatherService(weather_config)
            weather = await service.get_weather("London")
            
            assert weather["temperature"]["current"] == 20
            assert weather["condition"]["description"] == "Clear sky"
            assert weather["humidity"] == 65

    @pytest.mark.asyncio
    async def test_weather_caching(self, weather_config):
        """Test weather data caching."""
        service = WeatherService(weather_config)
        
        # Mock cache data
        service.cache = {
            "London": {
                "data": {"temperature": 20},
                "timestamp": datetime.now()
            }
        }
        
        # Should return cached data
        weather = await service.get_weather("London")
        assert weather["temperature"] == 20
        
        # Expire cache
        service.cache["London"]["timestamp"] = \
            datetime.now() - timedelta(hours=1)
        
        # Should fetch new data
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.json = \
                asyncio.coroutine(lambda: {"temperature": 25})
            
            weather = await service.get_weather("London")
            assert weather["temperature"] == 25

@pytest.mark.service
class TestNewsService:
    """Test suite for NewsService."""

    @pytest.fixture
    def news_config(self):
        return {
            "api_key": "test_key",
            "update_interval": 3600,
            "max_articles": 10
        }

    @pytest.mark.asyncio
    async def test_news_fetch(self, news_config, mock_news_api):
        """Test news fetching."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value.json = \
                asyncio.coroutine(lambda: {"articles": mock_news_api.articles})
            
            service = NewsService(news_config)
            articles = await service.get_headlines()
            
            assert len(articles) == 2
            assert articles[0]["title"] == "Test Article 1"
            assert articles[1]["title"] == "Test Article 2"

    @pytest.mark.asyncio
    async def test_news_filtering(self, news_config, mock_news_api):
        """Test news filtering and sorting."""
        service = NewsService(news_config)
        
        # Test category filtering
        articles = await service.get_headlines(category="technology")
        assert all("technology" in article["url"] for article in articles)
        
        # Test sorting by date
        articles = await service.get_headlines(sort_by="date")
        dates = [article["published_at"] for article in articles]
        assert dates == sorted(dates, reverse=True)

@pytest.mark.service
class TestSystemMonitor:
    """Test suite for SystemMonitor."""

    @pytest.mark.asyncio
    async def test_system_stats(self, mock_system_stats):
        """Test system statistics collection."""
        with patch('psutil.cpu_percent') as mock_cpu, \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            mock_cpu.return_value = mock_system_stats.stats["cpu_percent"]
            mock_memory.return_value.percent = mock_system_stats.stats["memory_percent"]
            mock_disk.return_value.percent = mock_system_stats.stats["disk_usage"][0]["percent"]
            
            monitor = SystemMonitor()
            stats = await monitor.get_status()
            
            assert stats["cpu_percent"] == 25.5
            assert stats["memory_percent"] == 45.2
            assert stats["disk_usage"][0]["percent"] == 50.0

    @pytest.mark.asyncio
    async def test_alert_thresholds(self):
        """Test system alert thresholds."""
        monitor = SystemMonitor()
        monitor.cpu_threshold = 80
        monitor.memory_threshold = 90
        
        with patch('psutil.cpu_percent', return_value=85), \
             patch('psutil.virtual_memory') as mock_memory:
            mock_memory.return_value.percent = 95
            
            alerts = await monitor.check_alerts()
            assert "CPU usage" in alerts
            assert "Memory usage" in alerts

@pytest.mark.service
class TestOpenAIService:
    """Test suite for OpenAIService."""

    @pytest.fixture
    def openai_config(self):
        return {
            "api_key": "test_key",
            "model": "gpt-3.5-turbo",
            "max_tokens": 150,
            "temperature": 0.7
        }

    @pytest.mark.asyncio
    async def test_text_generation(self, openai_config):
        """Test text generation."""
        with patch('openai.ChatCompletion.acreate') as mock_create:
            mock_create.return_value = {
                "choices": [{
                    "message": {"content": "Generated response"}
                }]
            }
            
            service = OpenAIService(openai_config)
            response = await service.generate_response("Test prompt")
            
            assert response == "Generated response"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling(self, openai_config):
        """Test API error handling."""
        service = OpenAIService(openai_config)
        
        with patch('openai.ChatCompletion.acreate', 
                  side_effect=Exception("API Error")):
            with pytest.raises(Exception):
                await service.generate_response("Test prompt")

@pytest.mark.service
class TestSpeechService:
    """Test suite for SpeechService."""

    @pytest.fixture
    def speech_config(self):
        return {
            "language": "en-US",
            "rate": 150,
            "volume": 1.0
        }

    def test_text_to_speech(self, speech_config):
        """Test text-to-speech conversion."""
        with patch('pyttsx3.init') as mock_init:
            mock_engine = MagicMock()
            mock_init.return_value = mock_engine
            
            service = SpeechService(speech_config)
            service.speak("Test message")
            
            mock_engine.say.assert_called_with("Test message")
            mock_engine.runAndWait.assert_called_once()

    @pytest.mark.asyncio
    async def test_speech_recognition(self, speech_config):
        """Test speech recognition."""
        with patch('speech_recognition.Recognizer') as mock_recognizer:
            mock_instance = MagicMock()
            mock_recognizer.return_value = mock_instance
            mock_instance.recognize_google.return_value = "Test speech"
            
            service = SpeechService(speech_config)
            text = await service.recognize_speech()
            
            assert text == "Test speech"

@pytest.mark.service
class TestGoogleService:
    """Test suite for GoogleService."""

    @pytest.fixture
    def google_config(self):
        return {
            "client_secrets_file": "test_secrets.json",
            "scopes": [
                "https://www.googleapis.com/auth/calendar.readonly",
                "https://www.googleapis.com/auth/gmail.send"
            ]
        }

    @pytest.mark.asyncio
    async def test_calendar_events(self, google_config):
        """Test calendar events fetching."""
        with patch('googleapiclient.discovery.build') as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.events().list().execute.return_value = {
                "items": [
                    {
                        "summary": "Test Event",
                        "start": {"dateTime": "2023-01-01T10:00:00Z"}
                    }
                ]
            }
            
            service = GoogleService(google_config)
            events = await service.get_calendar_events()
            
            assert len(events) == 1
            assert events[0]["summary"] == "Test Event"

    @pytest.mark.asyncio
    async def test_email_sending(self, google_config):
        """Test email sending."""
        with patch('googleapiclient.discovery.build') as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            
            service = GoogleService(google_config)
            await service.send_email(
                to="test@example.com",
                subject="Test Subject",
                body="Test Body"
            )
            
            mock_service.users().messages().send.assert_called_once()

if __name__ == "__main__":
    pytest.main(["-v", __file__])
