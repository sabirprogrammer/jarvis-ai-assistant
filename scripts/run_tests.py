#!/usr/bin/env python3
"""
Test runner script for Jarvis AI Assistant.
This script provides utilities for running tests with various configurations
and generating reports.
"""

import os
import sys
import argparse
import subprocess
import webbrowser
from pathlib import Path
from typing import List, Optional, Dict
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
TESTS_DIR = PROJECT_ROOT / "tests"
REPORTS_DIR = PROJECT_ROOT / "reports"
COVERAGE_DIR = REPORTS_DIR / "coverage"
JUNIT_DIR = REPORTS_DIR / "junit"

class TestRunner:
    """Test runner utility class."""
    
    def __init__(self):
        """Initialize test runner."""
        self.setup_directories()
        self.test_results: Dict = {}
        
    def setup_directories(self) -> None:
        """Create necessary directories."""
        REPORTS_DIR.mkdir(exist_ok=True)
        COVERAGE_DIR.mkdir(exist_ok=True)
        JUNIT_DIR.mkdir(exist_ok=True)
    
    def run_command(self, command: List[str]) -> subprocess.CompletedProcess:
        """Run a command and handle its output."""
        try:
            return subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(command)}")
            logger.error(f"Error output: {e.stderr}")
            raise
    
    def run_tests(self, args: argparse.Namespace) -> bool:
        """Run tests with specified configuration."""
        try:
            start_time = datetime.now()
            
            # Build pytest command
            cmd = ["pytest"]
            
            # Add verbosity
            if args.verbose:
                cmd.append("-v")
            
            # Add test selection
            if args.test_path:
                cmd.append(str(args.test_path))
            else:
                cmd.append("tests/")
            
            # Add markers
            if args.markers:
                cmd.extend(["-m", args.markers])
            
            # Add coverage
            if args.coverage:
                cmd.extend([
                    f"--cov={args.coverage_source}",
                    "--cov-report=term-missing",
                    f"--cov-report=html:{COVERAGE_DIR}",
                    "--cov-branch"
                ])
            
            # Add JUnit report
            if args.junit:
                cmd.extend([
                    f"--junitxml={JUNIT_DIR}/test-results.xml"
                ])
            
            # Add last failed
            if args.last_failed:
                cmd.append("--lf")
            
            # Add failed first
            if args.failed_first:
                cmd.append("--ff")
            
            # Add parallel execution
            if args.parallel:
                cmd.extend(["-n", str(args.parallel)])
            
            # Run tests
            logger.info(f"Running tests: {' '.join(cmd)}")
            result = self.run_command(cmd)
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            
            # Store results
            self.test_results = {
                "command": " ".join(cmd),
                "success": True,
                "duration": duration,
                "output": result.stdout,
                "timestamp": datetime.now().isoformat()
            }
            
            # Generate report
            self.generate_report()
            
            # Open coverage report if requested
            if args.coverage and args.show_coverage:
                webbrowser.open(str(COVERAGE_DIR / "index.html"))
            
            logger.info(f"Tests completed in {duration:.2f} seconds")
            return True
            
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            self.test_results = {
                "command": " ".join(cmd),
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            return False
    
    def generate_report(self) -> None:
        """Generate test execution report."""
        report_file = REPORTS_DIR / f"test-report-{datetime.now():%Y%m%d-%H%M%S}.json"
        with open(report_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        logger.info(f"Test report generated: {report_file}")

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Jarvis AI Assistant Test Runner")
    
    parser.add_argument(
        "--test-path",
        type=Path,
        help="Specific test path to run"
    )
    
    parser.add_argument(
        "-m", "--markers",
        help="Only run tests matching given markers"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "-c", "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    
    parser.add_argument(
        "--coverage-source",
        default=".",
        help="Source directory for coverage analysis"
    )
    
    parser.add_argument(
        "--show-coverage",
        action="store_true",
        help="Open coverage report in browser"
    )
    
    parser.add_argument(
        "--junit",
        action="store_true",
        help="Generate JUnit XML report"
    )
    
    parser.add_argument(
        "--last-failed",
        action="store_true",
        help="Run only last failed tests"
    )
    
    parser.add_argument(
        "--failed-first",
        action="store_true",
        help="Run failed tests first"
    )
    
    parser.add_argument(
        "-n", "--parallel",
        type=int,
        help="Number of parallel test processes"
    )
    
    return parser.parse_args()

def main():
    """Main function to run tests."""
    args = parse_args()
    
    runner = TestRunner()
    success = runner.run_tests(args)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
