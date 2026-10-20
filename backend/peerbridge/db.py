"""SQLite storage. Connections are short lived and writes commit atomically."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
 id TEXT PRIMARY KEY, alias TEXT NOT NULL COLLATE NOCASE UNIQUE,
 avatar_id TEXT NOT NULL, grade_band TEXT NOT NULL,
 strengths TEXT NOT NULL, needs TEXT NOT NULL, available_slots TEXT NOT NULL,
 capacity INTEGER NOT NULL CHECK(capacity BETWEEN 0 AND 5),
 support_preferences TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS missions (
 id TEXT PRIMARY KEY, requester_id TEXT NOT NULL REFERENCES profiles(id),
 text TEXT NOT NULL, normalized_text TEXT NOT NULL, topic TEXT,
 route TEXT NOT NULL, status TEXT NOT NULL, analysis TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_pending_mission
 ON missions(requester_id, normalized_text) WHERE status IN ('open','matched');
CREATE TABLE IF NOT EXISTS matches (
 id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES missions(id),
 mentor_id TEXT NOT NULL REFERENCES profiles(id), requester_id TEXT NOT NULL REFERENCES profiles(id),
 topic TEXT NOT NULL, component_scores TEXT NOT NULL, score REAL NOT NULL,
 explanation TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_active_match ON matches(mission_id) WHERE status='active';
CREATE INDEX IF NOT EXISTS mentor_active ON matches(mentor_id,status);
CREATE TABLE IF NOT EXISTS reports (
 id TEXT PRIMARY KEY, reporter_id TEXT NOT NULL REFERENCES profiles(id),
 target_type TEXT NOT NULL, target_id TEXT NOT NULL, reason TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blocks (
 id TEXT PRIMARY KEY, blocker_id TEXT NOT NULL REFERENCES profiles(id),
 blocked_id TEXT NOT NULL REFERENCES profiles(id), created_at TEXT NOT NULL,
 UNIQUE(blocker_id,blocked_id), CHECK(blocker_id != blocked_id)
);
CREATE TABLE IF NOT EXISTS resources (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL,
 topics TEXT NOT NULL, access_notes TEXT NOT NULL, verified_at TEXT
);
"""


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def database_path():
    return Path(os.environ.get("PEERBRIDGE_DB", str(ROOT / "data" / "peerbridge.sqlite3")))


@contextmanager
def connect():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_tables(conn):
    conn.executescript(SCHEMA)


def init_database():
    from .seed import seed_database
    with connect() as conn:
        create_tables(conn)
        if not conn.execute("SELECT 1 FROM profiles LIMIT 1").fetchone():
            seed_database(conn)


def reset_database():
    from .seed import seed_database
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for table in ("reports", "blocks", "matches", "missions", "resources", "profiles"):
            conn.execute(f"DELETE FROM {table}")
        seed_database(conn)


def decode(value, default=None):
    if value is None:
        return default
    return json.loads(value) if isinstance(value, str) else value


def profile_dict(conn, row):
    result = dict(row)
    for field in ("strengths", "needs", "available_slots", "support_preferences"):
        result[field] = decode(result[field], [])
    result["active_matches"] = conn.execute(
        "SELECT COUNT(*) FROM matches WHERE mentor_id=? AND status='active'", (result["id"],)
    ).fetchone()[0]
    result["remaining_capacity"] = max(0, result["capacity"] - result["active_matches"])
    result.pop("created_at", None)
    return result


def mission_dict(conn, row):
    result = dict(row)
    result["analysis"] = decode(result["analysis"], {})
    result.pop("normalized_text", None)
    profile = conn.execute("SELECT alias FROM profiles WHERE id=?", (result["requester_id"],)).fetchone()
    result["requester_alias"] = profile["alias"] if profile else "Unavailable hero"
    return result


def match_dict(conn, row):
    result = dict(row)
    result["component_scores"] = decode(result["component_scores"], {})
    for field in ("mentor", "requester"):
        p = conn.execute("SELECT alias FROM profiles WHERE id=?", (result[f"{field}_id"],)).fetchone()
        result[f"{field}_alias"] = p["alias"] if p else "Unavailable hero"
    return result


def resource_dict(row):
    result = dict(row)
    result["topics"] = decode(result["topics"], [])
    return result
