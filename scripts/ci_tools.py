#!/usr/bin/env python3
"""
CI/CD tools for Jarvis AI Assistant.
This script provides utilities for managing continuous integration
and deployment processes, including build, test, and deployment automation.
"""

import os
import sys
import argparse
from pathlib import Path
import logging
import json
import yaml
from typing import Dict, List, Optional, Set, Union, Tuple
import subprocess
import re
from datetime import datetime
import docker
import requests
from jinja2 import Template
import shutil
import hashlib
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"
REPORTS_DIR = PROJECT_ROOT / "reports" / "ci"
DOCKER_DIR = PROJECT_ROOT / "docker"

class CITools:
    """CI/CD utility class."""
    
    def __init__(self):
        """Initialize CI tools."""
        self.build_dir = BUILD_DIR
        self.dist_dir = DIST_DIR
        self.reports_dir = REPORTS_DIR
        self.docker_dir = DOCKER_DIR
        
        # Create necessary directories
        self.build_dir.mkdir(exist_ok=True)
        self.dist_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Docker client
        try:
            self.docker = docker.from_env()
        except Exception as e:
            logger.warning(f"Could not initialize Docker client: {e}")
            self.docker = None
    
    def clean_build(self) -> bool:
        """Clean build directories."""
        try:
            # Remove build artifacts
            if self.build_dir.exists():
                shutil.rmtree(self.build_dir)
            if self.dist_dir.exists():
                shutil.rmtree(self.dist_dir)
            
            # Recreate directories
            self.build_dir.mkdir()
            self.dist_dir.mkdir()
            
            # Clean Python cache
            for cache_dir in PROJECT_ROOT.rglob("__pycache__"):
                shutil.rmtree(cache_dir)
            
            for cache_file in PROJECT_ROOT.rglob("*.pyc"):
                cache_file.unlink()
            
            logger.info("Build directories cleaned")
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning build: {e}")
            return False
    
    def build_package(self) -> bool:
        """Build Python package."""
        try:
            # Clean previous builds
            self.clean_build()
            
            # Build package
            subprocess.run(
                [sys.executable, "setup.py", "sdist", "bdist_wheel"],
                check=True
            )
            
            # Verify build artifacts
            wheels = list(self.dist_dir.glob("*.whl"))
            tarballs = list(self.dist_dir.glob("*.tar.gz"))
            
            if not wheels and not tarballs:
                logger.error("No build artifacts produced")
                return False
            
            # Generate build report
            report = {
                "timestamp": datetime.now().isoformat(),
                "artifacts": {
                    "wheels": [str(w.name) for w in wheels],
                    "tarballs": [str(t.name) for t in tarballs]
                },
                "sizes": {
                    str(f.name): f.stat().st_size
                    for f in [*wheels, *tarballs]
                }
            }
            
            report_file = self.reports_dir / "build_report.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Package built successfully: {len(wheels)} wheels, {len(tarballs)} tarballs")
            return True
            
        except Exception as e:
            logger.error(f"Error building package: {e}")
            return False
    
    def build_docker(self, tag: str = "latest") -> bool:
        """Build Docker image."""
        try:
            if not self.docker:
                logger.error("Docker client not available")
                return False
            
            # Check Dockerfile exists
            dockerfile = PROJECT_ROOT / "Dockerfile"
            if not dockerfile.exists():
                logger.error("Dockerfile not found")
                return False
            
            # Build image
            logger.info("Building Docker image...")
            image, logs = self.docker.images.build(
                path=str(PROJECT_ROOT),
                tag=f"jarvis-ai:{tag}",
                rm=True
            )
            
            # Save build logs
            log_file = self.reports_dir / f"docker_build_{tag}.log"
            with open(log_file, 'w') as f:
                for log in logs:
                    if 'stream' in log:
                        f.write(log['stream'])
            
            # Verify image
            if not image:
                logger.error("Failed to build Docker image")
                return False
            
            logger.info(f"Docker image built: jarvis-ai:{tag}")
            return True
            
        except Exception as e:
            logger.error(f"Error building Docker image: {e}")
            return False
    
    def run_tests(self, coverage: bool = True) -> bool:
        """Run test suite."""
        try:
            # Prepare test command
            cmd = ["pytest", "-v"]
            if coverage:
                cmd.extend([
                    "--cov=.",
                    "--cov-report=term-missing",
                    f"--cov-report=html:{self.reports_dir}/coverage"
                ])
            
            # Run tests
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Save test output
            output_file = self.reports_dir / "test_output.txt"
            with open(output_file, 'w') as f:
                f.write(result.stdout)
                if result.stderr:
                    f.write("\n\nErrors:\n")
                    f.write(result.stderr)
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return False
    
    def check_quality(self) -> Dict:
        """Run code quality checks."""
        results = {
            "passed": True,
            "checks": {}
        }
        
        try:
            # Run flake8
            flake8_result = subprocess.run(
                ["flake8", "."],
                capture_output=True,
                text=True
            )
            results["checks"]["flake8"] = {
                "passed": flake8_result.returncode == 0,
                "output": flake8_result.stdout
            }
            
            # Run mypy
            mypy_result = subprocess.run(
                ["mypy", "."],
                capture_output=True,
                text=True
            )
            results["checks"]["mypy"] = {
                "passed": mypy_result.returncode == 0,
                "output": mypy_result.stdout
            }
            
            # Run bandit
            bandit_result = subprocess.run(
                ["bandit", "-r", "."],
                capture_output=True,
                text=True
            )
            results["checks"]["bandit"] = {
                "passed": bandit_result.returncode == 0,
                "output": bandit_result.stdout
            }
            
            # Run pylint
            pylint_result = subprocess.run(
                ["pylint", "."],
                capture_output=True,
                text=True
            )
            results["checks"]["pylint"] = {
                "passed": pylint_result.returncode == 0,
                "output": pylint_result.stdout
            }
            
            # Update overall status
            results["passed"] = all(
                check["passed"]
                for check in results["checks"].values()
            )
            
            # Save results
            report_file = self.reports_dir / "quality_report.json"
            with open(report_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            return results
            
        except Exception as e:
            logger.error(f"Error checking code quality: {e}")
            results["passed"] = False
            return results
    
    def deploy_package(self, repository: str) -> bool:
        """Deploy package to PyPI repository."""
        try:
            # Check credentials
            if not os.getenv("TWINE_USERNAME") or not os.getenv("TWINE_PASSWORD"):
                logger.error("PyPI credentials not found in environment")
                return False
            
            # Check build artifacts
            if not list(self.dist_dir.glob("*")):
                logger.error("No build artifacts found")
                return False
            
            # Upload to PyPI
            result = subprocess.run(
                ["twine", "upload", "--repository", repository, "dist/*"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Upload failed: {result.stderr}")
                return False
            
            logger.info(f"Package deployed to {repository}")
            return True
            
        except Exception as e:
            logger.error(f"Error deploying package: {e}")
            return False
    
    def deploy_docker(
        self,
        registry: str,
        tag: str = "latest",
        push: bool = True
    ) -> bool:
        """Deploy Docker image to registry."""
        try:
            if not self.docker:
                logger.error("Docker client not available")
                return False
            
            # Tag image for registry
            image = self.docker.images.get(f"jarvis-ai:{tag}")
            registry_tag = f"{registry}/jarvis-ai:{tag}"
            image.tag(registry_tag)
            
            if push:
                # Push to registry
                logger.info(f"Pushing image to {registry}...")
                for line in self.docker.images.push(
                    registry_tag,
                    stream=True,
                    decode=True
                ):
                    if 'status' in line:
                        logger.info(line['status'])
            
            logger.info(f"Docker image deployed: {registry_tag}")
            return True
            
        except Exception as e:
            logger.error(f"Error deploying Docker image: {e}")
            return False
    
    def generate_report(
        self,
        build_results: Optional[bool] = None,
        test_results: Optional[bool] = None,
        quality_results: Optional[Dict] = None,
        deploy_results: Optional[Dict] = None
    ) -> Path:
        """Generate CI/CD report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f"ci_report_{timestamp}.html"
        
        content = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>CI/CD Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            ".section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f2f2f2; }",
            ".success { color: #4caf50; }",
            ".failure { color: #f44336; }",
            ".warning { color: #ff9800; }",
            "pre { background: #f5f5f5; padding: 10px; overflow-x: auto; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>CI/CD Report</h1>",
            f"<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        ]
        
        # Build section
        if build_results is not None:
            content.extend([
                "<div class='section'>",
                "<h2>Build Results</h2>",
                f"<p class='{'success' if build_results else 'failure'}'>"
                f"{'Success' if build_results else 'Failure'}</p>"
            ])
            
            # Add build artifacts if available
            if self.dist_dir.exists():
                content.extend([
                    "<h3>Build Artifacts</h3>",
                    "<ul>"
                ])
                for artifact in self.dist_dir.glob("*"):
                    size = artifact.stat().st_size / 1024  # KB
                    content.append(
                        f"<li>{artifact.name} ({size:.1f} KB)</li>"
                    )
                content.append("</ul>")
            
            content.append("</div>")
        
        # Test section
        if test_results is not None:
            content.extend([
                "<div class='section'>",
                "<h2>Test Results</h2>",
                f"<p class='{'success' if test_results else 'failure'}'>"
                f"{'Success' if test_results else 'Failure'}</p>"
            ])
            
            # Add test output if available
            test_output = self.reports_dir / "test_output.txt"
            if test_output.exists():
                content.extend([
                    "<h3>Test Output</h3>",
                    "<pre>",
                    test_output.read_text(),
                    "</pre>"
                ])
            
            content.append("</div>")
        
        # Quality section
        if quality_results is not None:
            content.extend([
                "<div class='section'>",
                "<h2>Code Quality Results</h2>",
                f"<p class='{'success' if quality_results['passed'] else 'failure'}'>"
                f"{'All checks passed' if quality_results['passed'] else 'Some checks failed'}</p>",
                "<table>",
                "<tr><th>Check</th><th>Status</th><th>Output</th></tr>"
            ])
            
            for check, results in quality_results["checks"].items():
                content.append(
                    f"<tr><td>{check}</td>"
                    f"<td class='{'success' if results['passed'] else 'failure'}'>"
                    f"{'Passed' if results['passed'] else 'Failed'}</td>"
                    f"<td><pre>{results['output']}</pre></td></tr>"
                )
            
            content.extend([
                "</table>",
                "</div>"
            ])
        
        # Deployment section
        if deploy_results is not None:
            content.extend([
                "<div class='section'>",
                "<h2>Deployment Results</h2>",
                "<table>",
                "<tr><th>Target</th><th>Status</th></tr>"
            ])
            
            for target, success in deploy_results.items():
                content.append(
                    f"<tr><td>{target}</td>"
                    f"<td class='{'success' if success else 'failure'}'>"
                    f"{'Success' if success else 'Failure'}</td></tr>"
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
        description="Jarvis AI Assistant CI Tools"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Clean command
    subparsers.add_parser("clean", help="Clean build directories")
    
    # Build command
    build_parser = subparsers.add_parser("build", help="Build package")
    build_parser.add_argument(
        "--docker",
        action="store_true",
        help="Build Docker image"
    )
    build_parser.add_argument(
        "--tag",
        default="latest",
        help="Docker image tag"
    )
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Skip coverage analysis"
    )
    
    # Quality command
    quality_parser = subparsers.add_parser(
        "quality",
        help="Run code quality checks"
    )
    quality_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    
    # Deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Deploy package")
    deploy_parser.add_argument(
        "--pypi",
        help="PyPI repository to deploy to"
    )
    deploy_parser.add_argument(
        "--docker-registry",
        help="Docker registry to deploy to"
    )
    deploy_parser.add_argument(
        "--tag",
        default="latest",
        help="Docker image tag"
    )
    deploy_parser.add_argument(
        "--no-push",
        action="store_true",
        help="Don't push Docker image"
    )
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    tools = CITools()
    
    try:
        if args.command == "clean":
            success = tools.clean_build()
            sys.exit(0 if success else 1)
        
        elif args.command == "build":
            build_results = tools.build_package()
            
            if args.docker:
                docker_results = tools.build_docker(args.tag)
                build_results = build_results and docker_results
            
            report_file = tools.generate_report(build_results=build_results)
            logger.info(f"Report generated: {report_file}")
            
            sys.exit(0 if build_results else 1)
        
        elif args.command == "test":
            test_results = tools.run_tests(not args.no_coverage)
            report_file = tools.generate_report(test_results=test_results)
            logger.info(f"Report generated: {report_file}")
            
            sys.exit(0 if test_results else 1)
        
        elif args.command == "quality":
            quality_results = tools.check_quality()
            
            if args.json:
                print(json.dumps(quality_results, indent=2))
            else:
                report_file = tools.generate_report(
                    quality_results=quality_results
                )
                logger.info(f"Report generated: {report_file}")
            
            sys.exit(0 if quality_results["passed"] else 1)
        
        elif args.command == "deploy":
            deploy_results = {}
            
            if args.pypi:
                deploy_results["pypi"] = tools.deploy_package(args.pypi)
            
            if args.docker_registry:
                deploy_results["docker"] = tools.deploy_docker(
                    args.docker_registry,
                    args.tag,
                    not args.no_push
                )
            
            report_file = tools.generate_report(deploy_results=deploy_results)
            logger.info(f"Report generated: {report_file}")
            
            sys.exit(0 if all(deploy_results.values()) else 1)
        
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
