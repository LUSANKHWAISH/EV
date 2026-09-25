# E.V. TASK 012B.1 — WINDOWS SQLITE CONNECTION-CLOSE FIX

## Root cause

The Windows test traceback shows TemporaryDirectory cleanup failing with:

WinError 32: history.sqlite3 is being used by another process.

The store used:

    with self._connect() as connection:

Python's sqlite3.Connection context manager manages transaction commit/rollback,
but leaving the context does NOT close the connection.

On Linux an open SQLite file can still be unlinked, so the isolated validation
did not expose the defect. Windows keeps the file locked until the connection is
closed.

## Exact repair

1. Add:

    from contextlib import closing

2. Replace each of the 8 connection contexts:

    with self._connect() as connection:

with:

    with closing(self._connect()) as connection:

No schema, model, query, persistence, or public API behavior is changed.

## Scope

Changed:
- core/history.py only

Unchanged:
- core/models.py
- tests/test_history.py
- .gitignore
- EVAgent
- verifier
- backup
- risk
- events
- GUI/QML
