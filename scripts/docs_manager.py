#!/usr/bin/env python3
"""
Documentation management tools for Jarvis AI Assistant.
This script provides utilities for managing project documentation,
generating API docs, and maintaining documentation quality.
"""

import os
import sys
import argparse
from pathlib import Path
import logging
import json
import yaml
from typing import Dict, List, Optional, Set, Union
import subprocess
import re
from datetime import datetime
import shutil
import docstring_parser
import pdoc
from sphinx.cmd.build import build_main as sphinx_build
import mkdocs.commands.build
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
BUILD_DIR = DOCS_DIR / "_build"
API_DOCS_DIR = DOCS_DIR / "api"
REPORTS_DIR = PROJECT_ROOT / "reports" / "docs"

class DocsManager:
    """Documentation management utility class."""
    
    def __init__(self):
        """Initialize documentation manager."""
        self.docs_dir = DOCS_DIR
        self.build_dir = BUILD_DIR
        self.api_docs_dir = API_DOCS_DIR
        self.reports_dir = REPORTS_DIR
        
        # Create necessary directories
        self.docs_dir.mkdir(exist_ok=True)
        self.build_dir.mkdir(exist_ok=True)
        self.api_docs_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def analyze_docstrings(self, module_paths: List[Path]) -> Dict:
        """Analyze docstring coverage and quality."""
        results = {
            "coverage": {
                "total_objects": 0,
                "documented_objects": 0,
                "coverage_percent": 0.0
            },
            "quality": {
                "missing_params": [],
                "missing_returns": [],
                "missing_types": [],
                "incomplete_docs": []
            },
            "by_file": {}
        }
        
        for module_path in module_paths:
            file_results = {
                "objects": [],
                "coverage": 0.0,
                "issues": []
            }
            
            try:
                with open(module_path) as f:
                    content = f.read()
                
                # Use AST to analyze Python code
                import ast
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                        results["coverage"]["total_objects"] += 1
                        file_results["objects"].append({
                            "name": node.name,
                            "type": type(node).__name__,
                            "line": node.lineno
                        })
                        
                        # Check docstring
                        docstring = ast.get_docstring(node)
                        if docstring:
                            results["coverage"]["documented_objects"] += 1
                            
                            # Parse docstring
                            try:
                                parsed = docstring_parser.parse(docstring)
                                
                                # Check parameters
                                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                    arg_names = {a.arg for a in node.args.args if a.arg != 'self'}
                                    doc_params = {p.arg_name for p in parsed.params}
                                    
                                    missing_params = arg_names - doc_params
                                    if missing_params:
                                        issue = {
                                            "object": node.name,
                                            "missing_params": list(missing_params)
                                        }
                                        results["quality"]["missing_params"].append({
                                            "file": str(module_path),
                                            **issue
                                        })
                                        file_results["issues"].append(issue)
                                
                                # Check return documentation
                                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                    returns = node.returns or ast.Return()
                                    if returns and not parsed.returns:
                                        issue = {
                                            "object": node.name,
                                            "missing": "return documentation"
                                        }
                                        results["quality"]["missing_returns"].append({
                                            "file": str(module_path),
                                            **issue
                                        })
                                        file_results["issues"].append(issue)
                                
                                # Check type hints
                                if not any(p.type_name for p in parsed.params):
                                    issue = {
                                        "object": node.name,
                                        "missing": "type hints"
                                    }
                                    results["quality"]["missing_types"].append({
                                        "file": str(module_path),
                                        **issue
                                    })
                                    file_results["issues"].append(issue)
                                
                            except Exception as e:
                                logger.warning(f"Error parsing docstring for {node.name}: {e}")
                        
                        else:
                            issue = {
                                "object": node.name,
                                "missing": "docstring"
                            }
                            results["quality"]["incomplete_docs"].append({
                                "file": str(module_path),
                                **issue
                            })
                            file_results["issues"].append(issue)
                
                # Calculate file coverage
                if file_results["objects"]:
                    documented = sum(1 for obj in file_results["objects"]
                                  if not any(i["object"] == obj["name"] and
                                           i["missing"] == "docstring"
                                           for i in file_results["issues"]))
                    file_results["coverage"] = (
                        documented / len(file_results["objects"]) * 100
                    )
                
                results["by_file"][str(module_path)] = file_results
                
            except Exception as e:
                logger.error(f"Error analyzing {module_path}: {e}")
        
        # Calculate overall coverage
        if results["coverage"]["total_objects"] > 0:
            results["coverage"]["coverage_percent"] = (
                results["coverage"]["documented_objects"] /
                results["coverage"]["total_objects"] * 100
            )
        
        return results
    
    def generate_api_docs(self) -> bool:
        """Generate API documentation using pdoc."""
        try:
            logger.info("Generating API documentation...")
            
            # Clean API docs directory
            if self.api_docs_dir.exists():
                shutil.rmtree(self.api_docs_dir)
            self.api_docs_dir.mkdir()
            
            # Generate documentation
            modules = [
                str(f.relative_to(PROJECT_ROOT))
                for f in PROJECT_ROOT.rglob("*.py")
                if not any(part.startswith(".") for part in f.parts)
                and "tests" not in f.parts
            ]
            
            pdoc.cli.main([
                "--html",
                "--output-dir", str(self.api_docs_dir),
                *modules
            ])
            
            logger.info(f"API documentation generated in {self.api_docs_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating API documentation: {e}")
            return False
    
    def build_sphinx_docs(self) -> bool:
        """Build Sphinx documentation."""
        try:
            logger.info("Building Sphinx documentation...")
            
            # Clean build directory
            if self.build_dir.exists():
                shutil.rmtree(self.build_dir)
            
            # Build documentation
            result = sphinx_build([
                "-b", "html",
                "-d", str(self.build_dir / "doctrees"),
                str(self.docs_dir),
                str(self.build_dir / "html")
            ])
            
            if result == 0:
                logger.info(f"Documentation built in {self.build_dir}/html")
                return True
            else:
                logger.error("Documentation build failed")
                return False
            
        except Exception as e:
            logger.error(f"Error building documentation: {e}")
            return False
    
    def check_links(self) -> Dict:
        """Check documentation links."""
        results = {
            "broken_links": [],
            "warnings": []
        }
        
        try:
            import urllib.request
            import urllib.error
            
            def check_url(url: str) -> Optional[str]:
                try:
                    urllib.request.urlopen(url)
                    return None
                except urllib.error.URLError as e:
                    return str(e)
                except Exception as e:
                    return str(e)
            
            # Check all .rst and .md files
            doc_files = list(self.docs_dir.rglob("*.rst"))
            doc_files.extend(self.docs_dir.rglob("*.md"))
            
            url_pattern = re.compile(
                r'https?://[^\s<>"]+|www\.[^\s<>"]+|(?<=\]\().*?(?=\))'
            )
            
            for doc_file in doc_files:
                try:
                    content = doc_file.read_text()
                    urls = url_pattern.findall(content)
                    
                    for url in urls:
                        if url.startswith(("http://", "https://", "www.")):
                            error = check_url(url)
                            if error:
                                results["broken_links"].append({
                                    "file": str(doc_file),
                                    "url": url,
                                    "error": error
                                })
                        else:
                            # Check relative links
                            target = (doc_file.parent / url).resolve()
                            if not target.exists():
                                results["broken_links"].append({
                                    "file": str(doc_file),
                                    "url": url,
                                    "error": "File not found"
                                })
                    
                except Exception as e:
                    results["warnings"].append({
                        "file": str(doc_file),
                        "error": str(e)
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error checking links: {e}")
            return results
    
    def generate_report(self, analysis: Dict, link_check: Dict) -> Path:
        """Generate documentation quality report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f"docs_report_{timestamp}.html"
        
        content = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Documentation Quality Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            ".section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f2f2f2; }",
            ".warning { color: #ff9800; }",
            ".error { color: #f44336; }",
            ".success { color: #4caf50; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Documentation Quality Report</h1>",
            f"<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
            
            "<div class='section'>",
            "<h2>Documentation Coverage</h2>",
            f"<p>Overall Coverage: <span class='{self._get_coverage_class(analysis['coverage']['coverage_percent'])}'>"
            f"{analysis['coverage']['coverage_percent']:.1f}%</span></p>",
            "<ul>",
            f"<li>Total Objects: {analysis['coverage']['total_objects']}</li>",
            f"<li>Documented Objects: {analysis['coverage']['documented_objects']}</li>",
            "</ul>",
            "</div>",
            
            "<div class='section'>",
            "<h2>Documentation Quality Issues</h2>",
            "<h3>Missing Parameters</h3>"
        ]
        
        if analysis["quality"]["missing_params"]:
            content.extend([
                "<table>",
                "<tr><th>File</th><th>Object</th><th>Missing Parameters</th></tr>"
            ])
            for issue in analysis["quality"]["missing_params"]:
                content.append(
                    f"<tr><td>{issue['file']}</td><td>{issue['object']}</td>"
                    f"<td>{', '.join(issue['missing_params'])}</td></tr>"
                )
            content.append("</table>")
        else:
            content.append("<p class='success'>No missing parameters</p>")
        
        content.extend([
            "<h3>Missing Return Documentation</h3>"
        ])
        
        if analysis["quality"]["missing_returns"]:
            content.extend([
                "<table>",
                "<tr><th>File</th><th>Object</th></tr>"
            ])
            for issue in analysis["quality"]["missing_returns"]:
                content.append(
                    f"<tr><td>{issue['file']}</td><td>{issue['object']}</td></tr>"
                )
            content.append("</table>")
        else:
            content.append("<p class='success'>No missing return documentation</p>")
        
        content.extend([
            "<h3>Missing Type Hints</h3>"
        ])
        
        if analysis["quality"]["missing_types"]:
            content.extend([
                "<table>",
                "<tr><th>File</th><th>Object</th></tr>"
            ])
            for issue in analysis["quality"]["missing_types"]:
                content.append(
                    f"<tr><td>{issue['file']}</td><td>{issue['object']}</td></tr>"
                )
            content.append("</table>")
        else:
            content.append("<p class='success'>No missing type hints</p>")
        
        content.append("</div>")
        
        content.extend([
            "<div class='section'>",
            "<h2>Link Check Results</h2>"
        ])
        
        if link_check["broken_links"]:
            content.extend([
                "<table>",
                "<tr><th>File</th><th>URL</th><th>Error</th></tr>"
            ])
            for link in link_check["broken_links"]:
                content.append(
                    f"<tr><td>{link['file']}</td><td>{link['url']}</td>"
                    f"<td>{link['error']}</td></tr>"
                )
            content.append("</table>")
        else:
            content.append("<p class='success'>No broken links found</p>")
        
        if link_check["warnings"]:
            content.extend([
                "<h3>Warnings</h3>",
                "<ul>"
            ])
            for warning in link_check["warnings"]:
                content.append(
                    f"<li>{warning['file']}: {warning['error']}</li>"
                )
            content.append("</ul>")
        
        content.extend([
            "</div>",
            "</body>",
            "</html>"
        ])
        
        report_file.write_text("\n".join(content))
        return report_file
    
    def _get_coverage_class(self, coverage: float) -> str:
        """Get CSS class for coverage percentage."""
        if coverage >= 80:
            return "success"
        elif coverage >= 50:
            return "warning"
        else:
            return "error"

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Jarvis AI Assistant Documentation Manager"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze documentation quality"
    )
    analyze_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    
    # Generate API docs command
    subparsers.add_parser(
        "generate-api",
        help="Generate API documentation"
    )
    
    # Build docs command
    subparsers.add_parser(
        "build",
        help="Build Sphinx documentation"
    )
    
    # Check links command
    subparsers.add_parser(
        "check-links",
        help="Check documentation links"
    )
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    manager = DocsManager()
    
    try:
        if args.command == "analyze":
            # Get Python files
            python_files = [
                f for f in PROJECT_ROOT.rglob("*.py")
                if not any(part.startswith(".") for part in f.parts)
                and "tests" not in f.parts
            ]
            
            analysis = manager.analyze_docstrings(python_files)
            link_check = manager.check_links()
            
            if args.json:
                print(json.dumps(
                    {"analysis": analysis, "links": link_check},
                    indent=2
                ))
            else:
                report_file = manager.generate_report(analysis, link_check)
                logger.info(f"Report generated: {report_file}")
        
        elif args.command == "generate-api":
            success = manager.generate_api_docs()
            sys.exit(0 if success else 1)
        
        elif args.command == "build":
            success = manager.build_sphinx_docs()
            sys.exit(0 if success else 1)
        
        elif args.command == "check-links":
            results = manager.check_links()
            
            if results["broken_links"]:
                print("\nBroken Links:")
                for link in results["broken_links"]:
                    print(f"\nFile: {link['file']}")
                    print(f"URL: {link['url']}")
                    print(f"Error: {link['error']}")
                sys.exit(1)
            else:
                print("No broken links found")
                sys.exit(0)
        
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
