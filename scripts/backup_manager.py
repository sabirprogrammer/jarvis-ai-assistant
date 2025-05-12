#!/usr/bin/env python3
"""
Backup and restore utility for Jarvis AI Assistant.
This script provides utilities for managing backups of application data,
configurations, and databases.
"""

import os
import sys
import argparse
from pathlib import Path
import logging
import json
import yaml
from typing import Dict, List, Optional, Set
import shutil
import tarfile
import zipfile
from datetime import datetime
import hashlib
import sqlite3
import asyncio
import aiosqlite
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
BACKUP_DIR = PROJECT_ROOT / "backups"
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
EXCLUDE_PATTERNS = {
    r'.*\.pyc$',
    r'.*\.git/.*',
    r'.*\.venv/.*',
    r'.*__pycache__/.*',
    r'.*/\..+',
    r'.*/node_modules/.*',
    r'.*/backups/.*'
}

class BackupManager:
    """Backup and restore utility class."""
    
    def __init__(self):
        """Initialize backup manager."""
        self.backup_dir = BACKUP_DIR
        self.data_dir = DATA_DIR
        self.config_dir = CONFIG_DIR
        
        # Create necessary directories
        self.backup_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        self.config_dir.mkdir(exist_ok=True)
    
    def _should_exclude(self, path: str) -> bool:
        """Check if path should be excluded from backup."""
        return any(re.match(pattern, path) for pattern in EXCLUDE_PATTERNS)
    
    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    async def backup_database(self, db_path: Path, backup_path: Path) -> bool:
        """Create a backup of SQLite database."""
        try:
            if not db_path.exists():
                logger.error(f"Database file not found: {db_path}")
                return False
            
            # Create backup using SQLite backup API
            async with aiosqlite.connect(db_path) as source_db:
                async with aiosqlite.connect(backup_path) as backup_db:
                    await source_db.backup(backup_db)
            
            # Verify backup integrity
            async with aiosqlite.connect(backup_path) as db:
                async with db.execute("PRAGMA integrity_check") as cursor:
                    result = await cursor.fetchone()
                    if result[0] != "ok":
                        raise Exception("Backup integrity check failed")
            
            logger.info(f"Database backup created: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error backing up database: {e}")
            return False
    
    def create_backup(self, include_db: bool = True) -> Optional[Path]:
        """Create a complete backup of application data."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"jarvis_backup_{timestamp}"
            backup_dir = self.backup_dir / backup_name
            backup_dir.mkdir()
            
            # Create manifest
            manifest = {
                "timestamp": timestamp,
                "version": "1.0.0",
                "contents": {
                    "data": [],
                    "config": [],
                    "database": None
                },
                "hashes": {}
            }
            
            # Backup data files
            if self.data_dir.exists():
                data_backup = backup_dir / "data"
                data_backup.mkdir()
                
                for item in self.data_dir.rglob("*"):
                    if item.is_file() and not self._should_exclude(str(item)):
                        rel_path = item.relative_to(self.data_dir)
                        backup_path = data_backup / rel_path
                        backup_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, backup_path)
                        
                        manifest["contents"]["data"].append(str(rel_path))
                        manifest["hashes"][str(rel_path)] = self._calculate_hash(backup_path)
            
            # Backup configuration files
            if self.config_dir.exists():
                config_backup = backup_dir / "config"
                config_backup.mkdir()
                
                for item in self.config_dir.rglob("*"):
                    if item.is_file() and not self._should_exclude(str(item)):
                        rel_path = item.relative_to(self.config_dir)
                        backup_path = config_backup / rel_path
                        backup_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, backup_path)
                        
                        manifest["contents"]["config"].append(str(rel_path))
                        manifest["hashes"][str(rel_path)] = self._calculate_hash(backup_path)
            
            # Backup database
            if include_db:
                db_path = self.data_dir / "jarvis.db"
                if db_path.exists():
                    db_backup = backup_dir / "database" / "jarvis.db"
                    db_backup.parent.mkdir()
                    
                    asyncio.run(self.backup_database(db_path, db_backup))
                    manifest["contents"]["database"] = "jarvis.db"
                    manifest["hashes"]["database"] = self._calculate_hash(db_backup)
            
            # Save manifest
            manifest_path = backup_dir / "manifest.json"
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Create archive
            archive_path = self.backup_dir / f"{backup_name}.tar.gz"
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(backup_dir, arcname=backup_name)
            
            # Clean up temporary directory
            shutil.rmtree(backup_dir)
            
            logger.info(f"Backup created: {archive_path}")
            return archive_path
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            if backup_dir and backup_dir.exists():
                shutil.rmtree(backup_dir)
            return None
    
    def restore_backup(self, backup_path: Path, include_db: bool = True) -> bool:
        """Restore from a backup archive."""
        try:
            # Create temporary directory
            temp_dir = self.backup_dir / "temp_restore"
            temp_dir.mkdir()
            
            try:
                # Extract archive
                with tarfile.open(backup_path, "r:gz") as tar:
                    tar.extractall(temp_dir)
                
                # Find backup directory
                backup_dir = next(temp_dir.iterdir())
                
                # Load and verify manifest
                manifest_path = backup_dir / "manifest.json"
                with open(manifest_path) as f:
                    manifest = json.load(f)
                
                # Verify file hashes
                for rel_path, stored_hash in manifest["hashes"].items():
                    if rel_path == "database":
                        file_path = backup_dir / "database" / "jarvis.db"
                    else:
                        file_path = backup_dir / rel_path
                    
                    if file_path.exists():
                        current_hash = self._calculate_hash(file_path)
                        if current_hash != stored_hash:
                            raise Exception(f"Hash mismatch for {rel_path}")
                
                # Restore data files
                if manifest["contents"]["data"]:
                    data_backup = backup_dir / "data"
                    if data_backup.exists():
                        for item in manifest["contents"]["data"]:
                            source = data_backup / item
                            target = self.data_dir / item
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(source, target)
                
                # Restore configuration files
                if manifest["contents"]["config"]:
                    config_backup = backup_dir / "config"
                    if config_backup.exists():
                        for item in manifest["contents"]["config"]:
                            source = config_backup / item
                            target = self.config_dir / item
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(source, target)
                
                # Restore database
                if include_db and manifest["contents"]["database"]:
                    db_backup = backup_dir / "database" / "jarvis.db"
                    if db_backup.exists():
                        db_path = self.data_dir / "jarvis.db"
                        if db_path.exists():
                            db_path.rename(db_path.with_suffix(".db.bak"))
                        
                        asyncio.run(self.backup_database(db_backup, db_path))
                
                logger.info("Backup restored successfully")
                return True
                
            finally:
                # Clean up
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            
        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            return False
    
    def list_backups(self) -> List[Dict]:
        """List available backups."""
        backups = []
        
        for backup_file in self.backup_dir.glob("*.tar.gz"):
            try:
                with tarfile.open(backup_file, "r:gz") as tar:
                    manifest_info = tar.getmember(
                        f"{backup_file.stem}/manifest.json"
                    )
                    manifest_f = tar.extractfile(manifest_info)
                    manifest = json.load(manifest_f)
                
                backups.append({
                    "file": backup_file.name,
                    "timestamp": manifest["timestamp"],
                    "version": manifest.get("version", "unknown"),
                    "size": backup_file.stat().st_size,
                    "contents": manifest["contents"]
                })
                
            except Exception as e:
                logger.warning(f"Error reading backup {backup_file}: {e}")
        
        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)
    
    def verify_backup(self, backup_path: Path) -> Dict:
        """Verify backup integrity."""
        results = {
            "valid": False,
            "errors": []
        }
        
        try:
            # Create temporary directory
            temp_dir = self.backup_dir / "temp_verify"
            temp_dir.mkdir()
            
            try:
                # Extract archive
                with tarfile.open(backup_path, "r:gz") as tar:
                    tar.extractall(temp_dir)
                
                # Find backup directory
                backup_dir = next(temp_dir.iterdir())
                
                # Load manifest
                manifest_path = backup_dir / "manifest.json"
                with open(manifest_path) as f:
                    manifest = json.load(f)
                
                # Verify file presence and hashes
                for rel_path, stored_hash in manifest["hashes"].items():
                    if rel_path == "database":
                        file_path = backup_dir / "database" / "jarvis.db"
                    else:
                        file_path = backup_dir / rel_path
                    
                    if not file_path.exists():
                        results["errors"].append(f"Missing file: {rel_path}")
                        continue
                    
                    current_hash = self._calculate_hash(file_path)
                    if current_hash != stored_hash:
                        results["errors"].append(
                            f"Hash mismatch for {rel_path}"
                        )
                
                # Verify database integrity if present
                if manifest["contents"]["database"]:
                    db_path = backup_dir / "database" / "jarvis.db"
                    if db_path.exists():
                        async with aiosqlite.connect(db_path) as db:
                            async with db.execute("PRAGMA integrity_check") as cursor:
                                result = await cursor.fetchone()
                                if result[0] != "ok":
                                    results["errors"].append(
                                        "Database integrity check failed"
                                    )
                
                results["valid"] = len(results["errors"]) == 0
                
            finally:
                # Clean up
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            
        except Exception as e:
            results["errors"].append(f"Error verifying backup: {e}")
        
        return results

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Jarvis AI Assistant Backup Manager"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Create backup command
    create_parser = subparsers.add_parser("create", help="Create backup")
    create_parser.add_argument(
        "--no-db",
        action="store_true",
        help="Exclude database from backup"
    )
    
    # Restore backup command
    restore_parser = subparsers.add_parser("restore", help="Restore from backup")
    restore_parser.add_argument(
        "backup_file",
        type=Path,
        help="Backup file to restore from"
    )
    restore_parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip database restoration"
    )
    
    # List backups command
    list_parser = subparsers.add_parser("list", help="List available backups")
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    
    # Verify backup command
    verify_parser = subparsers.add_parser("verify", help="Verify backup integrity")
    verify_parser.add_argument(
        "backup_file",
        type=Path,
        help="Backup file to verify"
    )
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    manager = BackupManager()
    
    try:
        if args.command == "create":
            backup_file = manager.create_backup(not args.no_db)
            if not backup_file:
                sys.exit(1)
        
        elif args.command == "restore":
            if not args.backup_file.exists():
                logger.error(f"Backup file not found: {args.backup_file}")
                sys.exit(1)
            
            success = manager.restore_backup(args.backup_file, not args.no_db)
            sys.exit(0 if success else 1)
        
        elif args.command == "list":
            backups = manager.list_backups()
            
            if args.json:
                print(json.dumps(backups, indent=2))
            else:
                if not backups:
                    print("No backups found")
                else:
                    print("\nAvailable Backups:")
                    for backup in backups:
                        print(f"\nFile: {backup['file']}")
                        print(f"Created: {backup['timestamp']}")
                        print(f"Version: {backup['version']}")
                        print(f"Size: {backup['size'] / 1024 / 1024:.2f} MB")
                        print("Contents:")
                        print(f"- Data files: {len(backup['contents']['data'])}")
                        print(f"- Config files: {len(backup['contents']['config'])}")
                        print(f"- Database: {'Yes' if backup['contents']['database'] else 'No'}")
        
        elif args.command == "verify":
            if not args.backup_file.exists():
                logger.error(f"Backup file not found: {args.backup_file}")
                sys.exit(1)
            
            results = manager.verify_backup(args.backup_file)
            
            if results["valid"]:
                logger.info("Backup verification successful")
                sys.exit(0)
            else:
                logger.error("Backup verification failed:")
                for error in results["errors"]:
                    logger.error(f"- {error}")
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
