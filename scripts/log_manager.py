#!/usr/bin/env python3
"""
Logging configuration and management tools for Jarvis AI Assistant.
This script provides utilities for setting up logging, managing log files,
and analyzing log data.
"""

import os
import sys
import argparse
from pathlib import Path
import logging
import logging.handlers
import json
import yaml
from typing import Dict, List, Optional, Set, Union
from datetime import datetime, timedelta
import re
import gzip
import shutil
from dataclasses import dataclass
import statistics
from collections import defaultdict
import concurrent.futures
from tqdm import tqdm
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
ARCHIVE_DIR = LOGS_DIR / "archive"
REPORTS_DIR = PROJECT_ROOT / "reports" / "logs"

@dataclass
class LogEntry:
    """Represents a parsed log entry."""
    timestamp: datetime
    level: str
    logger_name: str
    message: str
    exception: Optional[str] = None

class LogManager:
    """Logging management utility class."""
    
    def __init__(self):
        """Initialize log manager."""
        self.logs_dir = LOGS_DIR
        self.archive_dir = ARCHIVE_DIR
        self.reports_dir = REPORTS_DIR
        
        # Create necessary directories
        self.logs_dir.mkdir(exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Compile regex patterns
        self.log_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - '
            r'(\w+) - ([^-]+) - (.+?)(?:\n((?:Traceback.*?\n(?:.*\n)*?)?(?:.*Error.*)))?$',
            re.MULTILINE
        )
    
    def setup_logging(self, config: Dict) -> None:
        """Configure logging system."""
        # Reset logging configuration
        logging.getLogger().handlers.clear()
        
        # Create formatters
        formatters = {
            "default": logging.Formatter(
                config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            ),
            "simple": logging.Formatter("%(message)s")
        }
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(config.get("level", "INFO"))
        
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatters["default"])
        root_logger.addHandler(console_handler)
        
        # Add file handler
        log_file = self.logs_dir / config.get("file", "jarvis.log")
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=config.get("max_size", 10 * 1024 * 1024),  # 10MB default
            backupCount=config.get("backup_count", 5)
        )
        file_handler.setFormatter(formatters["default"])
        root_logger.addHandler(file_handler)
        
        # Configure module-specific loggers
        for module, module_config in config.get("modules", {}).items():
            module_logger = logging.getLogger(module)
            module_logger.setLevel(module_config.get("level", config["level"]))
            
            if module_config.get("file"):
                module_file = self.logs_dir / module_config["file"]
                module_handler = logging.handlers.RotatingFileHandler(
                    module_file,
                    maxBytes=module_config.get("max_size", config["max_size"]),
                    backupCount=module_config.get("backup_count", config["backup_count"])
                )
                module_handler.setFormatter(formatters["default"])
                module_logger.addHandler(module_handler)
    
    def parse_log_file(self, log_file: Path) -> List[LogEntry]:
        """Parse a log file into structured entries."""
        entries = []
        
        # Handle both plain and gzipped files
        open_func = gzip.open if log_file.suffix == '.gz' else open
        
        with open_func(log_file, 'rt') as f:
            content = f.read()
            matches = self.log_pattern.finditer(content)
            
            for match in matches:
                timestamp_str, level, logger_name, message, exception = match.groups()
                try:
                    timestamp = datetime.strptime(
                        timestamp_str,
                        "%Y-%m-%d %H:%M:%S,%f"
                    )
                    entries.append(LogEntry(
                        timestamp=timestamp,
                        level=level,
                        logger_name=logger_name.strip(),
                        message=message.strip(),
                        exception=exception.strip() if exception else None
                    ))
                except ValueError as e:
                    logger.warning(f"Error parsing timestamp {timestamp_str}: {e}")
        
        return entries
    
    def analyze_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """Analyze log files within date range."""
        results = {
            "total_entries": 0,
            "level_counts": defaultdict(int),
            "logger_counts": defaultdict(int),
            "error_counts": defaultdict(int),
            "hourly_distribution": defaultdict(int),
            "response_times": [],
            "exceptions": defaultdict(int)
        }
        
        # Get log files
        log_files = list(self.logs_dir.glob("*.log*"))
        log_files.extend(self.archive_dir.glob("*.log.gz"))
        
        # Process log files in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_file = {
                executor.submit(self.parse_log_file, file): file
                for file in log_files
            }
            
            for future in tqdm(
                concurrent.futures.as_completed(future_to_file),
                total=len(log_files),
                desc="Analyzing logs"
            ):
                file = future_to_file[future]
                try:
                    entries = future.result()
                    
                    for entry in entries:
                        # Apply date filter
                        if start_date and entry.timestamp < start_date:
                            continue
                        if end_date and entry.timestamp > end_date:
                            continue
                        
                        results["total_entries"] += 1
                        results["level_counts"][entry.level] += 1
                        results["logger_counts"][entry.logger_name] += 1
                        results["hourly_distribution"][entry.timestamp.hour] += 1
                        
                        # Track exceptions
                        if entry.exception:
                            error_type = entry.exception.split('\n')[0]
                            results["exceptions"][error_type] += 1
                        
                        # Extract response times
                        if "Response time:" in entry.message:
                            try:
                                time_str = entry.message.split("Response time:")[1].strip()
                                time_ms = float(time_str.replace("ms", ""))
                                results["response_times"].append(time_ms)
                            except (ValueError, IndexError):
                                pass
                        
                        # Track error patterns
                        if entry.level in {"ERROR", "CRITICAL"}:
                            results["error_counts"][entry.message] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing {file}: {e}")
        
        return results
    
    def generate_report(self, analysis: Dict, output_format: str = "html") -> Path:
        """Generate analysis report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if output_format == "html":
            report_file = self.reports_dir / f"log_analysis_{timestamp}.html"
            
            # Create visualizations
            plt.style.use('seaborn')
            
            # Level distribution
            plt.figure(figsize=(10, 6))
            plt.bar(analysis["level_counts"].keys(), analysis["level_counts"].values())
            plt.title("Log Level Distribution")
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(self.reports_dir / "level_distribution.png")
            plt.close()
            
            # Hourly distribution
            plt.figure(figsize=(12, 6))
            hours = range(24)
            counts = [analysis["hourly_distribution"][hour] for hour in hours]
            plt.plot(hours, counts)
            plt.title("Hourly Log Distribution")
            plt.xlabel("Hour of Day")
            plt.ylabel("Number of Logs")
            plt.grid(True)
            plt.tight_layout()
            plt.savefig(self.reports_dir / "hourly_distribution.png")
            plt.close()
            
            # Response time distribution
            if analysis["response_times"]:
                plt.figure(figsize=(10, 6))
                plt.hist(analysis["response_times"], bins=50)
                plt.title("Response Time Distribution")
                plt.xlabel("Response Time (ms)")
                plt.ylabel("Frequency")
                plt.tight_layout()
                plt.savefig(self.reports_dir / "response_times.png")
                plt.close()
            
            # Generate HTML report
            content = [
                "<!DOCTYPE html>",
                "<html>",
                "<head>",
                "<title>Log Analysis Report</title>",
                "<style>",
                "body { font-family: Arial, sans-serif; margin: 20px; }",
                ".section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; }",
                "table { border-collapse: collapse; width: 100%; }",
                "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
                "th { background-color: #f2f2f2; }",
                ".chart { margin: 20px 0; max-width: 800px; }",
                "</style>",
                "</head>",
                "<body>",
                "<h1>Log Analysis Report</h1>",
                f"<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
                
                "<div class='section'>",
                "<h2>Overview</h2>",
                f"<p>Total Entries: {analysis['total_entries']}</p>",
                
                "<h3>Log Level Distribution</h3>",
                "<img src='level_distribution.png' class='chart'>",
                
                "<h3>Hourly Distribution</h3>",
                "<img src='hourly_distribution.png' class='chart'>"
            ]
            
            if analysis["response_times"]:
                content.extend([
                    "<h3>Response Times</h3>",
                    "<img src='response_times.png' class='chart'>",
                    "<p>Statistics:</p>",
                    "<ul>",
                    f"<li>Average: {statistics.mean(analysis['response_times']):.2f} ms</li>",
                    f"<li>Median: {statistics.median(analysis['response_times']):.2f} ms</li>",
                    f"<li>95th Percentile: {statistics.quantiles(analysis['response_times'], n=20)[-1]:.2f} ms</li>",
                    "</ul>"
                ])
            
            content.extend([
                "<h3>Top Loggers</h3>",
                "<table>",
                "<tr><th>Logger</th><th>Count</th></tr>"
            ])
            
            for logger_name, count in sorted(
                analysis["logger_counts"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]:
                content.append(
                    f"<tr><td>{logger_name}</td><td>{count}</td></tr>"
                )
            
            content.append("</table>")
            
            if analysis["exceptions"]:
                content.extend([
                    "<h3>Top Exceptions</h3>",
                    "<table>",
                    "<tr><th>Exception</th><th>Count</th></tr>"
                ])
                
                for error, count in sorted(
                    analysis["exceptions"].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]:
                    content.append(
                        f"<tr><td>{error}</td><td>{count}</td></tr>"
                    )
                
                content.append("</table>")
            
            content.extend([
                "</div>",
                "</body>",
                "</html>"
            ])
            
            report_file.write_text("\n".join(content))
            
        else:  # JSON format
            report_file = self.reports_dir / f"log_analysis_{timestamp}.json"
            with open(report_file, 'w') as f:
                json.dump(analysis, f, indent=2, default=str)
        
        return report_file
    
    def archive_logs(self, days: int = 30) -> int:
        """Archive old log files."""
        cutoff_date = datetime.now() - timedelta(days=days)
        archived = 0
        
        for log_file in self.logs_dir.glob("*.log*"):
            try:
                # Skip already rotated logs
                if log_file.name.endswith(".gz"):
                    continue
                
                # Check file modification time
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff_date:
                    # Compress and move to archive
                    archive_path = self.archive_dir / f"{log_file.name}.gz"
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(archive_path, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    log_file.unlink()
                    archived += 1
                    
            except Exception as e:
                logger.error(f"Error archiving {log_file}: {e}")
        
        return archived
    
    def cleanup_logs(self, max_age_days: int = 365) -> int:
        """Remove old archived logs."""
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        removed = 0
        
        for archive_file in self.archive_dir.glob("*.log.gz"):
            try:
                mtime = datetime.fromtimestamp(archive_file.stat().st_mtime)
                if mtime < cutoff_date:
                    archive_file.unlink()
                    removed += 1
                    
            except Exception as e:
                logger.error(f"Error removing {archive_file}: {e}")
        
        return removed

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Jarvis AI Assistant Log Manager"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Setup logging command
    setup_parser = subparsers.add_parser("setup", help="Configure logging")
    setup_parser.add_argument(
        "config_file",
        type=Path,
        help="Logging configuration file"
    )
    
    # Analyze logs command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze logs")
    analyze_parser.add_argument(
        "--start-date",
        help="Start date (YYYY-MM-DD)"
    )
    analyze_parser.add_argument(
        "--end-date",
        help="End date (YYYY-MM-DD)"
    )
    analyze_parser.add_argument(
        "--format",
        choices=["html", "json"],
        default="html",
        help="Report format"
    )
    
    # Archive logs command
    archive_parser = subparsers.add_parser("archive", help="Archive old logs")
    archive_parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Archive logs older than days"
    )
    
    # Cleanup logs command
    cleanup_parser = subparsers.add_parser("cleanup", help="Remove old archives")
    cleanup_parser.add_argument(
        "--max-age",
        type=int,
        default=365,
        help="Remove archives older than days"
    )
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    manager = LogManager()
    
    try:
        if args.command == "setup":
            if not args.config_file.exists():
                logger.error(f"Configuration file not found: {args.config_file}")
                sys.exit(1)
            
            with open(args.config_file) as f:
                config = yaml.safe_load(f)
            
            manager.setup_logging(config)
            logger.info("Logging configured successfully")
        
        elif args.command == "analyze":
            start_date = None
            end_date = None
            
            if args.start_date:
                start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
            if args.end_date:
                end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
            
            analysis = manager.analyze_logs(start_date, end_date)
            report_file = manager.generate_report(analysis, args.format)
            logger.info(f"Analysis report generated: {report_file}")
        
        elif args.command == "archive":
            archived = manager.archive_logs(args.days)
            logger.info(f"Archived {archived} log files")
        
        elif args.command == "cleanup":
            removed = manager.cleanup_logs(args.max_age)
            logger.info(f"Removed {removed} old archive files")
        
        else:
            parser.print_help()
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
