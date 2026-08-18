import sqlite3
from pathlib import Path
from flask import current_app, g

_SCHEMA = Path(__file__).parent.parent / 'database' / 'schema.sql'


def get_db() -> sqlite3.Connection:
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def init_db(db_path: str = None) -> None:
    path = db_path or current_app.config['DATABASE']
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA.read_text(encoding='utf-8'))
    conn.commit()
    conn.close()
