import sqlite3

from app.backup import create_backup, inspect_database, restore_to_backup


def test_backup_restore_drill_preserves_integrity_and_rows(tmp_path):
    source = tmp_path / "source.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.executescript(
            "CREATE TABLE organizations(id INTEGER PRIMARY KEY, name TEXT);"
            "INSERT INTO organizations(name) VALUES('Audit workspace');"
        )

    backup = create_backup(source, tmp_path / "backups")
    restored = tmp_path / "restore-drill.sqlite3"
    counts = restore_to_backup(backup, restored)

    assert counts == inspect_database(source)
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT name FROM organizations").fetchone()[0] == "Audit workspace"
