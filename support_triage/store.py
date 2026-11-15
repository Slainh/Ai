"""SQLite persistence for repeatable and idempotent demo runs."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .core import Decision, Ticket


@contextmanager
def database(path: str):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
            category TEXT NOT NULL, priority TEXT NOT NULL, summary TEXT NOT NULL,
            requires_review INTEGER NOT NULL, reply_draft TEXT NOT NULL,
            engine TEXT NOT NULL, reviewed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit()
        yield conn
    finally:
        conn.close()


def is_unchanged(conn, ticket: Ticket) -> bool:
    record = conn.execute("SELECT fingerprint FROM tickets WHERE ticket_id=?", (ticket.ticket_id,)).fetchone()
    return bool(record and record[0] == ticket.fingerprint())


def save(conn, ticket: Ticket, decision: Decision):
    conn.execute("""INSERT INTO tickets
        (ticket_id,fingerprint,category,priority,summary,requires_review,reply_draft,engine)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(ticket_id) DO UPDATE SET
        fingerprint=excluded.fingerprint,category=excluded.category,
        priority=excluded.priority,summary=excluded.summary,
        requires_review=excluded.requires_review,reply_draft=excluded.reply_draft,
        engine=excluded.engine,reviewed=0,updated_at=CURRENT_TIMESTAMP""",
        (ticket.ticket_id, ticket.fingerprint(), decision.category, decision.priority,
         decision.summary, int(decision.requires_review), decision.reply_draft, decision.engine))
    conn.commit()


def mark_reviewed(conn, ticket_id: str) -> bool:
    cur = conn.execute("UPDATE tickets SET reviewed=1 WHERE ticket_id=?", (ticket_id,))
    conn.commit()
    return cur.rowcount > 0


def summary(conn) -> dict:
    count = conn.execute("SELECT count(*) FROM tickets").fetchone()[0]
    pending = conn.execute("SELECT count(*) FROM tickets WHERE reviewed=0").fetchone()[0]
    categories = dict(conn.execute("SELECT category,count(*) FROM tickets GROUP BY category").fetchall())
    return {"total":count,"pending_review":pending,"by_category":categories}
