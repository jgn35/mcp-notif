"""SQLite token store adapter (AD-13).

Single-row (`id=1`) table holding the FCM device token. Every connection sets
WAL journal mode and a 5s busy_timeout so concurrent read/write (enrollment
vs. notify) does not raise SQLITE_BUSY. The table is created at startup before
either inbound adapter serves.
"""

from __future__ import annotations

import asyncio
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime

from ...ports import NoDeviceEnrolledError, StoreUnavailableError

_CREATE_SQL = (
    "CREATE TABLE IF NOT EXISTS device_token ("
    "id INTEGER PRIMARY KEY DEFAULT 1, "
    "token TEXT NOT NULL, "
    "enrolled_at TEXT NOT NULL"
    ")"
)
_READ_SQL = "SELECT token FROM device_token WHERE id = 1"
_WRITE_SQL = (
    "INSERT OR REPLACE INTO device_token (id, token, enrolled_at) "
    "VALUES (1, ?, ?)"
)


class SqliteTokenStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- public async API (TokenStore protocol) ---

    async def init(self) -> None:
        await asyncio.to_thread(self._init)

    async def read(self) -> str:
        return await asyncio.to_thread(self._read)

    async def write(self, token: str) -> None:
        await asyncio.to_thread(self._write, token)

    # --- blocking impls, run in a worker thread ---

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_SQL)

    def _read(self) -> str:
        try:
            with self._connect() as conn:
                row = conn.execute(_READ_SQL).fetchone()
        except sqlite3.DatabaseError as exc:
            raise StoreUnavailableError(f"token store is unavailable: {exc}") from exc
        if row is None:
            raise NoDeviceEnrolledError("no device token enrolled")
        return str(row[0])

    def _write(self, token: str) -> None:
        enrolled_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with self._connect() as conn:
                conn.execute(_WRITE_SQL, (token, enrolled_at))
        except sqlite3.DatabaseError as exc:
            raise StoreUnavailableError(f"token store is unavailable: {exc}") from exc
