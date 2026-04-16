"""SQLite program database and thin DAO."""
from __future__ import annotations
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation INTEGER NOT NULL,
    island INTEGER NOT NULL,
    parent_ids TEXT NOT NULL,
    source TEXT NOT NULL,
    score REAL,
    runtime REAL,
    status TEXT NOT NULL,
    error TEXT,
    embedding TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_programs_gen ON programs(generation);
CREATE INDEX IF NOT EXISTS idx_programs_island ON programs(island);
CREATE INDEX IF NOT EXISTS idx_programs_score ON programs(score);

CREATE TABLE IF NOT EXISTS generations (
    generation INTEGER PRIMARY KEY,
    started_at REAL NOT NULL,
    finished_at REAL,
    best_score REAL,
    candidates INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at REAL NOT NULL,
    finished_at REAL,
    problem TEXT NOT NULL,
    config TEXT NOT NULL,
    seed INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation INTEGER NOT NULL,
    island INTEGER,
    model TEXT NOT NULL,
    temperature REAL NOT NULL,
    prompt_hash TEXT NOT NULL,
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    cached INTEGER NOT NULL,
    elapsed REAL,
    created_at REAL NOT NULL
);
"""


@dataclass
class ProgramRow:
    id: int
    generation: int
    island: int
    parent_ids: list[int]
    source: str
    score: Optional[float]
    runtime: Optional[float]
    status: str
    error: Optional[str]
    embedding: Optional[list[float]]
    created_at: float


def _conn(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


class _LockedConn:
    """Thin wrapper that serializes all access to a sqlite3 connection."""

    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock):
        self._conn = conn
        self._lock = lock

    def execute(self, *args, **kwargs):
        with self._lock:
            return self._conn.execute(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        with self._lock:
            return self._conn.executescript(*args, **kwargs)

    def commit(self):
        with self._lock:
            return self._conn.commit()

    def close(self):
        with self._lock:
            return self._conn.close()


class ProgramDB:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        raw = _conn(self.path)
        self._conn = _LockedConn(raw, self._lock)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def start_run(self, problem: str, seed: int, config: dict) -> int:
        cur = self._conn.execute(
            "INSERT INTO runs(started_at, problem, config, seed) VALUES (?,?,?,?)",
            (time.time(), problem, json.dumps(config), seed),
        )
        self._conn.commit()
        return cur.lastrowid or 0

    def finish_run(self, run_id: int) -> None:
        self._conn.execute(
            "UPDATE runs SET finished_at=? WHERE id=?", (time.time(), run_id)
        )
        self._conn.commit()

    def start_generation(self, generation: int) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO generations(generation, started_at) VALUES (?,?)",
            (generation, time.time()),
        )
        self._conn.commit()

    def finish_generation(self, generation: int, best_score: float | None, candidates: int) -> None:
        self._conn.execute(
            "UPDATE generations SET finished_at=?, best_score=?, candidates=? WHERE generation=?",
            (time.time(), best_score, candidates, generation),
        )
        self._conn.commit()

    def insert_program(
        self,
        *,
        generation: int,
        island: int,
        parent_ids: list[int],
        source: str,
        score: float | None,
        runtime: float | None,
        status: str,
        error: str | None = None,
        embedding: list[float] | None = None,
    ) -> int:
        cur = self._conn.execute(
            """INSERT INTO programs(generation, island, parent_ids, source, score,
               runtime, status, error, embedding, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                generation,
                island,
                json.dumps(parent_ids),
                source,
                score,
                runtime,
                status,
                error,
                json.dumps(embedding) if embedding else None,
                time.time(),
            ),
        )
        self._conn.commit()
        return cur.lastrowid or 0

    def log_llm_call(
        self,
        *,
        generation: int,
        island: int | None,
        model: str,
        temperature: float,
        prompt_hash: str,
        prompt: str,
        response: str,
        cached: bool,
        elapsed: float | None,
    ) -> None:
        self._conn.execute(
            """INSERT INTO llm_calls(generation, island, model, temperature,
               prompt_hash, prompt, response, cached, elapsed, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                generation,
                island,
                model,
                temperature,
                prompt_hash,
                prompt,
                response,
                1 if cached else 0,
                elapsed,
                time.time(),
            ),
        )
        self._conn.commit()

    def top_k(self, *, island: int | None = None, k: int = 3, higher_is_better: bool = False) -> list[ProgramRow]:
        order = "DESC" if higher_is_better else "ASC"
        q = "SELECT * FROM programs WHERE status='ok' AND score IS NOT NULL"
        args: list = []
        if island is not None:
            q += " AND island=?"
            args.append(island)
        q += f" ORDER BY score {order} LIMIT ?"
        args.append(k)
        rows = self._conn.execute(q, args).fetchall()
        return [self._row(r) for r in rows]

    def island_population(self, island: int, limit: int = 100) -> list[ProgramRow]:
        rows = self._conn.execute(
            "SELECT * FROM programs WHERE island=? AND status='ok' "
            "ORDER BY id DESC LIMIT ?",
            (island, limit),
        ).fetchall()
        return [self._row(r) for r in rows]

    def best(self, higher_is_better: bool = False) -> ProgramRow | None:
        order = "DESC" if higher_is_better else "ASC"
        row = self._conn.execute(
            f"SELECT * FROM programs WHERE status='ok' AND score IS NOT NULL "
            f"ORDER BY score {order} LIMIT 1"
        ).fetchone()
        return self._row(row) if row else None

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) AS c FROM programs").fetchone()["c"]

    @staticmethod
    def _row(r: sqlite3.Row) -> ProgramRow:
        return ProgramRow(
            id=r["id"],
            generation=r["generation"],
            island=r["island"],
            parent_ids=json.loads(r["parent_ids"]),
            source=r["source"],
            score=r["score"],
            runtime=r["runtime"],
            status=r["status"],
            error=r["error"],
            embedding=json.loads(r["embedding"]) if r["embedding"] else None,
            created_at=r["created_at"],
        )


@contextmanager
def open_db(path: str | Path) -> Iterator[ProgramDB]:
    db = ProgramDB(path)
    try:
        yield db
    finally:
        db.close()
