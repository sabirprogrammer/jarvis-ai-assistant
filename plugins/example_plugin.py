from typing import Dict, Any, Optional
import re
from datetime import datetime
import random

from plugins.base_plugin import BasePlugin
from utils.logger import logger

class JokePlugin(BasePlugin):
    """Example plugin that tells jokes"""

    def __init__(self, assistant):
        super().__init__(assistant)
        self.name = "JokePlugin"
        self.description = "Tells random jokes"
        self.version = "1.0.0"
        self.author = "Jarvis Team"
        
        # List of sample jokes
        self.jokes = [
            "Why don't programmers like nature? It has too many bugs!",
            "What do you call a bear with no teeth? A gummy bear!",
            "Why don't scientists trust atoms? Because they make up everything!",
            "What do you call fake spaghetti? An impasta!",
            "Why did the scarecrow win an award? He was outstanding in his field!"
        ]

    async def initialize(self) -> bool:
        """Initialize the plugin"""
        try:
            # Register command patterns
            self.register_command(
                "tell (me )?(a )?joke",
                "Tells a random joke"
            )
            self.register_command(
                "make me laugh",
                "Tells a random joke"
            )
            
            self.is_active = True
            logger.info(f"{self.name} initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing {self.name}: {str(e)}")
            return False

    async def process_command(self, command: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a command"""
        try:
            # Select a random joke
            joke = random.choice(self.jokes)
            
            return {
                'success': True,
                'message': joke,
                'type': 'joke',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return await self.handle_error(e)

class TimePlugin(BasePlugin):
    """Example plugin that handles time-related commands"""

    def __init__(self, assistant):
        super().__init__(assistant)
        self.name = "TimePlugin"
        self.description = "Handles time-related commands"
        self.version = "1.0.0"
        self.author = "Jarvis Team"

    async def initialize(self) -> bool:
        """Initialize the plugin"""
        try:
            # Register command patterns
            self.register_command(
                "what('s| is) the time",
                "Tells the current time"
            )
            self.register_command(
                "what('s| is) today('s| is) date",
                "Tells today's date"
            )
            
            self.is_active = True
            logger.info(f"{self.name} initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing {self.name}: {str(e)}")
            return False

    async def process_command(self, command: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a command"""
        try:
            now = datetime.now()
            
            if re.search(r"time", command, re.IGNORECASE):
                return {
                    'success': True,
                    'message': f"The current time is {now.strftime('%I:%M %p')}",
                    'type': 'time',
                    'timestamp': now.isoformat()
                }
            elif re.search(r"date", command, re.IGNORECASE):
                return {
                    'success': True,
                    'message': f"Today's date is {now.strftime('%B %d, %Y')}",
                    'type': 'date',
                    'timestamp': now.isoformat()
                }
            else:
                return {
                    'success': False,
                    'message': "I don't understand that time-related command",
                    'type': 'error',
                    'timestamp': now.isoformat()
                }
                
        except Exception as e:
            return await self.handle_error(e)

class CalculatorPlugin(BasePlugin):
    """Example plugin that handles basic calculations"""

    def __init__(self, assistant):
        super().__init__(assistant)
        self.name = "CalculatorPlugin"
        self.description = "Performs basic calculations"
        self.version = "1.0.0"
        self.author = "Jarvis Team"

    async def initialize(self) -> bool:
        """Initialize the plugin"""
        try:
            # Register command patterns
            self.register_command(
                "calculate",
                "Performs a calculation"
            )
            self.register_command(
                "what('s| is) \\d+( )?[+\\-*/]( )?\\d+",
                "Performs a calculation"
            )
            
            self.is_active = True
            logger.info(f"{self.name} initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing {self.name}: {str(e)}")
            return False

    async def process_command(self, command: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a command"""
        try:
            # Extract numbers and operator
            match = re.search(r"(\d+)\s*([+\-*/])\s*(\d+)", command)
            if not match:
                return {
                    'success': False,
                    'message': "I couldn't understand the calculation",
                    'type': 'error',
                    'timestamp': datetime.now().isoformat()
                }
            
            num1 = float(match.group(1))
            operator = match.group(2)
            num2 = float(match.group(3))
            
            # Perform calculation
            if operator == '+':
                result = num1 + num2
            elif operator == '-':
                result = num1 - num2
            elif operator == '*':
                result = num1 * num2
            elif operator == '/':
                if num2 == 0:
                    return {
                        'success': False,
                        'message': "Cannot divide by zero",
                        'type': 'error',
                        'timestamp': datetime.now().isoformat()
                    }
                result = num1 / num2
            
            return {
                'success': True,
                'message': f"The result is {result}",
                'type': 'calculation',
                'result': result,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return await self.handle_error(e)

# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test():
        # Create a mock assistant
        class MockAssistant:
            pass
        
        assistant = MockAssistant()
        
        # Test JokePlugin
        joke_plugin = JokePlugin(assistant)
        if await joke_plugin.initialize():
            response = await joke_plugin.process_command("tell me a joke")
            print("\nJoke Plugin Test:")
            print(response['message'])
        
        # Test TimePlugin
        time_plugin = TimePlugin(assistant)
        if await time_plugin.initialize():
            response = await time_plugin.process_command("what's the time")
            print("\nTime Plugin Test:")
            print(response['message'])
            
            response = await time_plugin.process_command("what's today's date")
            print("\nDate Plugin Test:")
            print(response['message'])
        
        # Test CalculatorPlugin
        calc_plugin = CalculatorPlugin(assistant)
        if await calc_plugin.initialize():
            response = await calc_plugin.process_command("what's 5 + 3")
            print("\nCalculator Plugin Test:")
            print(response['message'])
    
    # Run async tests
    asyncio.run(test())
