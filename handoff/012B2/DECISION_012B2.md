# E.V. TASK 012B.2 — WINDOWS TEST SQLITE CLOSE FIX

## Root cause

After the production 012B.1 repair, 14 of 15 history tests pass on Windows.

The remaining test `test_database_and_schema_are_created` opens SQLite directly
with:

    with sqlite3.connect(self.db_path) as connection:

As with the production issue, sqlite3.Connection's context manager controls the
transaction but does not close the connection.

Windows therefore keeps history.sqlite3 locked during TemporaryDirectory
cleanup.

## Exact repair

Add:

    from contextlib import closing

Change only the test's direct SQLite context to:

    with closing(sqlite3.connect(self.db_path)) as connection:

No production code changes.
No schema changes.
No test expectations change.
