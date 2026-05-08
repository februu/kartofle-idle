import sqlite3
import os

conn = sqlite3.connect(os.getenv("SQLITE_PATH", ":memory:"))
cursor = conn.cursor()

cursor.executescript(
    """
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id        INTEGER NOT NULL,
        amount         REAL    NOT NULL,
        timestamp      TEXT    DEFAULT (datetime('now')),
        source         TEXT    NOT NULL,  -- 'job', 'passive', 'game'
        source_id      INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS jobs (
        job_id              INTEGER PRIMARY KEY AUTOINCREMENT,
        title               TEXT    NOT NULL,
        description         TEXT,
        amount              REAL    NOT NULL,
        duration_seconds    INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS job_log (
        log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER NOT NULL,
        job_id          INTEGER NOT NULL,
        end_time        TEXT    NOT NULL,
        collected       INTEGER DEFAULT 0,
        FOREIGN KEY (job_id) REFERENCES jobs(job_id)
    );

    CREATE TABLE IF NOT EXISTS passive_income (
        income_id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id             INTEGER NOT NULL,
        title               TEXT    NOT NULL,
        description         TEXT,
        amount_per_second   REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS games (
        game_id         INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id      INTEGER NOT NULL,
        title           TEXT    NOT NULL,
        description     TEXT,
        resolved        INTEGER DEFAULT 0  -- 0 = open, 1 = resolved
    );

    CREATE TABLE IF NOT EXISTS options (
        option_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        description     TEXT    NOT NULL,
        game_id         INTEGER NOT NULL,
        FOREIGN KEY (game_id) REFERENCES games(game_id)
    );

    CREATE TABLE IF NOT EXISTS bets (
        bet_id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         INTEGER NOT NULL,
        game_id         INTEGER NOT NULL,
        amount          REAL    NOT NULL,
        option_id       INTEGER NOT NULL,
        FOREIGN KEY (game_id)    REFERENCES games(game_id),
        FOREIGN KEY (option_id)  REFERENCES options(option_id)
    );
    """
)


def get_user_balance(user_id):
    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = ?",
        (user_id,),
    )
    return cursor.fetchone()[0]
