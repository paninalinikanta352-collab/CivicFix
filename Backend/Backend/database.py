from contextlib import contextmanager
from pathlib import Path
import sqlite3

DATABASE_DIR = Path(__file__).resolve().parent.parent / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = DATABASE_DIR / "civicfix.db"

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user','worker','admin')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other' CHECK(category IN ('roads','water','electricity','cleanliness','other')),
    latitude REAL,
    longitude REAL,
    address TEXT,
    photo_url TEXT,
    ai_analysis TEXT,
    risk_percentage INTEGER NOT NULL DEFAULT 0 CHECK(risk_percentage BETWEEN 0 AND 100),
    status TEXT NOT NULL DEFAULT 'reported' CHECK(status IN ('reported','assigned','in_progress','resolved','rejected')),
    reporter_id INTEGER NOT NULL REFERENCES users(id),
    assigned_worker_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS issue_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    actor_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status);
CREATE INDEX IF NOT EXISTS idx_issues_created ON issues(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_issues_assignee ON issues(assigned_worker_id);
"""

@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        # Live migration for databases created before ai_analysis existed.
        cols = {row[1] for row in conn.execute('PRAGMA table_info(issues)').fetchall()}
        if 'ai_analysis' not in cols:
            conn.execute('ALTER TABLE issues ADD COLUMN ai_analysis TEXT')
