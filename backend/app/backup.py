"""Create, verify, and restore SQLite backups using SQLite's online backup API."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time


BACKUP_PREFIX = "projectpulse-"
BACKUP_SUFFIX = ".sqlite3"


def _connect(path: Path, *, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    return sqlite3.connect(path)


def inspect_database(path: str | Path) -> dict[str, int]:
    """Check SQLite integrity, foreign keys, and count rows by table."""
    database = Path(path).expanduser().resolve()
    if not database.is_file():
        raise FileNotFoundError(f"Database file does not exist: {database}")

    with closing(_connect(database, readonly=True)) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise RuntimeError(f"SQLite foreign key check found {len(foreign_key_errors)} error(s).")
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            table: connection.execute(f' SELECT count(*) FROM "{table}"').fetchone()[0]  # nosec B608 — identifiers come from the verified SQLite table list.
            for table in tables
        }


def _copy_database(source_path: Path, destination_path: Path) -> None:
    if source_path.resolve() == destination_path.resolve():
        raise ValueError("Source and destination database paths must be different.")
    if not source_path.is_file():
        raise FileNotFoundError(f"Source database does not exist: {source_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect(source_path, readonly=True)) as source:
        with closing(sqlite3.connect(destination_path)) as destination:
            source.backup(destination, pages=256, sleep=0.1)
            destination.commit()


def create_backup(database_path: str | Path, backup_dir: str | Path, retention_days: int = 30) -> Path:
    """Take and validate a consistent online backup, then prune expired copies."""
    if retention_days < 1:
        raise ValueError("Backup retention must be at least one day.")
    source = Path(database_path).expanduser().resolve()
    target_dir = Path(backup_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = target_dir / f"{BACKUP_PREFIX}{timestamp}{BACKUP_SUFFIX}"

    descriptor, temporary_name = tempfile.mkstemp(prefix=".projectpulse-", suffix=".tmp", dir=target_dir)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        _copy_database(source, temporary)
        counts = inspect_database(temporary)
        os.replace(temporary, target)
        print(f"SQLite backup created: {target} ({sum(counts.values())} rows across {len(counts)} tables)", flush=True)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    for old_backup in target_dir.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"):
        try:
            modified = datetime.fromtimestamp(old_backup.stat().st_mtime, timezone.utc)
        except FileNotFoundError:
            continue
        if modified < cutoff:
            old_backup.unlink(missing_ok=True)
    return target


def restore_to_backup(backup_path: str | Path, destination_path: str | Path, *, replace: bool = False) -> dict[str, int]:
    """Restore to a new file, or atomically replace a stopped app's database."""
    source = Path(backup_path).expanduser().resolve()
    destination = Path(destination_path).expanduser().resolve()
    if source == destination:
        raise ValueError("Backup and restore destination must be different files.")
    if destination.exists() and not replace:
        raise FileExistsError(f"Restore destination already exists: {destination}; pass --replace to overwrite it.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".restore", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        _copy_database(source, temporary)
        restored_counts = inspect_database(temporary)
        source_counts = inspect_database(source)
        if restored_counts != source_counts:
            raise RuntimeError("Restore verification failed: table row counts differ from the backup.")
        os.replace(temporary, destination)
        print(f"Restore verified: {destination} ({sum(restored_counts.values())} rows across {len(restored_counts)} tables)", flush=True)
        return restored_counts
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def backup_loop(database_path: str | Path, backup_dir: str | Path, interval_seconds: int, retention_days: int) -> None:
    if interval_seconds < 60:
        raise ValueError("Backup interval must be at least 60 seconds.")
    while True:
        create_backup(database_path, backup_dir, retention_days)
        time.sleep(interval_seconds)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backup", help="create one validated backup")
    commands.add_parser("backup-loop", help="create a backup now and repeat on an interval")
    verify = commands.add_parser("verify", help="check a database backup")
    verify.add_argument("path")
    restore_check = commands.add_parser("restore-check", help="restore a backup to a new file and verify it")
    restore_check.add_argument("backup")
    restore_check.add_argument("destination")
    restore = commands.add_parser("restore-to", help="restore backup to a database path")
    restore.add_argument("backup")
    restore.add_argument("destination")
    restore.add_argument("--replace", action="store_true", help="atomically replace an existing database; stop the app first")
    args = parser.parse_args(argv)

    database = Path(os.environ.get("PROJECTPULSE_DATABASE", "/data/projectpulse.sqlite3"))
    backup_dir = Path(os.environ.get("PROJECTPULSE_BACKUP_DIR", "/backups"))
    interval = int(os.environ.get("PROJECTPULSE_BACKUP_INTERVAL_SECONDS", "86400"))
    retention = int(os.environ.get("PROJECTPULSE_BACKUP_RETENTION_DAYS", "30"))

    if args.command == "backup":
        create_backup(database, backup_dir, retention)
    elif args.command == "backup-loop":
        backup_loop(database, backup_dir, interval, retention)
    elif args.command == "verify":
        counts = inspect_database(args.path)
        print(f"Backup is valid: {args.path} ({sum(counts.values())} rows across {len(counts)} tables)")
    elif args.command == "restore-check":
        counts = restore_to_backup(args.backup, args.destination)
        Path(args.destination).unlink()
        print(f"Isolated restore drill passed for {args.backup}: {sum(counts.values())} rows verified")
    else:
        restore_to_backup(args.backup, args.destination, replace=args.replace)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, FileExistsError, OSError, RuntimeError, ValueError) as error:
        print(f"Backup operation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
