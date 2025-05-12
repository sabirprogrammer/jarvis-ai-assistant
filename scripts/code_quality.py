#!/usr/bin/env python3
"""
Code quality and linting tools for Jarvis AI Assistant.
This script provides utilities for checking code quality, enforcing standards,
and generating quality reports.
"""

import os
import sys
import argparse
from pathlib import Path
import logging
import json
from typing import Dict, List, Optional, Set, Union
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import pylint.lint
import black
import isort
import mypy.api
from pycodestyle import StyleGuide
import radon.complexity as radon_cc
import radon.metrics as radon_metrics
import radon.raw as radon_raw
from vulture import Vulture
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "code_quality"
EXCLUDE_PATTERNS = {
    r'.*\.pyc$',
    r'.*\.git/.*',
    r'.*\.venv/.*',
    r'.*__pycache__/.*',
    r'.*/\..+',
    r'.*/node_modules/.*'
}

class CodeQualityChecker:
    """Code quality checking utility class."""
    
    def __init__(self):
        """Initialize code quality checker."""
        self.reports_dir = REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def _should_exclude(self, path: str) -> bool:
        """Check if path should be excluded."""
        return any(re.match(pattern, path) for pattern in EXCLUDE_PATTERNS)
    
    def _get_python_files(self) -> List[Path]:
        """Get all Python files in project."""
        python_files = []
        for file_path in PROJECT_ROOT.rglob("*.py"):
            if not self._should_exclude(str(file_path)):
                python_files.append(file_path)
        return python_files
    
    def run_pylint(self, files: List[Path]) -> Dict:
        """Run Pylint analysis."""
        results = {
            "score": 0.0,
            "messages": [],
            "stats": {}
        }
        
        try:
            # Create temporary file for report
            report_path = self.reports_dir / "pylint_report.json"
            
            # Run Pylint
            pylint_opts = [
                "--output-format=json",
                "--reports=no",
                f"--output={report_path}",
                *[str(f) for f in files]
            ]
            
            pylint.lint.Run(pylint_opts, exit=False)
            
            # Read results
            if report_path.exists():
                with open(report_path) as f:
                    pylint_results = json.load(f)
                
                # Process results
                total_score = 0
                file_count = 0
                
                for result in pylint_results:
                    if "score" in result:
                        total_score += result["score"]
                        file_count += 1
                    
                    if "message" in result:
                        results["messages"].append({
                            "path": result["path"],
                            "line": result["line"],
                            "column": result["column"],
                            "type": result["type"],
                            "symbol": result["symbol"],
                            "message": result["message"]
                        })
                
                if file_count > 0:
                    results["score"] = total_score / file_count
                
                # Collect statistics
                message_types = {}
                for msg in results["messages"]:
                    msg_type = msg["type"]
                    message_types[msg_type] = message_types.get(msg_type, 0) + 1
                
                results["stats"] = {
                    "total_messages": len(results["messages"]),
                    "by_type": message_types
                }
            
            return results
            
        except Exception as e:
            logger.error(f"Error running Pylint: {e}")
            return results
    
    def run_black(self, files: List[Path], check_only: bool = True) -> Dict:
        """Run Black code formatter."""
        results = {
            "would_change": [],
            "errors": []
        }
        
        try:
            mode = black.FileMode()
            
            for file_path in files:
                try:
                    with open(file_path, "rb") as f:
                        source = f.read()
                    
                    if check_only:
                        try:
                            black.format_file_contents(
                                source,
                                fast=False,
                                mode=mode
                            )
                        except black.NothingChanged:
                            pass
                        except Exception:
                            results["would_change"].append(str(file_path))
                    else:
                        try:
                            new_content = black.format_file_contents(
                                source,
                                fast=False,
                                mode=mode
                            )
                            with open(file_path, "wb") as f:
                                f.write(new_content)
                        except black.NothingChanged:
                            pass
                        except Exception as e:
                            results["errors"].append({
                                "file": str(file_path),
                                "error": str(e)
                            })
                
                except Exception as e:
                    results["errors"].append({
                        "file": str(file_path),
                        "error": str(e)
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error running Black: {e}")
            return results
    
    def run_isort(self, files: List[Path], check_only: bool = True) -> Dict:
        """Run isort import sorter."""
        results = {
            "would_change": [],
            "errors": []
        }
        
        try:
            for file_path in files:
                try:
                    if check_only:
                        if not isort.check_file(file_path):
                            results["would_change"].append(str(file_path))
                    else:
                        isort.file(file_path)
                except Exception as e:
                    results["errors"].append({
                        "file": str(file_path),
                        "error": str(e)
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error running isort: {e}")
            return results
    
    def run_mypy(self, files: List[Path]) -> Dict:
        """Run MyPy type checker."""
        results = {
            "errors": []
        }
        
        try:
            # Run MyPy
            stdout, stderr, status = mypy.api.run([
                "--ignore-missing-imports",
                *[str(f) for f in files]
            ])
            
            # Parse results
            if stdout:
                for line in stdout.split("\n"):
                    if line.strip():
                        try:
                            file_path, line_no, *message_parts = line.split(":")
                            results["errors"].append({
                                "file": file_path,
                                "line": int(line_no),
                                "message": ":".join(message_parts).strip()
                            })
                        except Exception:
                            continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error running MyPy: {e}")
            return results
    
    def run_style_check(self, files: List[Path]) -> Dict:
        """Run PEP 8 style checker."""
        results = {
            "violations": []
        }
        
        try:
            style_guide = StyleGuide(quiet=True)
            result = style_guide.check_files([str(f) for f in files])
            
            for message in result.messages:
                results["violations"].append({
                    "file": message.path,
                    "line": message.line_number,
                    "column": message.column,
                    "code": message.code,
                    "text": message.text
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error running style check: {e}")
            return results
    
    def analyze_complexity(self, files: List[Path]) -> Dict:
        """Analyze code complexity."""
        results = {
            "complexity": [],
            "maintainability": [],
            "raw_metrics": []
        }
        
        try:
            for file_path in files:
                try:
                    with open(file_path) as f:
                        content = f.read()
                    
                    # Cyclomatic complexity
                    cc = radon_cc.cc_visit(content)
                    for item in cc:
                        results["complexity"].append({
                            "file": str(file_path),
                            "name": item.name,
                            "type": item.type,
                            "complexity": item.complexity,
                            "rank": item.rank
                        })
                    
                    # Maintainability index
                    mi = radon_metrics.mi_visit(content, True)
                    results["maintainability"].append({
                        "file": str(file_path),
                        "maintainability_index": mi,
                        "rank": radon_metrics.mi_rank(mi)
                    })
                    
                    # Raw metrics
                    raw = radon_raw.analyze(content)
                    results["raw_metrics"].append({
                        "file": str(file_path),
                        "loc": raw.loc,
                        "lloc": raw.lloc,
                        "sloc": raw.sloc,
                        "comments": raw.comments,
                        "multi": raw.multi,
                        "blank": raw.blank
                    })
                    
                except Exception as e:
                    logger.warning(f"Error analyzing {file_path}: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error analyzing complexity: {e}")
            return results
    
    def find_dead_code(self, files: List[Path]) -> Dict:
        """Find potentially dead code."""
        results = {
            "unused_code": []
        }
        
        try:
            vulture = Vulture()
            for file_path in files:
                vulture.scavenge([str(file_path)])
            
            # Process results
            for item in vulture.unused_funcs + vulture.unused_props + vulture.unused_vars:
                results["unused_code"].append({
                    "type": item.typ,
                    "name": item.name,
                    "file": item.filename,
                    "line": item.first_lineno,
                    "size": item.size
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error finding dead code: {e}")
            return results
    
    def generate_report(self, all_results: Dict) -> Path:
        """Generate code quality report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f"code_quality_report_{timestamp}.html"
        
        content = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Code Quality Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            ".section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f2f2f2; }",
            ".error { color: #f44336; }",
            ".warning { color: #ff9800; }",
            ".success { color: #4caf50; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Code Quality Report</h1>",
            f"<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        ]
        
        # Pylint section
        content.extend([
            "<div class='section'>",
            "<h2>Pylint Analysis</h2>",
            f"<p>Overall Score: <span class='{self._get_score_class(all_results['pylint']['score'])}'>"
            f"{all_results['pylint']['score']:.2f}/10</span></p>",
            "<h3>Message Statistics</h3>",
            "<table>",
            "<tr><th>Type</th><th>Count</th></tr>"
        ])
        
        for msg_type, count in all_results["pylint"]["stats"]["by_type"].items():
            content.append(f"<tr><td>{msg_type}</td><td>{count}</td></tr>")
        
        content.extend([
            "</table>",
            "<h3>Messages</h3>",
            "<table>",
            "<tr><th>File</th><th>Line</th><th>Type</th><th>Message</th></tr>"
        ])
        
        for msg in all_results["pylint"]["messages"]:
            content.append(
                f"<tr><td>{msg['path']}</td><td>{msg['line']}</td>"
                f"<td>{msg['type']}</td><td>{msg['message']}</td></tr>"
            )
        
        content.extend([
            "</table>",
            "</div>"
        ])
        
        # Code formatting section
        content.extend([
            "<div class='section'>",
            "<h2>Code Formatting</h2>",
            "<h3>Black</h3>"
        ])
        
        if all_results["black"]["would_change"]:
            content.extend([
                "<p>Files needing formatting:</p>",
                "<ul>"
            ])
            for file in all_results["black"]["would_change"]:
                content.append(f"<li>{file}</li>")
            content.append("</ul>")
        else:
            content.append("<p class='success'>All files properly formatted</p>")
        
        content.extend([
            "<h3>isort</h3>"
        ])
        
        if all_results["isort"]["would_change"]:
            content.extend([
                "<p>Files needing import sorting:</p>",
                "<ul>"
            ])
            for file in all_results["isort"]["would_change"]:
                content.append(f"<li>{file}</li>")
            content.append("</ul>")
        else:
            content.append("<p class='success'>All imports properly sorted</p>")
        
        content.append("</div>")
        
        # Type checking section
        content.extend([
            "<div class='section'>",
            "<h2>Type Checking (MyPy)</h2>"
        ])
        
        if all_results["mypy"]["errors"]:
            content.extend([
                "<table>",
                "<tr><th>File</th><th>Line</th><th>Message</th></tr>"
            ])
            for error in all_results["mypy"]["errors"]:
                content.append(
                    f"<tr><td>{error['file']}</td><td>{error['line']}</td>"
                    f"<td>{error['message']}</td></tr>"
                )
            content.append("</table>")
        else:
            content.append("<p class='success'>No type errors found</p>")
        
        content.append("</div>")
        
        # Code complexity section
        content.extend([
            "<div class='section'>",
            "<h2>Code Complexity</h2>",
            "<h3>Complex Functions</h3>",
            "<table>",
            "<tr><th>File</th><th>Function</th><th>Complexity</th><th>Rank</th></tr>"
        ])
        
        for item in sorted(
            all_results["complexity"]["complexity"],
            key=lambda x: x["complexity"],
            reverse=True
        )[:10]:
            content.append(
                f"<tr><td>{item['file']}</td><td>{item['name']}</td>"
                f"<td>{item['complexity']}</td><td>{item['rank']}</td></tr>"
            )
        
        content.extend([
            "</table>",
            "<h3>Maintainability Index</h3>",
            "<table>",
            "<tr><th>File</th><th>Index</th><th>Rank</th></tr>"
        ])
        
        for item in sorted(
            all_results["complexity"]["maintainability"],
            key=lambda x: x["maintainability_index"]
        )[:10]:
            content.append(
                f"<tr><td>{item['file']}</td>"
                f"<td>{item['maintainability_index']:.2f}</td>"
                f"<td>{item['rank']}</td></tr>"
            )
        
        content.append("</table>")
        content.append("</div>")
        
        # Dead code section
        content.extend([
            "<div class='section'>",
            "<h2>Potentially Dead Code</h2>"
        ])
        
        if all_results["dead_code"]["unused_code"]:
            content.extend([
                "<table>",
                "<tr><th>Type</th><th>Name</th><th>File</th><th>Line</th></tr>"
            ])
            for item in all_results["dead_code"]["unused_code"]:
                content.append(
                    f"<tr><td>{item['type']}</td><td>{item['name']}</td>"
                    f"<td>{item['file']}</td><td>{item['line']}</td></tr>"
                )
            content.append("</table>")
        else:
            content.append("<p class='success'>No dead code found</p>")
        
        content.extend([
            "</div>",
            "</body>",
            "</html>"
        ])
        
        report_file.write_text("\n".join(content))
        return report_file
    
    def _get_score_class(self, score: float) -> str:
        """Get CSS class for score."""
        if score >= 8:
            return "success"
        elif score >= 6:
            return "warning"
        else:
            return "error"

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Jarvis AI Assistant Code Quality Checker"
    )
    
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Fix formatting issues"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    checker = CodeQualityChecker()
    
    try:
        # Get Python files
        python_files = checker._get_python_files()
        
        if not python_files:
            logger.error("No Python files found")
            sys.exit(1)
        
        logger.info(f"Found {len(python_files)} Python files")
        
        # Run all checks
        results = {
            "pylint": checker.run_pylint(python_files),
            "black": checker.run_black(python_files, not args.fix),
            "isort": checker.run_isort(python_files, not args.fix),
            "mypy": checker.run_mypy(python_files),
            "style": checker.run_style_check(python_files),
            "complexity": checker.analyze_complexity(python_files),
            "dead_code": checker.find_dead_code(python_files)
        }
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            report_file = checker.generate_report(results)
            logger.info(f"Report generated: {report_file}")
        
        # Exit with error if significant issues found
        has_issues = (
            results["pylint"]["score"] < 7.0 or
            results["black"]["would_change"] or
            results["isort"]["would_change"] or
            results["mypy"]["errors"] or
            len(results["style"]["violations"]) > 10
        )
        
        sys.exit(1 if has_issues else 0)
        
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
