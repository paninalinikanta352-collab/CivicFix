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
    email_verified INTEGER NOT NULL DEFAULT 0 CHECK(email_verified IN (0,1)),
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
CREATE TABLE IF NOT EXISTS email_otps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL COLLATE NOCASE,
    purpose TEXT NOT NULL CHECK(purpose IN ('password_reset','email_verify')),
    code_hash TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    expires_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_otp_email_purpose ON email_otps(email, purpose);
CREATE INDEX IF NOT EXISTS idx_otp_expires ON email_otps(expires_at);
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
        # Live migrations for databases created before newer columns/tables.
        cols = {row[1] for row in conn.execute('PRAGMA table_info(issues)').fetchall()}
        if 'ai_analysis' not in cols:
            conn.execute('ALTER TABLE issues ADD COLUMN ai_analysis TEXT')
        if 'category_source' not in cols:
            conn.execute("ALTER TABLE issues ADD COLUMN category_source TEXT DEFAULT 'user'")
        ucols = {row[1] for row in conn.execute('PRAGMA table_info(users)').fetchall()}
        if 'email_verified' not in ucols:
            conn.execute('ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0')
        # Old single-purpose OTP table -> purpose-aware email_otps (rows survive).
        legacy = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='password_reset_otps'").fetchone()
        if legacy is not None:
            old_rows = conn.execute('SELECT id, email, code_hash, attempts, created_at, expires_at FROM password_reset_otps').fetchall()
            for row in old_rows:
                conn.execute(
                    '''INSERT INTO email_otps(id, email, purpose, code_hash, attempts, created_at, expires_at)
                       VALUES(?, ?, 'password_reset', ?, ?, ?, ?)
                       ON CONFLICT(email, purpose) DO UPDATE SET code_hash=excluded.code_hash, attempts=excluded.attempts,
                             created_at=excluded.created_at, expires_at=excluded.expires_at''',
                    (row['id'], row['email'], row['code_hash'], row['attempts'], row['created_at'], row['expires_at']),
                )
            conn.execute('DROP TABLE password_reset_otps')
            conn.execute('DROP INDEX IF EXISTS idx_otp_expires')  # recreate below on the new table
            conn.execute('CREATE INDEX IF NOT EXISTS idx_otp_expires ON email_otps(expires_at)')
