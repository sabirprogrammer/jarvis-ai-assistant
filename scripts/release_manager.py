#!/usr/bin/env python3
"""
Release management tools for Jarvis AI Assistant.
This script provides utilities for managing releases, including version control,
changelog generation, and release automation.
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
import semver
import git
from github import Github
import toml
from jinja2 import Template
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
CHANGELOG_FILE = PROJECT_ROOT / "CHANGELOG.md"
VERSION_FILE = PROJECT_ROOT / "VERSION"
REPORTS_DIR = PROJECT_ROOT / "reports" / "releases"

class ReleaseManager:
    """Release management utility class."""
    
    def __init__(self):
        """Initialize release manager."""
        self.reports_dir = REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize git repository
        self.repo = git.Repo(PROJECT_ROOT)
        
        # Load GitHub token if available
        self.github = None
        if gh_token := os.getenv("GITHUB_TOKEN"):
            self.github = Github(gh_token)
    
    def get_current_version(self) -> str:
        """Get current version from VERSION file."""
        try:
            if VERSION_FILE.exists():
                return VERSION_FILE.read_text().strip()
            return "0.1.0"
        except Exception as e:
            logger.error(f"Error reading version: {e}")
            return "0.1.0"
    
    def bump_version(
        self,
        bump_type: str = "patch",
        specific_version: Optional[str] = None
    ) -> Tuple[str, str]:
        """Bump version number."""
        current = self.get_current_version()
        
        try:
            if specific_version:
                new = specific_version
                # Validate version format
                semver.VersionInfo.parse(new)
            else:
                ver = semver.VersionInfo.parse(current)
                if bump_type == "major":
                    new = str(ver.bump_major())
                elif bump_type == "minor":
                    new = str(ver.bump_minor())
                else:  # patch
                    new = str(ver.bump_patch())
            
            # Update VERSION file
            VERSION_FILE.write_text(new)
            
            return current, new
            
        except Exception as e:
            logger.error(f"Error bumping version: {e}")
            return current, current
    
    def update_changelog(
        self,
        version: str,
        changes: Dict[str, List[str]]
    ) -> bool:
        """Update CHANGELOG.md with new changes."""
        try:
            # Create changelog if it doesn't exist
            if not CHANGELOG_FILE.exists():
                CHANGELOG_FILE.write_text(
                    "# Changelog\n\nAll notable changes to this project "
                    "will be documented in this file.\n\n"
                )
            
            current_content = CHANGELOG_FILE.read_text()
            
            # Prepare new entry
            new_entry = [
                f"\n## [{version}] - {datetime.now().strftime('%Y-%m-%d')}\n"
            ]
            
            for category, items in changes.items():
                if items:
                    new_entry.extend([
                        f"\n### {category}\n"
                    ])
                    for item in items:
                        new_entry.append(f"- {item}\n")
            
            # Insert after header
            header_end = current_content.find("\n\n") + 2
            updated_content = (
                current_content[:header_end] +
                "".join(new_entry) +
                current_content[header_end:]
            )
            
            CHANGELOG_FILE.write_text(updated_content)
            return True
            
        except Exception as e:
            logger.error(f"Error updating changelog: {e}")
            return False
    
    def collect_changes(self, since_tag: Optional[str] = None) -> Dict[str, List[str]]:
        """Collect changes since last release."""
        changes = {
            "Added": [],
            "Changed": [],
            "Deprecated": [],
            "Removed": [],
            "Fixed": [],
            "Security": []
        }
        
        try:
            # Get commit range
            if since_tag:
                commit_range = f"{since_tag}..HEAD"
            else:
                tags = sorted(self.repo.tags, key=lambda t: t.commit.committed_date)
                if tags:
                    commit_range = f"{tags[-1]}..HEAD"
                else:
                    commit_range = "HEAD"
            
            # Get commits
            commits = list(self.repo.iter_commits(commit_range))
            
            # Process commits
            for commit in commits:
                message = commit.message.strip()
                
                # Skip merge commits
                if message.startswith("Merge"):
                    continue
                
                # Categorize based on conventional commits
                if message.startswith("feat"):
                    changes["Added"].append(
                        message.split(":", 1)[1].strip()
                    )
                elif message.startswith("fix"):
                    changes["Fixed"].append(
                        message.split(":", 1)[1].strip()
                    )
                elif message.startswith("chore"):
                    changes["Changed"].append(
                        message.split(":", 1)[1].strip()
                    )
                elif message.startswith("refactor"):
                    changes["Changed"].append(
                        message.split(":", 1)[1].strip()
                    )
                elif message.startswith("docs"):
                    changes["Changed"].append(
                        message.split(":", 1)[1].strip()
                    )
                elif message.startswith("style"):
                    changes["Changed"].append(
                        message.split(":", 1)[1].strip()
                    )
                elif message.startswith("perf"):
                    changes["Changed"].append(
                        message.split(":", 1)[1].strip()
                    )
                elif message.startswith("test"):
                    continue  # Skip test commits
                elif message.startswith("build"):
                    continue  # Skip build commits
                elif message.startswith("ci"):
                    continue  # Skip CI commits
                else:
                    # Try to guess category from message
                    lower_msg = message.lower()
                    if "deprecat" in lower_msg:
                        changes["Deprecated"].append(message)
                    elif "remove" in lower_msg:
                        changes["Removed"].append(message)
                    elif "security" in lower_msg:
                        changes["Security"].append(message)
                    else:
                        changes["Changed"].append(message)
            
            return changes
            
        except Exception as e:
            logger.error(f"Error collecting changes: {e}")
            return changes
    
    def create_release(
        self,
        version: str,
        changes: Dict[str, List[str]],
        draft: bool = True
    ) -> bool:
        """Create a new release."""
        try:
            if not self.github:
                logger.error("GitHub token not available")
                return False
            
            # Get repository
            repo_name = self.repo.remotes.origin.url.split(".git")[0].split("/")[-2:]
            repo = self.github.get_repo("/".join(repo_name))
            
            # Create release notes
            notes = [
                f"# Release {version}\n",
                f"Released on {datetime.now().strftime('%Y-%m-%d')}\n"
            ]
            
            for category, items in changes.items():
                if items:
                    notes.extend([
                        f"\n## {category}\n"
                    ])
                    for item in items:
                        notes.append(f"- {item}\n")
            
            # Create tag
            tag_name = f"v{version}"
            tag_message = f"Release {version}"
            
            # Create release
            release = repo.create_git_release(
                tag_name,
                f"Release {version}",
                "".join(notes),
                draft=draft,
                prerelease=False
            )
            
            logger.info(f"Created release {version}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating release: {e}")
            return False
    
    def update_version_files(self, version: str) -> bool:
        """Update version in project files."""
        try:
            files_updated = []
            
            # Update setup.py
            setup_file = PROJECT_ROOT / "setup.py"
            if setup_file.exists():
                content = setup_file.read_text()
                new_content = re.sub(
                    r'version="[^"]*"',
                    f'version="{version}"',
                    content
                )
                setup_file.write_text(new_content)
                files_updated.append(setup_file)
            
            # Update pyproject.toml
            pyproject_file = PROJECT_ROOT / "pyproject.toml"
            if pyproject_file.exists():
                data = toml.load(pyproject_file)
                if "tool" in data and "poetry" in data["tool"]:
                    data["tool"]["poetry"]["version"] = version
                    pyproject_file.write_text(toml.dumps(data))
                    files_updated.append(pyproject_file)
            
            # Update package __init__.py
            init_files = list(PROJECT_ROOT.rglob("__init__.py"))
            for init_file in init_files:
                content = init_file.read_text()
                if "__version__" in content:
                    new_content = re.sub(
                        r'__version__\s*=\s*["\'][^"\']*["\']',
                        f'__version__ = "{version}"',
                        content
                    )
                    init_file.write_text(new_content)
                    files_updated.append(init_file)
            
            if files_updated:
                logger.info(
                    f"Updated version to {version} in: "
                    f"{', '.join(str(f.relative_to(PROJECT_ROOT)) for f in files_updated)}"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating version files: {e}")
            return False
    
    def check_release_readiness(self) -> Dict:
        """Check if project is ready for release."""
        results = {
            "ready": True,
            "checks": [],
            "warnings": [],
            "errors": []
        }
        
        try:
            # Check for uncommitted changes
            if self.repo.is_dirty():
                results["errors"].append(
                    "There are uncommitted changes"
                )
                results["ready"] = False
            
            # Check tests
            try:
                subprocess.run(
                    ["pytest"],
                    check=True,
                    capture_output=True
                )
                results["checks"].append("All tests passing")
            except subprocess.CalledProcessError:
                results["errors"].append("Tests are failing")
                results["ready"] = False
            
            # Check code quality
            try:
                subprocess.run(
                    ["flake8"],
                    check=True,
                    capture_output=True
                )
                results["checks"].append("Code quality checks passing")
            except subprocess.CalledProcessError:
                results["warnings"].append("Code quality issues found")
            
            # Check documentation
            docs_dir = PROJECT_ROOT / "docs"
            if not docs_dir.exists():
                results["warnings"].append("Documentation directory not found")
            else:
                try:
                    subprocess.run(
                        ["sphinx-build", "-b", "html", "docs", "docs/_build"],
                        check=True,
                        capture_output=True
                    )
                    results["checks"].append("Documentation builds successfully")
                except subprocess.CalledProcessError:
                    results["warnings"].append("Documentation build failed")
            
            # Check dependencies
            requirements_file = PROJECT_ROOT / "requirements.txt"
            if requirements_file.exists():
                try:
                    subprocess.run(
                        ["pip", "check"],
                        check=True,
                        capture_output=True
                    )
                    results["checks"].append("Dependencies are compatible")
                except subprocess.CalledProcessError:
                    results["warnings"].append("Dependency conflicts found")
            
            # Check changelog
            if not CHANGELOG_FILE.exists():
                results["warnings"].append("CHANGELOG.md not found")
            
            # Check version file
            if not VERSION_FILE.exists():
                results["warnings"].append("VERSION file not found")
            
            return results
            
        except Exception as e:
            logger.error(f"Error checking release readiness: {e}")
            results["errors"].append(str(e))
            results["ready"] = False
            return results
    
    def generate_report(
        self,
        version: str,
        changes: Dict[str, List[str]],
        checks: Dict
    ) -> Path:
        """Generate release report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f"release_report_{timestamp}.html"
        
        content = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Release Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            ".section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f2f2f2; }",
            ".success { color: #4caf50; }",
            ".warning { color: #ff9800; }",
            ".error { color: #f44336; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Release Report</h1>",
            f"<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
            
            "<div class='section'>",
            "<h2>Release Information</h2>",
            f"<p><strong>Version:</strong> {version}</p>",
            "<h3>Changes</h3>"
        ]
        
        for category, items in changes.items():
            if items:
                content.extend([
                    f"<h4>{category}</h4>",
                    "<ul>"
                ])
                for item in items:
                    content.append(f"<li>{item}</li>")
                content.append("</ul>")
        
        content.extend([
            "</div>",
            "<div class='section'>",
            "<h2>Release Readiness</h2>",
            f"<p><strong>Status:</strong> <span class='{'success' if checks['ready'] else 'error'}'>"
            f"{'Ready' if checks['ready'] else 'Not Ready'}</span></p>"
        ])
        
        if checks["checks"]:
            content.extend([
                "<h3>Passed Checks</h3>",
                "<ul>"
            ])
            for check in checks["checks"]:
                content.append(f"<li class='success'>{check}</li>")
            content.append("</ul>")
        
        if checks["warnings"]:
            content.extend([
                "<h3>Warnings</h3>",
                "<ul>"
            ])
            for warning in checks["warnings"]:
                content.append(f"<li class='warning'>{warning}</li>")
            content.append("</ul>")
        
        if checks["errors"]:
            content.extend([
                "<h3>Errors</h3>",
                "<ul>"
            ])
            for error in checks["errors"]:
                content.append(f"<li class='error'>{error}</li>")
            content.append("</ul>")
        
        content.extend([
            "</div>",
            "</body>",
            "</html>"
        ])
        
        report_file.write_text("\n".join(content))
        return report_file

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Jarvis AI Assistant Release Manager"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Bump version command
    bump_parser = subparsers.add_parser("bump", help="Bump version")
    bump_parser.add_argument(
        "type",
        choices=["major", "minor", "patch"],
        help="Version bump type"
    )
    bump_parser.add_argument(
        "--specific",
        help="Set specific version"
    )
    
    # Update changelog command
    changelog_parser = subparsers.add_parser(
        "changelog",
        help="Update changelog"
    )
    changelog_parser.add_argument(
        "--since",
        help="Since tag"
    )
    
    # Create release command
    release_parser = subparsers.add_parser(
        "release",
        help="Create release"
    )
    release_parser.add_argument(
        "--no-draft",
        action="store_true",
        help="Create as non-draft release"
    )
    
    # Check readiness command
    check_parser = subparsers.add_parser(
        "check",
        help="Check release readiness"
    )
    check_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    manager = ReleaseManager()
    
    try:
        if args.command == "bump":
            current, new = manager.bump_version(
                args.type,
                args.specific
            )
            logger.info(f"Bumped version: {current} → {new}")
            
            # Update version in project files
            manager.update_version_files(new)
        
        elif args.command == "changelog":
            changes = manager.collect_changes(args.since)
            version = manager.get_current_version()
            
            if manager.update_changelog(version, changes):
                logger.info("Updated changelog")
            else:
                sys.exit(1)
        
        elif args.command == "release":
            # Check readiness
            checks = manager.check_release_readiness()
            if not checks["ready"]:
                logger.error("Project not ready for release:")
                for error in checks["errors"]:
                    logger.error(f"- {error}")
                for warning in checks["warnings"]:
                    logger.warning(f"- {warning}")
                sys.exit(1)
            
            # Collect changes
            version = manager.get_current_version()
            changes = manager.collect_changes()
            
            # Create release
            if manager.create_release(version, changes, not args.no_draft):
                logger.info(f"Created release {version}")
            else:
                sys.exit(1)
        
        elif args.command == "check":
            checks = manager.check_release_readiness()
            
            if args.json:
                print(json.dumps(checks, indent=2))
            else:
                version = manager.get_current_version()
                changes = manager.collect_changes()
                
                report_file = manager.generate_report(
                    version,
                    changes,
                    checks
                )
                logger.info(f"Report generated: {report_file}")
            
            if not checks["ready"]:
                sys.exit(1)
        
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
