#!/usr/bin/env python3
"""
Test analysis tools for Jarvis AI Assistant.
This script provides utilities for analyzing test coverage, quality,
and maintaining test suite health.
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
from datetime import datetime
import pytest
import coverage
from pytest_cov.plugin import CovData
import mutation
from radon.complexity import cc_visit
from radon.metrics import mi_visit
import ast
from tqdm import tqdm
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
TESTS_DIR = PROJECT_ROOT / "tests"
REPORTS_DIR = PROJECT_ROOT / "reports" / "tests"

class TestAnalyzer:
    """Test analysis utility class."""
    
    def __init__(self):
        """Initialize test analyzer."""
        self.tests_dir = TESTS_DIR
        self.reports_dir = REPORTS_DIR
        
        # Create necessary directories
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def run_tests(self, coverage: bool = True) -> Dict:
        """Run test suite with coverage."""
        results = {
            "tests": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "errors": 0,
                "duration": 0.0
            },
            "coverage": None,
            "failures": []
        }
        
        try:
            # Configure pytest arguments
            pytest_args = ["-v"]
            if coverage:
                pytest_args.extend([
                    "--cov=.",
                    "--cov-report=term-missing",
                    f"--cov-report=html:{self.reports_dir}/coverage"
                ])
            
            # Run tests
            pytest.main(pytest_args)
            
            # Parse results
            with open(".pytest_cache/v/cache/lastfailed") as f:
                failed_tests = json.load(f)
            
            with open(".pytest_cache/v/cache/nodeids") as f:
                all_tests = json.load(f)
            
            results["tests"]["total"] = len(all_tests)
            results["tests"]["failed"] = len(failed_tests)
            results["tests"]["passed"] = (
                len(all_tests) - len(failed_tests)
            )
            
            # Get coverage data
            if coverage:
                cov = coverage.Coverage()
                cov.load()
                
                results["coverage"] = {
                    "total": cov.report(),
                    "missing": {},
                    "files": {}
                }
                
                # Get detailed coverage data
                for file in cov.get_data().measured_files():
                    rel_path = Path(file).relative_to(PROJECT_ROOT)
                    analysis = cov.analysis2(file)
                    
                    results["coverage"]["files"][str(rel_path)] = {
                        "statements": len(analysis[1]),
                        "missing": len(analysis[2]),
                        "branches": len(analysis[3]),
                        "missing_branches": len(analysis[4])
                    }
                    
                    if analysis[2]:  # Missing lines
                        results["coverage"]["missing"][str(rel_path)] = list(analysis[2])
            
            return results
            
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return results
    
    def analyze_test_quality(self) -> Dict:
        """Analyze test suite quality metrics."""
        results = {
            "complexity": [],
            "maintainability": [],
            "assertions": [],
            "parameterized": [],
            "fixtures": set(),
            "mocks": []
        }
        
        try:
            # Analyze test files
            for test_file in self.tests_dir.rglob("test_*.py"):
                with open(test_file) as f:
                    content = f.read()
                
                # Calculate complexity
                complexity = cc_visit(content)
                maintainability = mi_visit(content, True)
                
                # Parse AST
                tree = ast.parse(content)
                
                test_info = {
                    "file": str(test_file.relative_to(PROJECT_ROOT)),
                    "complexity": [],
                    "assertions": 0,
                    "parameterized": 0
                }
                
                for node in ast.walk(tree):
                    # Count assertions
                    if isinstance(node, ast.Call):
                        if (hasattr(node.func, 'attr') and
                            node.func.attr.startswith('assert_')):
                            test_info["assertions"] += 1
                        elif isinstance(node.func, ast.Name):
                            if node.func.id.startswith('assert'):
                                test_info["assertions"] += 1
                    
                    # Check for parameterized tests
                    if isinstance(node, ast.FunctionDef):
                        for decorator in node.decorator_list:
                            if (isinstance(decorator, ast.Call) and
                                hasattr(decorator.func, 'attr') and
                                decorator.func.attr == 'parametrize'):
                                test_info["parameterized"] += 1
                    
                    # Collect fixtures
                    if isinstance(node, ast.FunctionDef):
                        for decorator in node.decorator_list:
                            if (isinstance(decorator, ast.Call) and
                                hasattr(decorator.func, 'attr') and
                                decorator.func.attr == 'fixture'):
                                results["fixtures"].add(node.name)
                    
                    # Check for mocks
                    if isinstance(node, ast.Call):
                        if (hasattr(node.func, 'attr') and
                            node.func.attr in ['patch', 'Mock', 'MagicMock']):
                            results["mocks"].append({
                                "file": test_info["file"],
                                "line": node.lineno
                            })
                
                # Add complexity metrics
                for item in complexity:
                    test_info["complexity"].append({
                        "name": item.name,
                        "complexity": item.complexity,
                        "rank": item.rank
                    })
                
                results["complexity"].append(test_info)
                results["maintainability"].append({
                    "file": test_info["file"],
                    "maintainability_index": maintainability,
                    "rank": "A" if maintainability >= 20 else "B" if maintainability >= 10 else "C"
                })
            
            # Convert fixtures to list for JSON serialization
            results["fixtures"] = list(results["fixtures"])
            
            return results
            
        except Exception as e:
            logger.error(f"Error analyzing test quality: {e}")
            return results
    
    def run_mutation_testing(self) -> Dict:
        """Run mutation testing on the test suite."""
        results = {
            "score": 0.0,
            "mutations": [],
            "survived": [],
            "killed": []
        }
        
        try:
            # Configure mutation testing
            config = {
                "targets": ["core", "services", "utils"],
                "unit_test_command": "pytest",
                "test_dir": "tests",
                "exclude": ["__init__.py"]
            }
            
            # Run mutation testing
            mutation.main(config)
            
            # Parse results
            results_file = Path("mutation.json")
            if results_file.exists():
                with open(results_file) as f:
                    mutation_results = json.load(f)
                
                results["score"] = mutation_results["mutation_score"]
                
                for mutant in mutation_results["mutants"]:
                    mutant_info = {
                        "file": mutant["file"],
                        "line": mutant["line"],
                        "operator": mutant["operator"],
                        "original": mutant["original"],
                        "mutated": mutant["mutated"]
                    }
                    
                    results["mutations"].append(mutant_info)
                    
                    if mutant["status"] == "survived":
                        results["survived"].append(mutant_info)
                    else:
                        results["killed"].append(mutant_info)
            
            return results
            
        except Exception as e:
            logger.error(f"Error running mutation testing: {e}")
            return results
    
    def generate_report(
        self,
        test_results: Dict,
        quality_results: Dict,
        mutation_results: Optional[Dict] = None
    ) -> Path:
        """Generate test analysis report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f"test_report_{timestamp}.html"
        
        content = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Test Analysis Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            ".section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f2f2f2; }",
            ".chart { margin: 20px 0; max-width: 800px; }",
            ".good { color: #4caf50; }",
            ".warning { color: #ff9800; }",
            ".error { color: #f44336; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Test Analysis Report</h1>",
            f"<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        ]
        
        # Test results section
        content.extend([
            "<div class='section'>",
            "<h2>Test Results</h2>",
            "<table>",
            "<tr><th>Metric</th><th>Value</th></tr>",
            f"<tr><td>Total Tests</td><td>{test_results['tests']['total']}</td></tr>",
            f"<tr><td>Passed</td><td class='good'>{test_results['tests']['passed']}</td></tr>",
            f"<tr><td>Failed</td><td class='error'>{test_results['tests']['failed']}</td></tr>",
            f"<tr><td>Skipped</td><td>{test_results['tests']['skipped']}</td></tr>",
            f"<tr><td>Errors</td><td class='error'>{test_results['tests']['errors']}</td></tr>",
            "</table>"
        ])
        
        if test_results.get("coverage"):
            # Create coverage chart
            plt.figure(figsize=(10, 6))
            coverage_data = [
                (file, data["statements"] - data["missing"])
                for file, data in test_results["coverage"]["files"].items()
            ]
            files, coverage = zip(*coverage_data)
            
            plt.bar(range(len(files)), coverage)
            plt.xticks(range(len(files)), files, rotation=45, ha="right")
            plt.title("Coverage by File")
            plt.ylabel("Covered Statements")
            plt.tight_layout()
            plt.savefig(self.reports_dir / "coverage_chart.png")
            plt.close()
            
            content.extend([
                "<h3>Coverage Summary</h3>",
                f"<p>Total Coverage: <span class='{self._get_coverage_class(test_results['coverage']['total'])}'>"
                f"{test_results['coverage']['total']:.1f}%</span></p>",
                "<img src='coverage_chart.png' class='chart'>",
                "<h4>Missing Coverage</h4>",
                "<table>",
                "<tr><th>File</th><th>Missing Lines</th></tr>"
            ])
            
            for file, lines in test_results["coverage"]["missing"].items():
                content.append(
                    f"<tr><td>{file}</td><td>{', '.join(map(str, lines))}</td></tr>"
                )
            
            content.append("</table>")
        
        content.append("</div>")
        
        # Test quality section
        content.extend([
            "<div class='section'>",
            "<h2>Test Quality Analysis</h2>",
            "<h3>Complexity</h3>",
            "<table>",
            "<tr><th>File</th><th>Function</th><th>Complexity</th><th>Rank</th></tr>"
        ])
        
        for test_file in quality_results["complexity"]:
            for func in test_file["complexity"]:
                content.append(
                    f"<tr><td>{test_file['file']}</td><td>{func['name']}</td>"
                    f"<td>{func['complexity']}</td><td>{func['rank']}</td></tr>"
                )
        
        content.extend([
            "</table>",
            "<h3>Maintainability</h3>",
            "<table>",
            "<tr><th>File</th><th>Index</th><th>Rank</th></tr>"
        ])
        
        for item in quality_results["maintainability"]:
            content.append(
                f"<tr><td>{item['file']}</td>"
                f"<td>{item['maintainability_index']:.1f}</td>"
                f"<td>{item['rank']}</td></tr>"
            )
        
        content.extend([
            "</table>",
            "<h3>Test Characteristics</h3>",
            "<ul>",
            f"<li>Total Fixtures: {len(quality_results['fixtures'])}</li>",
            f"<li>Mock Usage: {len(quality_results['mocks'])} instances</li>"
        ])
        
        parameterized_count = sum(
            test["parameterized"]
            for test in quality_results["complexity"]
        )
        content.append(f"<li>Parameterized Tests: {parameterized_count}</li>")
        
        content.append("</ul>")
        
        # Mutation testing section
        if mutation_results:
            content.extend([
                "<h3>Mutation Testing</h3>",
                f"<p>Mutation Score: <span class='{self._get_mutation_class(mutation_results['score'])}'>"
                f"{mutation_results['score']:.1f}%</span></p>",
                "<h4>Survived Mutations</h4>",
                "<table>",
                "<tr><th>File</th><th>Line</th><th>Operator</th><th>Original</th><th>Mutated</th></tr>"
            ])
            
            for mutant in mutation_results["survived"]:
                content.append(
                    f"<tr><td>{mutant['file']}</td><td>{mutant['line']}</td>"
                    f"<td>{mutant['operator']}</td><td>{mutant['original']}</td>"
                    f"<td>{mutant['mutated']}</td></tr>"
                )
            
            content.append("</table>")
        
        content.extend([
            "</div>",
            "</body>",
            "</html>"
        ])
        
        report_file.write_text("\n".join(content))
        return report_file
    
    def _get_coverage_class(self, coverage: float) -> str:
        """Get CSS class for coverage percentage."""
        if coverage >= 90:
            return "good"
        elif coverage >= 75:
            return "warning"
        else:
            return "error"
    
    def _get_mutation_class(self, score: float) -> str:
        """Get CSS class for mutation score."""
        if score >= 80:
            return "good"
        elif score >= 60:
            return "warning"
        else:
            return "error"

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Jarvis AI Assistant Test Analyzer"
    )
    
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Skip coverage analysis"
    )
    
    parser.add_argument(
        "--mutation",
        action="store_true",
        help="Run mutation testing"
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
    analyzer = TestAnalyzer()
    
    try:
        # Run tests and analysis
        test_results = analyzer.run_tests(not args.no_coverage)
        quality_results = analyzer.analyze_test_quality()
        mutation_results = None
        
        if args.mutation:
            mutation_results = analyzer.run_mutation_testing()
        
        if args.json:
            results = {
                "tests": test_results,
                "quality": quality_results
            }
            if mutation_results:
                results["mutation"] = mutation_results
            print(json.dumps(results, indent=2))
        else:
            report_file = analyzer.generate_report(
                test_results,
                quality_results,
                mutation_results
            )
            logger.info(f"Report generated: {report_file}")
        
        # Exit with error if tests failed
        if test_results["tests"]["failed"] > 0:
            sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
