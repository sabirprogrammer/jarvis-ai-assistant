#!/usr/bin/env python3
"""
Performance profiling and monitoring tools for Jarvis AI Assistant.
This script provides utilities for profiling code, monitoring memory usage,
and identifying performance bottlenecks.
"""

import os
import sys
import argparse
import cProfile
import pstats
import tracemalloc
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
import logging
import json
from datetime import datetime
import psutil
from memory_profiler import profile as memory_profile
import yappi
from guppy3 import hpy
import matplotlib.pyplot as plt
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
PROFILE_DIR = PROJECT_ROOT / "profiles"
REPORTS_DIR = PROJECT_ROOT / "reports" / "performance"

class PerformanceProfiler:
    """Performance profiling utility class."""
    
    def __init__(self):
        """Initialize profiler."""
        self.profile_dir = PROFILE_DIR
        self.reports_dir = REPORTS_DIR
        self.profile_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.process = psutil.Process()
    
    async def profile_function(self, func: Callable, *args, **kwargs) -> Dict:
        """Profile a function's execution."""
        results = {}
        
        # CPU profiling
        profiler = cProfile.Profile()
        profiler.enable()
        
        # Memory tracking
        tracemalloc.start()
        start_mem = tracemalloc.get_traced_memory()
        
        # Time tracking
        start_time = time.perf_counter()
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
        finally:
            end_time = time.perf_counter()
            end_mem = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            profiler.disable()
        
        # Process results
        stats = pstats.Stats(profiler)
        profile_path = self.profile_dir / f"profile_{func.__name__}_{int(time.time())}.stats"
        stats.dump_stats(str(profile_path))
        
        results.update({
            "function": func.__name__,
            "execution_time": end_time - start_time,
            "memory": {
                "peak": end_mem[1] / 1024 / 1024,  # MB
                "increment": (end_mem[0] - start_mem[0]) / 1024 / 1024  # MB
            },
            "profile_file": str(profile_path)
        })
        
        return results
    
    def monitor_system(self, duration: int = 60, interval: float = 1.0) -> Dict:
        """Monitor system performance."""
        metrics = {
            "cpu": [],
            "memory": [],
            "disk_io": [],
            "network_io": []
        }
        
        start_time = time.time()
        last_disk_io = psutil.disk_io_counters()
        last_net_io = psutil.net_io_counters()
        
        try:
            while time.time() - start_time < duration:
                # CPU usage
                metrics["cpu"].append(psutil.cpu_percent(interval=None))
                
                # Memory usage
                mem = psutil.virtual_memory()
                metrics["memory"].append(mem.percent)
                
                # Disk I/O
                disk_io = psutil.disk_io_counters()
                metrics["disk_io"].append({
                    "read": disk_io.read_bytes - last_disk_io.read_bytes,
                    "write": disk_io.write_bytes - last_disk_io.write_bytes
                })
                last_disk_io = disk_io
                
                # Network I/O
                net_io = psutil.net_io_counters()
                metrics["network_io"].append({
                    "sent": net_io.bytes_sent - last_net_io.bytes_sent,
                    "recv": net_io.bytes_recv - last_net_io.bytes_recv
                })
                last_net_io = net_io
                
                time.sleep(interval)
        
        except KeyboardInterrupt:
            pass
        
        return metrics
    
    def analyze_memory(self) -> Dict:
        """Analyze memory usage using guppy."""
        h = hpy()
        heap = h.heap()
        
        analysis = {
            "total_size": heap.size / 1024 / 1024,  # MB
            "by_type": [
                {
                    "type": str(item.name),
                    "count": item.count,
                    "size": item.size / 1024  # KB
                }
                for item in heap.byrcs
            ]
        }
        
        return analysis
    
    def generate_report(self, data: Dict, report_type: str) -> Path:
        """Generate performance report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f"{report_type}_report_{timestamp}.html"
        
        # Create report content
        content = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"<title>Performance Report - {report_type}</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f2f2f2; }",
            ".chart { margin: 20px 0; max-width: 800px; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>Performance Report - {report_type}</h1>",
            f"<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        ]
        
        if report_type == "profile":
            # Add function profiling results
            content.extend([
                "<h2>Function Profile</h2>",
                "<table>",
                "<tr><th>Metric</th><th>Value</th></tr>",
                f"<tr><td>Function</td><td>{data['function']}</td></tr>",
                f"<tr><td>Execution Time</td><td>{data['execution_time']:.4f} seconds</td></tr>",
                f"<tr><td>Peak Memory</td><td>{data['memory']['peak']:.2f} MB</td></tr>",
                f"<tr><td>Memory Increment</td><td>{data['memory']['increment']:.2f} MB</td></tr>",
                "</table>"
            ])
            
        elif report_type == "monitor":
            # Create performance charts
            self._create_performance_charts(data)
            
            # Add system monitoring results
            content.extend([
                "<h2>System Monitoring</h2>",
                "<div class='chart'><img src='cpu_usage.png' alt='CPU Usage'></div>",
                "<div class='chart'><img src='memory_usage.png' alt='Memory Usage'></div>",
                "<div class='chart'><img src='io_usage.png' alt='I/O Usage'></div>"
            ])
            
        elif report_type == "memory":
            # Add memory analysis results
            content.extend([
                "<h2>Memory Analysis</h2>",
                "<table>",
                "<tr><th>Type</th><th>Count</th><th>Size (KB)</th></tr>"
            ])
            
            for item in sorted(data["by_type"], key=lambda x: x["size"], reverse=True)[:20]:
                content.append(
                    f"<tr><td>{item['type']}</td><td>{item['count']}</td><td>{item['size']:.2f}</td></tr>"
                )
            
            content.append("</table>")
        
        content.extend([
            "</body>",
            "</html>"
        ])
        
        report_file.write_text("\n".join(content))
        return report_file
    
    def _create_performance_charts(self, data: Dict) -> None:
        """Create performance charts using matplotlib."""
        # CPU Usage
        plt.figure(figsize=(10, 6))
        plt.plot(data["cpu"])
        plt.title("CPU Usage")
        plt.xlabel("Time (seconds)")
        plt.ylabel("Usage (%)")
        plt.grid(True)
        plt.savefig(self.reports_dir / "cpu_usage.png")
        plt.close()
        
        # Memory Usage
        plt.figure(figsize=(10, 6))
        plt.plot(data["memory"])
        plt.title("Memory Usage")
        plt.xlabel("Time (seconds)")
        plt.ylabel("Usage (%)")
        plt.grid(True)
        plt.savefig(self.reports_dir / "memory_usage.png")
        plt.close()
        
        # I/O Usage
        plt.figure(figsize=(10, 6))
        disk_read = [x["read"] for x in data["disk_io"]]
        disk_write = [x["write"] for x in data["disk_io"]]
        net_recv = [x["recv"] for x in data["network_io"]]
        net_sent = [x["sent"] for x in data["network_io"]]
        
        plt.plot(disk_read, label="Disk Read")
        plt.plot(disk_write, label="Disk Write")
        plt.plot(net_recv, label="Network Recv")
        plt.plot(net_sent, label="Network Sent")
        plt.title("I/O Usage")
        plt.xlabel("Time (seconds)")
        plt.ylabel("Bytes")
        plt.legend()
        plt.grid(True)
        plt.savefig(self.reports_dir / "io_usage.png")
        plt.close()

async def profile_app():
    """Profile the main application."""
    from main import main
    
    profiler = PerformanceProfiler()
    
    # Profile main function
    results = await profiler.profile_function(main)
    report_file = profiler.generate_report(results, "profile")
    logger.info(f"Profile report generated: {report_file}")
    
    # Monitor system
    logger.info("Monitoring system performance...")
    metrics = profiler.monitor_system(duration=60)
    report_file = profiler.generate_report(metrics, "monitor")
    logger.info(f"Monitoring report generated: {report_file}")
    
    # Analyze memory
    logger.info("Analyzing memory usage...")
    analysis = profiler.analyze_memory()
    report_file = profiler.generate_report(analysis, "memory")
    logger.info(f"Memory analysis report generated: {report_file}")

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Jarvis AI Assistant Performance Profiler"
    )
    
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration for system monitoring (seconds)"
    )
    
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Sampling interval for monitoring (seconds)"
    )
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    
    try:
        asyncio.run(profile_app())
    except KeyboardInterrupt:
        logger.info("Profiling interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error during profiling: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
