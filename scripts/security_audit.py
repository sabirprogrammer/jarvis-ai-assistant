#!/usr/bin/env python3
"""
Security audit tools for Jarvis AI Assistant.
This script provides utilities for security auditing, including
dependency scanning, code analysis, and security report generation.
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
import requests
import hashlib
import secrets
import bandit
from bandit.core import manager as bandit_manager
from safety.safety import check as safety_check
from safety.util import read_requirements
import jwt
from cryptography.fernet import Fernet
import docker
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "security"
SECRETS_DIR = PROJECT_ROOT / "secrets"

class SecurityAuditor:
    """Security auditing utility class."""
    
    def __init__(self):
        """Initialize security auditor."""
        self.reports_dir = REPORTS_DIR
        self.secrets_dir = SECRETS_DIR
        
        # Create necessary directories
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.secrets_dir.mkdir(exist_ok=True)
        
        # Initialize Docker client
        try:
            self.docker = docker.from_env()
        except Exception as e:
            logger.warning(f"Could not initialize Docker client: {e}")
            self.docker = None
    
    def scan_dependencies(self) -> Dict:
        """Scan dependencies for security vulnerabilities."""
        results = {
            "vulnerabilities": [],
            "affected_packages": set(),
            "total_issues": 0,
            "severity_counts": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0
            }
        }
        
        try:
            # Get requirements
            requirements = []
            req_files = [
                "requirements.txt",
                "requirements-dev.txt",
                "requirements-test.txt"
            ]
            
            for req_file in req_files:
                req_path = PROJECT_ROOT / req_file
                if req_path.exists():
                    requirements.extend(read_requirements(str(req_path)))
            
            # Check dependencies
            vulns = safety_check(requirements)
            
            # Process results
            for package, vuln_id, spec, vuln_data in vulns:
                severity = vuln_data.get("severity", "unknown").lower()
                if severity in results["severity_counts"]:
                    results["severity_counts"][severity] += 1
                
                results["vulnerabilities"].append({
                    "package": package,
                    "vulnerability_id": vuln_id,
                    "affected_versions": spec,
                    "severity": severity,
                    "description": vuln_data.get("description", ""),
                    "references": vuln_data.get("references", [])
                })
                
                results["affected_packages"].add(package)
            
            results["total_issues"] = len(results["vulnerabilities"])
            results["affected_packages"] = list(results["affected_packages"])
            
            return results
            
        except Exception as e:
            logger.error(f"Error scanning dependencies: {e}")
            return results
    
    def scan_code(self) -> Dict:
        """Scan code for security issues."""
        results = {
            "issues": [],
            "stats": {
                "total_files": 0,
                "total_lines": 0,
                "total_issues": 0
            },
            "severity_counts": {
                "high": 0,
                "medium": 0,
                "low": 0
            }
        }
        
        try:
            # Configure Bandit
            b_mgr = bandit_manager.BanditManager()
            b_mgr.discover_files([str(PROJECT_ROOT)])
            b_mgr.run_tests()
            
            # Process results
            for issue in b_mgr.get_issue_list():
                severity = issue.severity.lower()
                if severity in results["severity_counts"]:
                    results["severity_counts"][severity] += 1
                
                results["issues"].append({
                    "file": issue.fname,
                    "line": issue.lineno,
                    "issue_type": issue.test_id,
                    "issue_text": issue.text,
                    "severity": severity,
                    "confidence": issue.confidence,
                    "code": issue.get_code()
                })
            
            # Collect statistics
            results["stats"]["total_files"] = len(b_mgr.files_list)
            results["stats"]["total_lines"] = sum(
                len(open(f).readlines())
                for f in b_mgr.files_list
            )
            results["stats"]["total_issues"] = len(results["issues"])
            
            return results
            
        except Exception as e:
            logger.error(f"Error scanning code: {e}")
            return results
    
    def scan_secrets(self) -> Dict:
        """Scan for exposed secrets in code."""
        results = {
            "exposed_secrets": [],
            "stats": {
                "files_scanned": 0,
                "secrets_found": 0
            }
        }
        
        try:
            # Patterns to search for
            secret_patterns = {
                "api_key": r'(?i)api[_-]key.*[\'"][0-9a-zA-Z]{32,}[\'"]',
                "access_token": r'(?i)access[_-]token.*[\'"][0-9a-zA-Z]{32,}[\'"]',
                "secret_key": r'(?i)secret[_-]key.*[\'"][0-9a-zA-Z]{32,}[\'"]',
                "password": r'(?i)password.*[\'"][^\'"\s]{8,}[\'"]',
                "private_key": r'-----BEGIN (?:RSA )?PRIVATE KEY-----',
                "aws_key": r'(?i)aws[_-](?:access[_-])?key[_-]id.*[\'"][A-Z0-9]{20}[\'"]',
                "aws_secret": r'(?i)aws[_-]secret[_-]access[_-]key.*[\'"][A-Za-z0-9/+=]{40}[\'"]',
                "github_token": r'(?i)github[_-]token.*[\'"][0-9a-zA-Z]{40}[\'"]',
                "google_key": r'(?i)google[_-](?:api[_-])?key.*[\'"][A-Za-z0-9-_]{39}[\'"]',
                "slack_token": r'xox[baprs]-[0-9a-zA-Z]{10,48}',
                "stripe_key": r'(?i)stripe[_-](?:api[_-])?key.*[\'"](?:sk|pk)_(?:test|live)_[0-9a-zA-Z]{24,}'
            }
            
            # Scan files
            for file_path in PROJECT_ROOT.rglob("*"):
                if file_path.is_file() and not any(
                    part.startswith(".")
                    for part in file_path.parts
                ):
                    try:
                        content = file_path.read_text()
                        results["stats"]["files_scanned"] += 1
                        
                        for secret_type, pattern in secret_patterns.items():
                            matches = re.finditer(pattern, content)
                            for match in matches:
                                results["exposed_secrets"].append({
                                    "file": str(file_path.relative_to(PROJECT_ROOT)),
                                    "line": content.count('\n', 0, match.start()) + 1,
                                    "type": secret_type,
                                    "match": match.group()[:20] + "..."  # Truncate for safety
                                })
                                results["stats"]["secrets_found"] += 1
                    
                    except Exception:
                        continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error scanning for secrets: {e}")
            return results
    
    def scan_docker(self) -> Dict:
        """Scan Docker configuration for security issues."""
        results = {
            "issues": [],
            "best_practices": [],
            "stats": {
                "total_issues": 0,
                "severity_counts": {
                    "high": 0,
                    "medium": 0,
                    "low": 0
                }
            }
        }
        
        try:
            dockerfile = PROJECT_ROOT / "Dockerfile"
            if not dockerfile.exists():
                return results
            
            content = dockerfile.read_text()
            
            # Check for common issues
            checks = [
                {
                    "pattern": r"FROM\s+[^:]+(?!:)",
                    "severity": "high",
                    "message": "Image tag not specified, may use floating tag"
                },
                {
                    "pattern": r"FROM\s+[^@]+(?!@sha256:)",
                    "severity": "medium",
                    "message": "Image digest not specified, consider using SHA256 digest"
                },
                {
                    "pattern": r"(?i)apt-get\s+install(?!\s+--no-install-recommends)",
                    "severity": "low",
                    "message": "Consider using --no-install-recommends with apt-get install"
                },
                {
                    "pattern": r"(?i)apt-get(?!\s+update)",
                    "severity": "medium",
                    "message": "apt-get update should be run before install"
                },
                {
                    "pattern": r"(?i)sudo",
                    "severity": "medium",
                    "message": "Avoid using sudo in Dockerfile"
                },
                {
                    "pattern": r"chmod\s+777",
                    "severity": "high",
                    "message": "Avoid using chmod 777"
                },
                {
                    "pattern": r"ADD\s+",
                    "severity": "low",
                    "message": "Consider using COPY instead of ADD"
                }
            ]
            
            for check in checks:
                matches = re.finditer(check["pattern"], content)
                for match in matches:
                    line_number = content.count('\n', 0, match.start()) + 1
                    
                    results["issues"].append({
                        "line": line_number,
                        "severity": check["severity"],
                        "message": check["message"],
                        "code": match.group().strip()
                    })
                    
                    results["stats"]["severity_counts"][check["severity"]] += 1
                    results["stats"]["total_issues"] += 1
            
            # Check best practices
            best_practices = [
                {
                    "check": r"HEALTHCHECK",
                    "message": "Include HEALTHCHECK instruction"
                },
                {
                    "check": r"USER\s+[^root]",
                    "message": "Run container as non-root user"
                },
                {
                    "check": r"COPY\s+--chown=",
                    "message": "Set proper file ownership"
                }
            ]
            
            for practice in best_practices:
                if not re.search(practice["check"], content):
                    results["best_practices"].append(practice["message"])
            
            return results
            
        except Exception as e:
            logger.error(f"Error scanning Docker configuration: {e}")
            return results
    
    def generate_report(
        self,
        dependency_results: Optional[Dict] = None,
        code_results: Optional[Dict] = None,
        secrets_results: Optional[Dict] = None,
        docker_results: Optional[Dict] = None
    ) -> Path:
        """Generate security audit report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f"security_report_{timestamp}.html"
        
        content = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Security Audit Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            ".section { margin: 20px 0; padding: 20px; border: 1px solid #ddd; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f2f2f2; }",
            ".critical { color: #9c1f1f; }",
            ".high { color: #c41e3a; }",
            ".medium { color: #ff9800; }",
            ".low { color: #4caf50; }",
            "pre { background: #f5f5f5; padding: 10px; overflow-x: auto; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>Security Audit Report</h1>",
            f"<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        ]
        
        # Dependency section
        if dependency_results:
            content.extend([
                "<div class='section'>",
                "<h2>Dependency Security Scan</h2>",
                f"<p>Total Issues: {dependency_results['total_issues']}</p>",
                "<h3>Severity Distribution</h3>",
                "<table>",
                "<tr><th>Severity</th><th>Count</th></tr>"
            ])
            
            for severity, count in dependency_results["severity_counts"].items():
                content.append(
                    f"<tr><td class='{severity}'>{severity.title()}</td>"
                    f"<td>{count}</td></tr>"
                )
            
            content.extend([
                "</table>",
                "<h3>Vulnerabilities</h3>",
                "<table>",
                "<tr><th>Package</th><th>Severity</th><th>Description</th></tr>"
            ])
            
            for vuln in dependency_results["vulnerabilities"]:
                content.append(
                    f"<tr><td>{vuln['package']}</td>"
                    f"<td class='{vuln['severity']}'>{vuln['severity'].title()}</td>"
                    f"<td>{vuln['description']}</td></tr>"
                )
            
            content.extend([
                "</table>",
                "</div>"
            ])
        
        # Code scan section
        if code_results:
            content.extend([
                "<div class='section'>",
                "<h2>Code Security Scan</h2>",
                "<h3>Statistics</h3>",
                "<ul>",
                f"<li>Files Scanned: {code_results['stats']['total_files']}</li>",
                f"<li>Lines of Code: {code_results['stats']['total_lines']}</li>",
                f"<li>Issues Found: {code_results['stats']['total_issues']}</li>",
                "</ul>",
                "<h3>Issues</h3>",
                "<table>",
                "<tr><th>File</th><th>Line</th><th>Severity</th><th>Issue</th></tr>"
            ])
            
            for issue in code_results["issues"]:
                content.append(
                    f"<tr><td>{issue['file']}</td><td>{issue['line']}</td>"
                    f"<td class='{issue['severity']}'>{issue['severity'].title()}</td>"
                    f"<td>{issue['issue_text']}</td></tr>"
                )
            
            content.extend([
                "</table>",
                "</div>"
            ])
        
        # Secrets scan section
        if secrets_results:
            content.extend([
                "<div class='section'>",
                "<h2>Secrets Scan</h2>",
                "<h3>Statistics</h3>",
                "<ul>",
                f"<li>Files Scanned: {secrets_results['stats']['files_scanned']}</li>",
                f"<li>Secrets Found: {secrets_results['stats']['secrets_found']}</li>",
                "</ul>"
            ])
            
            if secrets_results["exposed_secrets"]:
                content.extend([
                    "<h3>Exposed Secrets</h3>",
                    "<table>",
                    "<tr><th>File</th><th>Line</th><th>Type</th></tr>"
                ])
                
                for secret in secrets_results["exposed_secrets"]:
                    content.append(
                        f"<tr><td>{secret['file']}</td><td>{secret['line']}</td>"
                        f"<td>{secret['type']}</td></tr>"
                    )
                
                content.append("</table>")
            
            content.append("</div>")
        
        # Docker scan section
        if docker_results:
            content.extend([
                "<div class='section'>",
                "<h2>Docker Security Scan</h2>",
                "<h3>Issues</h3>",
                "<table>",
                "<tr><th>Line</th><th>Severity</th><th>Message</th></tr>"
            ])
            
            for issue in docker_results["issues"]:
                content.append(
                    f"<tr><td>{issue['line']}</td>"
                    f"<td class='{issue['severity']}'>{issue['severity'].title()}</td>"
                    f"<td>{issue['message']}</td></tr>"
                )
            
            content.extend([
                "</table>",
                "<h3>Best Practices</h3>",
                "<ul>"
            ])
            
            for practice in docker_results["best_practices"]:
                content.append(f"<li>{practice}</li>")
            
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
        description="Jarvis AI Assistant Security Auditor"
    )
    
    parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="Skip dependency scanning"
    )
    
    parser.add_argument(
        "--skip-code",
        action="store_true",
        help="Skip code scanning"
    )
    
    parser.add_argument(
        "--skip-secrets",
        action="store_true",
        help="Skip secrets scanning"
    )
    
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip Docker scanning"
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
    auditor = SecurityAuditor()
    
    try:
        results = {}
        
        # Run scans
        if not args.skip_deps:
            logger.info("Scanning dependencies...")
            results["dependencies"] = auditor.scan_dependencies()
        
        if not args.skip_code:
            logger.info("Scanning code...")
            results["code"] = auditor.scan_code()
        
        if not args.skip_secrets:
            logger.info("Scanning for secrets...")
            results["secrets"] = auditor.scan_secrets()
        
        if not args.skip_docker:
            logger.info("Scanning Docker configuration...")
            results["docker"] = auditor.scan_docker()
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            report_file = auditor.generate_report(
                results.get("dependencies"),
                results.get("code"),
                results.get("secrets"),
                results.get("docker")
            )
            logger.info(f"Report generated: {report_file}")
        
        # Exit with error if critical/high severity issues found
        has_critical = any(
            results.get(scan, {}).get("severity_counts", {}).get("critical", 0) > 0
            for scan in ["dependencies", "code"]
        )
        has_high = any(
            results.get(scan, {}).get("severity_counts", {}).get("high", 0) > 0
            for scan in ["dependencies", "code"]
        )
        
        if has_critical or has_high:
            sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
