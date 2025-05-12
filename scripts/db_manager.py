#!/usr/bin/env python3
"""
Database management tools for Jarvis AI Assistant.
This script provides utilities for managing database operations,
migrations, backups, and maintenance tasks.
"""

import os
import sys
import argparse
import sqlite3
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
import shutil
import asyncio
import aiosqlite
from tabulate import tabulate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
DB_DIR = PROJECT_ROOT / "data"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
BACKUP_DIR = PROJECT_ROOT / "backups"
SCHEMA_FILE = PROJECT_ROOT / "schema.sql"

class DatabaseManager:
    """Database management utility class."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize database manager."""
        self.db_dir = DB_DIR
        self.migrations_dir = MIGRATIONS_DIR
        self.backup_dir = BACKUP_DIR
        
        # Create necessary directories
        self.db_dir.mkdir(exist_ok=True)
        self.migrations_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)
        
        # Load configuration
        self.config = self._load_config(config_path)
        self.db_path = self.db_dir / self.config["database"]["sqlite"]["path"]
    
    def _load_config(self, config_path: Optional[Path]) -> Dict:
        """Load configuration from file."""
        if config_path is None:
            config_path = PROJECT_ROOT / "config" / "config.yaml"
        
        try:
            with open(config_path) as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {
                "database": {
                    "type": "sqlite",
                    "sqlite": {
                        "path": "jarvis.db"
                    }
                }
            }
    
    async def initialize_db(self) -> bool:
        """Initialize database with schema."""
        try:
            if not SCHEMA_FILE.exists():
                logger.error(f"Schema file not found: {SCHEMA_FILE}")
                return False
            
            schema = SCHEMA_FILE.read_text()
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.executescript(schema)
                await db.commit()
            
            logger.info("Database initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            return False
    
    async def create_migration(self, name: str) -> Path:
        """Create a new migration file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        migration_file = self.migrations_dir / f"{timestamp}_{name}.sql"
        
        template = """-- Migration: {name}
-- Created at: {timestamp}

-- Write your UP migration here
BEGIN;

-- Add your SQL statements here

COMMIT;

-- Write your DOWN migration here
BEGIN;

-- Add your rollback SQL statements here

COMMIT;
"""
        
        migration_file.write_text(template.format(
            name=name,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        
        logger.info(f"Created migration file: {migration_file}")
        return migration_file
    
    async def apply_migrations(self, target: Optional[str] = None) -> bool:
        """Apply pending migrations."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Create migrations table if it doesn't exist
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS migrations (
                        id TEXT PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await db.commit()
                
                # Get applied migrations
                async with db.execute("SELECT id FROM migrations") as cursor:
                    applied = {row[0] async for row in cursor}
                
                # Get all migration files
                migrations = sorted(
                    self.migrations_dir.glob("*.sql"),
                    key=lambda p: p.stem
                )
                
                for migration in migrations:
                    migration_id = migration.stem
                    
                    if migration_id in applied:
                        continue
                    
                    if target and migration_id > target:
                        break
                    
                    logger.info(f"Applying migration: {migration_id}")
                    
                    # Read and split migration content
                    content = migration.read_text()
                    up_sql = content.split("-- Write your DOWN")[0].strip()
                    
                    # Apply migration
                    await db.executescript(up_sql)
                    await db.execute(
                        "INSERT INTO migrations (id) VALUES (?)",
                        (migration_id,)
                    )
                    await db.commit()
            
            logger.info("Migrations applied successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error applying migrations: {e}")
            return False
    
    async def rollback_migration(self, migration_id: str) -> bool:
        """Rollback a specific migration."""
        try:
            migration_file = self.migrations_dir / f"{migration_id}.sql"
            if not migration_file.exists():
                logger.error(f"Migration file not found: {migration_file}")
                return False
            
            # Read and split migration content
            content = migration_file.read_text()
            down_sql = content.split("-- Write your DOWN")[1].strip()
            
            async with aiosqlite.connect(self.db_path) as db:
                # Apply rollback
                await db.executescript(down_sql)
                await db.execute(
                    "DELETE FROM migrations WHERE id = ?",
                    (migration_id,)
                )
                await db.commit()
            
            logger.info(f"Rolled back migration: {migration_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error rolling back migration: {e}")
            return False
    
    async def create_backup(self) -> Optional[Path]:
        """Create a database backup."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"backup_{timestamp}.db"
            
            # Create backup
            shutil.copy2(self.db_path, backup_file)
            
            # Verify backup
            async with aiosqlite.connect(backup_file) as db:
                async with db.execute("PRAGMA integrity_check") as cursor:
                    result = await cursor.fetchone()
                    if result[0] != "ok":
                        raise Exception("Backup integrity check failed")
            
            logger.info(f"Created backup: {backup_file}")
            return backup_file
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return None
    
    async def restore_backup(self, backup_file: Path) -> bool:
        """Restore database from backup."""
        try:
            if not backup_file.exists():
                logger.error(f"Backup file not found: {backup_file}")
                return False
            
            # Verify backup
            async with aiosqlite.connect(backup_file) as db:
                async with db.execute("PRAGMA integrity_check") as cursor:
                    result = await cursor.fetchone()
                    if result[0] != "ok":
                        raise Exception("Backup integrity check failed")
            
            # Create backup of current database
            await self.create_backup()
            
            # Restore backup
            shutil.copy2(backup_file, self.db_path)
            
            logger.info(f"Restored from backup: {backup_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            return False
    
    async def show_tables(self) -> List[Dict]:
        """Show database tables and their information."""
        try:
            tables = []
            async with aiosqlite.connect(self.db_path) as db:
                # Get table list
                async with db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ) as cursor:
                    async for row in cursor:
                        table_name = row[0]
                        
                        # Get column information
                        async with db.execute(f"PRAGMA table_info({table_name})") as info_cursor:
                            columns = [
                                {
                                    "name": col[1],
                                    "type": col[2],
                                    "notnull": bool(col[3]),
                                    "pk": bool(col[5])
                                }
                                async for col in info_cursor
                            ]
                        
                        # Get row count
                        async with db.execute(f"SELECT COUNT(*) FROM {table_name}") as count_cursor:
                            count = (await count_cursor.fetchone())[0]
                        
                        tables.append({
                            "name": table_name,
                            "columns": columns,
                            "row_count": count
                        })
            
            return tables
            
        except Exception as e:
            logger.error(f"Error getting table information: {e}")
            return []
    
    async def vacuum_db(self) -> bool:
        """Vacuum database to optimize storage."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("VACUUM")
                await db.commit()
            
            logger.info("Database vacuumed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error vacuuming database: {e}")
            return False

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Jarvis AI Assistant Database Manager"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Initialize database command
    subparsers.add_parser("init", help="Initialize database")
    
    # Create migration command
    create_parser = subparsers.add_parser("create-migration", help="Create migration")
    create_parser.add_argument("name", help="Migration name")
    
    # Apply migrations command
    apply_parser = subparsers.add_parser("migrate", help="Apply migrations")
    apply_parser.add_argument(
        "--target",
        help="Target migration ID (default: latest)"
    )
    
    # Rollback migration command
    rollback_parser = subparsers.add_parser("rollback", help="Rollback migration")
    rollback_parser.add_argument("migration_id", help="Migration ID to rollback")
    
    # Backup commands
    subparsers.add_parser("backup", help="Create database backup")
    
    restore_parser = subparsers.add_parser("restore", help="Restore from backup")
    restore_parser.add_argument("backup_file", help="Backup file to restore from")
    
    # Show tables command
    subparsers.add_parser("show-tables", help="Show database tables")
    
    # Vacuum command
    subparsers.add_parser("vacuum", help="Vacuum database")
    
    return parser.parse_args()

async def main():
    """Main function."""
    args = parse_args()
    manager = DatabaseManager()
    
    if args.command == "init":
        success = await manager.initialize_db()
        sys.exit(0 if success else 1)
    
    elif args.command == "create-migration":
        migration_file = await manager.create_migration(args.name)
        logger.info(f"Edit the migration file: {migration_file}")
        sys.exit(0)
    
    elif args.command == "migrate":
        success = await manager.apply_migrations(args.target)
        sys.exit(0 if success else 1)
    
    elif args.command == "rollback":
        success = await manager.rollback_migration(args.migration_id)
        sys.exit(0 if success else 1)
    
    elif args.command == "backup":
        backup_file = await manager.create_backup()
        sys.exit(0 if backup_file else 1)
    
    elif args.command == "restore":
        success = await manager.restore_backup(Path(args.backup_file))
        sys.exit(0 if success else 1)
    
    elif args.command == "show-tables":
        tables = await manager.show_tables()
        
        for table in tables:
            print(f"\nTable: {table['name']}")
            print(f"Row count: {table['row_count']}")
            print("\nColumns:")
            
            headers = ["Name", "Type", "Not Null", "Primary Key"]
            rows = [
                [
                    col["name"],
                    col["type"],
                    "Yes" if col["notnull"] else "No",
                    "Yes" if col["pk"] else "No"
                ]
                for col in table["columns"]
            ]
            
            print(tabulate(rows, headers=headers, tablefmt="grid"))
        
        sys.exit(0)
    
    elif args.command == "vacuum":
        success = await manager.vacuum_db()
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
