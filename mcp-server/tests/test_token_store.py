"""SQLite token store (AD-13): init, read, write, overwrite, corrupt-store handling."""

from __future__ import annotations

import sqlite3

import pytest

from mcp_notif.adapters.outbound.token_store import SqliteTokenStore
from mcp_notif.ports import NoDeviceEnrolledError, StoreUnavailableError


async def test_read_empty_raises_no_device_enrolled(store):
    await store.init()
    with pytest.raises(NoDeviceEnrolledError):
        await store.read()


async def test_write_then_read_roundtrip(store):
    await store.init()
    await store.write("token-A")
    assert await store.read() == "token-A"


async def test_write_overwrites_last_enrollment_wins(store):
    await store.init()
    await store.write("token-A")
    await store.write("token-B")
    assert await store.read() == "token-B"
    # Single row enforced.
    with sqlite3.connect(store._db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM device_token WHERE id = 1").fetchone()[0]
    assert count == 1


async def test_init_creates_table_idempotent(store):
    await store.init()
    await store.init()  # second init must not error
    await store.write("x")
    assert await store.read() == "x"


async def test_wal_and_busy_timeout_pragmas_set(store):
    await store.init()
    with sqlite3.connect(store._db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    # WAL persists in the database header.
    assert mode.lower() == "wal"
    assert busy == 5000


async def test_corrupt_store_raises_store_unavailable(tmp_path):
    db_path = tmp_path / "notadb.db"
    db_path.write_bytes(b"this is not a sqlite database file")
    store = SqliteTokenStore(str(db_path))
    with pytest.raises(StoreUnavailableError):
        await store.read()
