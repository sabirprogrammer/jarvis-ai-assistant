#!/usr/bin/env python3
"""
Dependency management tools for Jarvis AI Assistant.
This script provides utilities for managing project dependencies,
analyzing requirements, and maintaining virtual environments.
"""

import os
import sys
import argparse
from pathlib import Path
import logging
import json
import yaml
from typing import Dict, List, Optional, Set, Tuple
import subprocess
import pkg_resources
from packaging import version
import re
import requests
from concurrent.futures import ThreadPoolExecutor
import virtualenv
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
VENV_DIR = PROJECT_ROOT / ".venv"
REQUIREMENTS = {
    "core": PROJECT_ROOT / "requirements.txt",
    "dev": PROJECT_ROOT / "requirements-dev.txt",
    "docs": PROJECT_ROOT / "requirements-docs.txt",
    "test": PROJECT_ROOT / "requirements-test.txt"
}

class DependencyManager:
    """Dependency management utility class."""
    
    def __init__(self):
        """Initialize dependency manager."""
        self.venv_dir = VENV_DIR
        self.requirements = REQUIREMENTS
    
    def _run_pip(self, args: List[str], **kwargs) -> subprocess.CompletedProcess:
        """Run pip command."""
        pip_path = self.venv_dir / ("Scripts" if os.name == "nt" else "bin") / "pip"
        return subprocess.run(
            [str(pip_path), *args],
            capture_output=True,
            text=True,
            **kwargs
        )
    
    def _get_installed_packages(self) -> Dict[str, str]:
        """Get installed packages and versions."""
        result = self._run_pip(["list", "--format=json"])
        return {
            pkg["name"]: pkg["version"]
            for pkg in json.loads(result.stdout)
        }
    
    def _get_package_info(self, package: str) -> Optional[Dict]:
        """Get package information from PyPI."""
        try:
            response = requests.get(f"https://pypi.org/pypi/{package}/json")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Error fetching info for {package}: {e}")
            return None
    
    def create_virtualenv(self) -> bool:
        """Create virtual environment."""
        try:
            logger.info("Creating virtual environment...")
            virtualenv.create_environment(str(self.venv_dir))
            logger.info(f"Virtual environment created at {self.venv_dir}")
            return True
        except Exception as e:
            logger.error(f"Error creating virtual environment: {e}")
            return False
    
    def install_requirements(self, req_type: str = "core") -> bool:
        """Install requirements."""
        try:
            if req_type not in self.requirements:
                logger.error(f"Unknown requirements type: {req_type}")
                return False
            
            req_file = self.requirements[req_type]
            if not req_file.exists():
                logger.error(f"Requirements file not found: {req_file}")
                return False
            
            logger.info(f"Installing {req_type} requirements...")
            result = self._run_pip(["install", "-r", str(req_file)])
            
            if result.returncode != 0:
                logger.error(f"Installation failed: {result.stderr}")
                return False
            
            logger.info("Requirements installed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error installing requirements: {e}")
            return False
    
    def check_updates(self) -> Dict[str, Dict]:
        """Check for package updates."""
        updates = {
            "available": {},
            "security": {},
            "incompatible": {}
        }
        
        try:
            installed = self._get_installed_packages()
            
            with ThreadPoolExecutor() as executor:
                futures = {
                    executor.submit(self._get_package_info, pkg): pkg
                    for pkg in installed.keys()
                }
                
                for future in tqdm(futures, desc="Checking packages"):
                    pkg = futures[future]
                    try:
                        info = future.result()
                        if info:
                            current_version = version.parse(installed[pkg])
                            latest_version = version.parse(
                                info["info"]["version"]
                            )
                            
                            if latest_version > current_version:
                                updates["available"][pkg] = {
                                    "current": str(current_version),
                                    "latest": str(latest_version)
                                }
                            
                            # Check for security releases
                            release_history = info.get("releases", {})
                            for ver, files in release_history.items():
                                if any("security" in f.get("comment", "").lower() 
                                      for f in files):
                                    updates["security"][pkg] = {
                                        "current": str(current_version),
                                        "security_version": ver
                                    }
                                    break
                    
                    except Exception as e:
                        logger.warning(f"Error checking {pkg}: {e}")
            
            return updates
            
        except Exception as e:
            logger.error(f"Error checking updates: {e}")
            return updates
    
    def analyze_dependencies(self) -> Dict:
        """Analyze project dependencies."""
        analysis = {
            "direct": {},
            "transitive": {},
            "cycles": [],
            "conflicts": [],
            "stats": {
                "total": 0,
                "direct": 0,
                "transitive": 0
            }
        }
        
        try:
            # Get direct dependencies
            for req_file in self.requirements.values():
                if req_file.exists():
                    with open(req_file) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                req = pkg_resources.Requirement.parse(line)
                                analysis["direct"][req.name] = str(req.specifier)
            
            # Get installed packages
            installed = self._get_installed_packages()
            
            # Analyze dependencies
            for pkg_name, pkg_version in installed.items():
                try:
                    dist = pkg_resources.working_set.by_key[pkg_name]
                    deps = {
                        dep.name: str(dep.specifier)
                        for dep in dist.requires()
                    }
                    
                    if pkg_name not in analysis["direct"]:
                        analysis["transitive"][pkg_name] = {
                            "version": pkg_version,
                            "dependencies": deps
                        }
                    
                    # Check for conflicts
                    for dep_name, dep_spec in deps.items():
                        if dep_name in installed:
                            dep_version = installed[dep_name]
                            if not pkg_resources.Requirement.parse(
                                f"{dep_name}{dep_spec}"
                            ).contains(dep_version):
                                analysis["conflicts"].append({
                                    "package": pkg_name,
                                    "dependency": dep_name,
                                    "required": dep_spec,
                                    "installed": dep_version
                                })
                    
                except Exception as e:
                    logger.warning(f"Error analyzing {pkg_name}: {e}")
            
            # Find dependency cycles
            def find_cycles(pkg: str, path: List[str], visited: Set[str]):
                if pkg in path:
                    cycle = path[path.index(pkg):]
                    cycle.append(pkg)
                    analysis["cycles"].append(cycle)
                    return
                
                if pkg in visited:
                    return
                
                visited.add(pkg)
                path.append(pkg)
                
                if pkg in analysis["direct"]:
                    deps = {}
                elif pkg in analysis["transitive"]:
                    deps = analysis["transitive"][pkg]["dependencies"]
                else:
                    deps = {}
                
                for dep in deps:
                    find_cycles(dep, path.copy(), visited)
            
            for pkg in analysis["direct"]:
                find_cycles(pkg, [], set())
            
            # Calculate statistics
            analysis["stats"]["direct"] = len(analysis["direct"])
            analysis["stats"]["transitive"] = len(analysis["transitive"])
            analysis["stats"]["total"] = (
                analysis["stats"]["direct"] + 
                analysis["stats"]["transitive"]
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing dependencies: {e}")
            return analysis
    
    def generate_report(self, analysis: Dict, updates: Dict) -> Path:
        """Generate dependency report."""
        report_dir = PROJECT_ROOT / "reports" / "dependencies"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = report_dir / "dependency_report.html"
        
        content = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Dependency Analysis Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            ".section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f2f2f2; }",
            ".warning { color: #f44336; }",
            ".info { color: #2196f3; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Dependency Analysis Report</h1>",
            
            "<div class='section'>",
            "<h2>Statistics</h2>",
            "<ul>",
            f"<li>Total Dependencies: {analysis['stats']['total']}</li>",
            f"<li>Direct Dependencies: {analysis['stats']['direct']}</li>",
            f"<li>Transitive Dependencies: {analysis['stats']['transitive']}</li>",
            "</ul>",
            "</div>",
            
            "<div class='section'>",
            "<h2>Direct Dependencies</h2>",
            "<table>",
            "<tr><th>Package</th><th>Version Spec</th></tr>"
        ]
        
        for pkg, spec in sorted(analysis["direct"].items()):
            content.append(f"<tr><td>{pkg}</td><td>{spec}</td></tr>")
        
        content.extend([
            "</table>",
            "</div>"
        ])
        
        if updates["available"]:
            content.extend([
                "<div class='section'>",
                "<h2>Available Updates</h2>",
                "<table>",
                "<tr><th>Package</th><th>Current</th><th>Latest</th></tr>"
            ])
            
            for pkg, info in updates["available"].items():
                content.append(
                    f"<tr><td>{pkg}</td><td>{info['current']}</td>"
                    f"<td>{info['latest']}</td></tr>"
                )
            
            content.extend([
                "</table>",
                "</div>"
            ])
        
        if updates["security"]:
            content.extend([
                "<div class='section'>",
                "<h2 class='warning'>Security Updates</h2>",
                "<table>",
                "<tr><th>Package</th><th>Current</th><th>Security Version</th></tr>"
            ])
            
            for pkg, info in updates["security"].items():
                content.append(
                    f"<tr><td>{pkg}</td><td>{info['current']}</td>"
                    f"<td>{info['security_version']}</td></tr>"
                )
            
            content.extend([
                "</table>",
                "</div>"
            ])
        
        if analysis["conflicts"]:
            content.extend([
                "<div class='section'>",
                "<h2 class='warning'>Dependency Conflicts</h2>",
                "<table>",
                "<tr><th>Package</th><th>Dependency</th><th>Required</th>"
                "<th>Installed</th></tr>"
            ])
            
            for conflict in analysis["conflicts"]:
                content.append(
                    f"<tr><td>{conflict['package']}</td>"
                    f"<td>{conflict['dependency']}</td>"
                    f"<td>{conflict['required']}</td>"
                    f"<td>{conflict['installed']}</td></tr>"
                )
            
            content.extend([
                "</table>",
                "</div>"
            ])
        
        if analysis["cycles"]:
            content.extend([
                "<div class='section'>",
                "<h2 class='warning'>Dependency Cycles</h2>",
                "<ul>"
            ])
            
            for cycle in analysis["cycles"]:
                content.append(f"<li>{' → '.join(cycle)}</li>")
            
            content.extend([
                "</ul>",
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
        description="Jarvis AI Assistant Dependency Manager"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Create virtualenv command
    subparsers.add_parser("create-venv", help="Create virtual environment")
    
    # Install requirements command
    install_parser = subparsers.add_parser("install", help="Install requirements")
    install_parser.add_argument(
        "--type",
        choices=list(REQUIREMENTS.keys()),
        default="core",
        help="Requirements type to install"
    )
    
    # Check updates command
    subparsers.add_parser("check-updates", help="Check for package updates")
    
    # Analyze dependencies command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze project dependencies"
    )
    analyze_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    manager = DependencyManager()
    
    try:
        if args.command == "create-venv":
            success = manager.create_virtualenv()
            sys.exit(0 if success else 1)
        
        elif args.command == "install":
            success = manager.install_requirements(args.type)
            sys.exit(0 if success else 1)
        
        elif args.command == "check-updates":
            updates = manager.check_updates()
            
            print("\nAvailable Updates:")
            for pkg, info in updates["available"].items():
                print(f"- {pkg}: {info['current']} → {info['latest']}")
            
            if updates["security"]:
                print("\nSecurity Updates:")
                for pkg, info in updates["security"].items():
                    print(
                        f"- {pkg}: {info['current']} → {info['security_version']}"
                    )
        
        elif args.command == "analyze":
            analysis = manager.analyze_dependencies()
            updates = manager.check_updates()
            
            if args.json:
                print(json.dumps(
                    {"analysis": analysis, "updates": updates},
                    indent=2
                ))
            else:
                report_file = manager.generate_report(analysis, updates)
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
