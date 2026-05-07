"""
SQLite database layer for storing scraped job listings.
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

from job_search.config import DB_PATH

logger = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,   -- board:company:job_id
    board       TEXT NOT NULL,      -- GREENHOUSE, LEVER, ASHBY, WORKABLE
    company     TEXT,
    title       TEXT,
    url         TEXT UNIQUE NOT NULL,
    location    TEXT,
    region      TEXT,               -- europe, asia_pacific, worldwide, etc.
    skills      TEXT,               -- JSON array
    description TEXT,
    posted_at   TEXT,               -- raw "X hours ago" string from Google
    scraped_at  TEXT NOT NULL,
    category    TEXT,               -- DEVOPS, DATA, AI_ML, BACKEND
    raw_html    TEXT                -- stored for re-parsing if needed
);

CREATE INDEX IF NOT EXISTS idx_jobs_board    ON jobs(board);
CREATE INDEX IF NOT EXISTS idx_jobs_region   ON jobs(region);
CREATE INDEX IF NOT EXISTS idx_jobs_category ON jobs(category);
CREATE INDEX IF NOT EXISTS idx_jobs_scraped  ON jobs(scraped_at);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
    logger.info("Database initialised at %s", DB_PATH)


def job_exists(url: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM jobs WHERE url = ?", (url,)).fetchone()
        return row is not None


def save_job(job: dict) -> bool:
    """
    Insert a job. Returns True if inserted, False if duplicate.
    """
    if job_exists(job["url"]):
        return False

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO jobs
                (id, board, company, title, url, location, region,
                 skills, description, posted_at, scraped_at, category, raw_html)
            VALUES
                (:id, :board, :company, :title, :url, :location, :region,
                 :skills, :description, :posted_at, :scraped_at, :category, :raw_html)
            """,
            {
                **job,
                "skills": json.dumps(job.get("skills", [])),
                "scraped_at": datetime.utcnow().isoformat(),
            },
        )
    return True


def get_jobs(
    board: Optional[str] = None,
    region: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    clauses = []
    params = []
    if board:
        clauses.append("board = ?")
        params.append(board)
    if region:
        clauses.append("region = ?")
        params.append(region)
    if category:
        clauses.append("category = ?")
        params.append(category)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM jobs {where} ORDER BY scraped_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        d["skills"] = json.loads(d["skills"] or "[]")
        result.append(d)
    return result


def stats() -> dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        by_board = {
            r["board"]: r["cnt"]
            for r in conn.execute(
                "SELECT board, COUNT(*) as cnt FROM jobs GROUP BY board"
            ).fetchall()
        }
        by_region = {
            r["region"]: r["cnt"]
            for r in conn.execute(
                "SELECT region, COUNT(*) as cnt FROM jobs GROUP BY region"
            ).fetchall()
        }
        by_category = {
            r["category"]: r["cnt"]
            for r in conn.execute(
                "SELECT category, COUNT(*) as cnt FROM jobs GROUP BY category"
            ).fetchall()
        }
    return {
        "total": total,
        "by_board": by_board,
        "by_region": by_region,
        "by_category": by_category,
    }
