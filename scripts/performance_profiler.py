#!/usr/bin/env python3
"""
Performance profiling tools for Jarvis AI Assistant.
This script provides utilities for profiling application performance,
analyzing bottlenecks, and generating optimization reports.
"""

import os
import sys
import argparse
from pathlib import Path
import logging
import json
from typing import Dict, List, Optional, Set, Union, Callable
import cProfile
import pstats
import time
import tracemalloc
import psutil
import asyncio
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from memory_profiler import profile as memory_profile
import line_profiler
import objgraph
from guppy3 import hpy
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "performance"
PROFILE_DIR = REPORTS_DIR / "profiles"

class PerformanceProfiler:
    """Performance profiling utility class."""
    
    def __init__(self):
        """Initialize performance profiler."""
        self.reports_dir = REPORTS_DIR
        self.profile_dir = PROFILE_DIR
        
        # Create necessary directories
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.profile_dir.mkdir(exist_ok=True)
    
    def profile_function(
        self,
        func: Callable,
        *args,
        profile_memory: bool = False,
        **kwargs
    ) -> Dict:
        """Profile a function's performance."""
        results = {
            "time": {},
            "memory": {},
            "calls": {}
        }
        
        # Time profiling
        profiler = cProfile.Profile()
        profiler.enable()
        
        # Memory tracking
        if profile_memory:
            tracemalloc.start()
            memory_before = psutil.Process().memory_info().rss
        
        # Execute function
        start_time = time.time()
        try:
            result = profiler.runcall(func, *args, **kwargs)
        finally:
            end_time = time.time()
            profiler.disable()
        
        # Process time profiling results
        stats = pstats.Stats(profiler)
        results["time"]["total"] = end_time - start_time
        
        # Get function statistics
        func_stats = {}
        for key, value in stats.stats.items():
            func_name = f"{key[0]}:{key[1]}({key[2]})"
            func_stats[func_name] = {
                "calls": value[0],
                "total_time": value[2],
                "per_call": value[3]
            }
        results["calls"] = func_stats
        
        # Memory profiling results
        if profile_memory:
            memory_after = psutil.Process().memory_info().rss
            snapshot = tracemalloc.take_snapshot()
            tracemalloc.stop()
            
            results["memory"] = {
                "total_increase": memory_after - memory_before,
                "detailed": [
                    {
                        "size": stat.size,
                        "count": stat.count,
                        "traceback": str(stat.traceback)
                    }
                    for stat in snapshot.statistics("lineno")[:10]
                ]
            }
        
        return results
    
    def profile_memory_usage(self, duration: int = 60) -> Dict:
        """Profile system-wide memory usage over time."""
        results = {
            "timestamps": [],
            "memory_usage": [],
            "swap_usage": [],
            "process_memory": []
        }
        
        process = psutil.Process()
        start_time = time.time()
        
        try:
            with tqdm(total=duration, desc="Profiling memory") as pbar:
                while time.time() - start_time < duration:
                    # System memory
                    memory = psutil.virtual_memory()
                    swap = psutil.swap_memory()
                    
                    results["timestamps"].append(time.time() - start_time)
                    results["memory_usage"].append(memory.percent)
                    results["swap_usage"].append(swap.percent)
                    results["process_memory"].append(
                        process.memory_info().rss / 1024 / 1024  # MB
                    )
                    
                    time.sleep(1)
                    pbar.update(1)
        
        except KeyboardInterrupt:
            pass
        
        return results
    
    def profile_cpu_usage(self, duration: int = 60) -> Dict:
        """Profile CPU usage over time."""
        results = {
            "timestamps": [],
            "cpu_usage": [],
            "per_cpu": [],
            "process_cpu": []
        }
        
        process = psutil.Process()
        start_time = time.time()
        
        try:
            with tqdm(total=duration, desc="Profiling CPU") as pbar:
                while time.time() - start_time < duration:
                    results["timestamps"].append(time.time() - start_time)
                    results["cpu_usage"].append(psutil.cpu_percent())
                    results["per_cpu"].append(psutil.cpu_percent(percpu=True))
                    results["process_cpu"].append(process.cpu_percent())
                    
                    time.sleep(1)
                    pbar.update(1)
        
        except KeyboardInterrupt:
            pass
        
        return results
    
    def analyze_object_graph(self) -> Dict:
        """Analyze object references and memory usage."""
        results = {
            "most_common": [],
            "by_type": {},
            "growth": [],
            "leaks": []
        }
        
        # Get most common types
        results["most_common"] = [
            {
                "type": type_name,
                "count": count
            }
            for type_name, count in objgraph.most_common_types(limit=20)
        ]
        
        # Get object counts by type
        for type_name in [obj["type"] for obj in results["most_common"]]:
            try:
                results["by_type"][type_name] = len(objgraph.by_type(type_name))
            except Exception:
                continue
        
        # Analyze memory leaks
        objgraph.growth(limit=10)  # Prime the growth data
        time.sleep(1)  # Wait for changes
        growth_data = objgraph.growth(limit=10)
        
        results["growth"] = [
            {
                "type": type_name,
                "count": count,
                "delta": delta
            }
            for type_name, count, delta in growth_data
        ]
        
        # Find potential memory leaks
        hp = hpy()
        heap = hp.heap()
        
        results["leaks"] = [
            {
                "type": str(obj.bytype),
                "size": obj.size,
                "count": obj.count
            }
            for obj in heap.bytype[:10]
        ]
        
        return results
    
    def generate_report(
        self,
        profile_results: Optional[Dict] = None,
        memory_results: Optional[Dict] = None,
        cpu_results: Optional[Dict] = None,
        object_results: Optional[Dict] = None
    ) -> Path:
        """Generate performance analysis report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f"performance_report_{timestamp}.html"
        
        content = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Performance Analysis Report</title>",
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
            "<h1>Performance Analysis Report</h1>",
            f"<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        ]
        
        # Function profiling section
        if profile_results:
            content.extend([
                "<div class='section'>",
                "<h2>Function Performance Profile</h2>",
                f"<p>Total Execution Time: {profile_results['time']['total']:.3f} seconds</p>",
                "<h3>Function Calls</h3>",
                "<table>",
                "<tr><th>Function</th><th>Calls</th><th>Total Time</th>"
                "<th>Time per Call</th></tr>"
            ])
            
            for func, stats in sorted(
                profile_results["calls"].items(),
                key=lambda x: x[1]["total_time"],
                reverse=True
            )[:20]:
                content.append(
                    f"<tr><td>{func}</td><td>{stats['calls']}</td>"
                    f"<td>{stats['total_time']:.3f}s</td>"
                    f"<td>{stats['per_call']:.6f}s</td></tr>"
                )
            
            content.append("</table>")
            
            if "memory" in profile_results and profile_results["memory"]:
                content.extend([
                    "<h3>Memory Usage</h3>",
                    f"<p>Total Memory Increase: {profile_results['memory']['total_increase'] / 1024 / 1024:.2f} MB</p>",
                    "<h4>Top Memory Allocations</h4>",
                    "<table>",
                    "<tr><th>Size</th><th>Count</th><th>Location</th></tr>"
                ])
                
                for stat in profile_results["memory"]["detailed"]:
                    content.append(
                        f"<tr><td>{stat['size'] / 1024:.2f} KB</td>"
                        f"<td>{stat['count']}</td><td>{stat['traceback']}</td></tr>"
                    )
                
                content.append("</table>")
            
            content.append("</div>")
        
        # Memory usage section
        if memory_results:
            plt.figure(figsize=(10, 6))
            plt.plot(
                memory_results["timestamps"],
                memory_results["memory_usage"],
                label="System Memory"
            )
            plt.plot(
                memory_results["timestamps"],
                memory_results["swap_usage"],
                label="Swap Usage"
            )
            plt.plot(
                memory_results["timestamps"],
                memory_results["process_memory"],
                label="Process Memory (MB)"
            )
            plt.title("Memory Usage Over Time")
            plt.xlabel("Time (seconds)")
            plt.ylabel("Usage (%)")
            plt.legend()
            plt.grid(True)
            plt.savefig(self.reports_dir / "memory_usage.png")
            plt.close()
            
            content.extend([
                "<div class='section'>",
                "<h2>Memory Usage Profile</h2>",
                "<img src='memory_usage.png' class='chart'>",
                "</div>"
            ])
        
        # CPU usage section
        if cpu_results:
            plt.figure(figsize=(10, 6))
            plt.plot(
                cpu_results["timestamps"],
                cpu_results["cpu_usage"],
                label="System CPU"
            )
            plt.plot(
                cpu_results["timestamps"],
                cpu_results["process_cpu"],
                label="Process CPU"
            )
            plt.title("CPU Usage Over Time")
            plt.xlabel("Time (seconds)")
            plt.ylabel("Usage (%)")
            plt.legend()
            plt.grid(True)
            plt.savefig(self.reports_dir / "cpu_usage.png")
            plt.close()
            
            # CPU cores heatmap
            if cpu_results["per_cpu"]:
                per_cpu_data = list(zip(*cpu_results["per_cpu"]))
                plt.figure(figsize=(12, 4))
                sns.heatmap(
                    per_cpu_data,
                    cmap="YlOrRd",
                    xticklabels=False,
                    yticklabels=[f"CPU {i}" for i in range(len(per_cpu_data))]
                )
                plt.title("CPU Core Usage Heatmap")
                plt.xlabel("Time")
                plt.savefig(self.reports_dir / "cpu_heatmap.png")
                plt.close()
            
            content.extend([
                "<div class='section'>",
                "<h2>CPU Usage Profile</h2>",
                "<img src='cpu_usage.png' class='chart'>",
                "<h3>CPU Core Usage</h3>",
                "<img src='cpu_heatmap.png' class='chart'>",
                "</div>"
            ])
        
        # Object analysis section
        if object_results:
            content.extend([
                "<div class='section'>",
                "<h2>Object Analysis</h2>",
                "<h3>Most Common Types</h3>",
                "<table>",
                "<tr><th>Type</th><th>Count</th></tr>"
            ])
            
            for obj in object_results["most_common"]:
                content.append(
                    f"<tr><td>{obj['type']}</td><td>{obj['count']}</td></tr>"
                )
            
            content.extend([
                "</table>",
                "<h3>Memory Growth</h3>",
                "<table>",
                "<tr><th>Type</th><th>Count</th><th>Delta</th></tr>"
            ])
            
            for obj in object_results["growth"]:
                content.append(
                    f"<tr><td>{obj['type']}</td><td>{obj['count']}</td>"
                    f"<td>{obj['delta']}</td></tr>"
                )
            
            content.extend([
                "</table>",
                "<h3>Potential Memory Leaks</h3>",
                "<table>",
                "<tr><th>Type</th><th>Size</th><th>Count</th></tr>"
            ])
            
            for obj in object_results["leaks"]:
                content.append(
                    f"<tr><td>{obj['type']}</td>"
                    f"<td>{obj['size'] / 1024:.2f} KB</td>"
                    f"<td>{obj['count']}</td></tr>"
                )
            
            content.extend([
                "</table>",
                "</div>"
            ])
        
        content.extend([
            "</body>",
            "</html>"
        ])
        
        report_file.write_text("\n".join(content))
        return report_file

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Jarvis AI Assistant Performance Profiler"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Profile memory command
    memory_parser = subparsers.add_parser(
        "memory",
        help="Profile memory usage"
    )
    memory_parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds"
    )
    
    # Profile CPU command
    cpu_parser = subparsers.add_parser(
        "cpu",
        help="Profile CPU usage"
    )
    cpu_parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds"
    )
    
    # Analyze objects command
    subparsers.add_parser(
        "objects",
        help="Analyze object graph"
    )
    
    # Profile function command
    function_parser = subparsers.add_parser(
        "function",
        help="Profile specific function"
    )
    function_parser.add_argument(
        "module",
        help="Module containing function"
    )
    function_parser.add_argument(
        "function",
        help="Function name to profile"
    )
    function_parser.add_argument(
        "--memory",
        action="store_true",
        help="Include memory profiling"
    )
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    profiler = PerformanceProfiler()
    
    try:
        if args.command == "memory":
            results = profiler.profile_memory_usage(args.duration)
            report_file = profiler.generate_report(memory_results=results)
            logger.info(f"Report generated: {report_file}")
        
        elif args.command == "cpu":
            results = profiler.profile_cpu_usage(args.duration)
            report_file = profiler.generate_report(cpu_results=results)
            logger.info(f"Report generated: {report_file}")
        
        elif args.command == "objects":
            results = profiler.analyze_object_graph()
            report_file = profiler.generate_report(object_results=results)
            logger.info(f"Report generated: {report_file}")
        
        elif args.command == "function":
            # Import target function
            sys.path.insert(0, str(PROJECT_ROOT))
            try:
                module = importlib.import_module(args.module)
                func = getattr(module, args.function)
            except Exception as e:
                logger.error(f"Error importing function: {e}")
                sys.exit(1)
            finally:
                sys.path.pop(0)
            
            # Profile function
            results = profiler.profile_function(func, profile_memory=args.memory)
            report_file = profiler.generate_report(profile_results=results)
            logger.info(f"Report generated: {report_file}")
        
        else:
            parser.print_help()
            sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
