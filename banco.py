"""Utilitários de conexão/segurança SQLite do RH Fácil."""
import sqlite3

def configure_connection(con):
    con.row_factory=sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.DatabaseError:
        pass
    return con

def checkpoint(con):
    try:
        con.execute("PRAGMA wal_checkpoint(FULL)")
    except sqlite3.DatabaseError:
        pass
