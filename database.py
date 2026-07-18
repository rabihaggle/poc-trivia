import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "trivia.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS correct_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL UNIQUE REFERENCES questions(id) ON DELETE CASCADE,
            text TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS wrong_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            text TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()
