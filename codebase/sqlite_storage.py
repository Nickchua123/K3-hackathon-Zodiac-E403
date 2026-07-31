from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Iterable, Mapping

import pandas as pd

from embedding_index import DIMENSIONS, MODEL_NAME, build_post_text, embed_post, serialize_vector


APP_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = APP_DIR / "data" / "quality_hub.db"
WRITE_LOCK = RLock()

POST_COLUMNS = [
    "post_id",
    "title",
    "author",
    "topic",
    "content",
    "clicks",
    "likes",
    "hearts",
    "watch_time_sec",
    "completion_rate",
    "save_shares",
    "url",
    "created_at",
    "mock_summary",
    "mock_tags",
    "source",
]


def _read_env_file_value(key: str) -> str | None:
    env_path = APP_DIR / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        current_key, value = stripped.split("=", 1)
        if current_key.strip() == key:
            return value.strip().strip('"').strip("'")
    return None


def database_path() -> Path:
    configured = os.getenv("QUALITY_HUB_DB_PATH") or _read_env_file_value("QUALITY_HUB_DB_PATH")
    if not configured:
        return DEFAULT_DATABASE_PATH
    path = Path(configured)
    return path if path.is_absolute() else APP_DIR / path


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialize_database() -> None:
    with WRITE_LOCK, connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS posts (
                post_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                clicks REAL NOT NULL DEFAULT 0,
                likes REAL NOT NULL DEFAULT 0,
                hearts REAL NOT NULL DEFAULT 0,
                watch_time_sec REAL NOT NULL DEFAULT 0,
                completion_rate REAL NOT NULL DEFAULT 0,
                save_shares REAL NOT NULL DEFAULT 0,
                url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                mock_summary TEXT NOT NULL,
                mock_tags TEXT NOT NULL,
                source TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                inserted_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_posts_source ON posts(source);
            CREATE INDEX IF NOT EXISTS idx_posts_topic ON posts(topic);
            CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at);

            CREATE TABLE IF NOT EXISTS post_embeddings (
                post_id TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                vector BLOB NOT NULL,
                content_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(post_id) REFERENCES posts(post_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_embeddings_model ON post_embeddings(model);

            CREATE TABLE IF NOT EXISTS sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                posts_seen INTEGER NOT NULL DEFAULT 0,
                posts_changed INTEGER NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL
            );
            """
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_record(post: Mapping[str, Any], source: str | None = None) -> dict[str, Any]:
    record = {column: post.get(column, "") for column in POST_COLUMNS}
    record["source"] = source or str(record.get("source") or "unknown")
    for column in ["clicks", "likes", "hearts", "watch_time_sec", "completion_rate", "save_shares"]:
        try:
            record[column] = float(record.get(column) or 0)
        except (TypeError, ValueError):
            record[column] = 0.0
    for column in [
        "post_id",
        "title",
        "author",
        "topic",
        "content",
        "url",
        "created_at",
        "mock_summary",
        "mock_tags",
        "source",
    ]:
        record[column] = str(record.get(column) or "")
    return record


def content_hash(post: Mapping[str, Any]) -> str:
    payload = build_post_text(post).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def upsert_posts(
    posts: Iterable[Mapping[str, Any]],
    source: str | None = None,
) -> dict[str, int]:
    initialize_database()
    records = [_as_record(post, source=source) for post in posts]
    records = [record for record in records if record["post_id"]]
    stats = {"seen": len(records), "inserted": 0, "updated": 0, "unchanged": 0, "embedded": 0}
    if not records:
        return stats

    now = utc_now()
    with WRITE_LOCK, connect() as connection:
        for record in records:
            digest = content_hash(record)
            existing = connection.execute(
                """
                SELECT p.content_hash, e.model AS embedding_model, e.content_hash AS embedding_hash
                FROM posts p
                LEFT JOIN post_embeddings e ON e.post_id = p.post_id
                WHERE p.post_id = ?
                """,
                (record["post_id"],),
            ).fetchone()

            if existing is None:
                stats["inserted"] += 1
            elif existing["content_hash"] != digest:
                stats["updated"] += 1
            else:
                stats["unchanged"] += 1

            connection.execute(
                """
                INSERT INTO posts (
                    post_id, title, author, topic, content, clicks, likes, hearts,
                    watch_time_sec, completion_rate, save_shares, url, created_at,
                    mock_summary, mock_tags, source, content_hash, inserted_at, updated_at
                ) VALUES (
                    :post_id, :title, :author, :topic, :content, :clicks, :likes, :hearts,
                    :watch_time_sec, :completion_rate, :save_shares, :url, :created_at,
                    :mock_summary, :mock_tags, :source, :content_hash, :inserted_at, :updated_at
                )
                ON CONFLICT(post_id) DO UPDATE SET
                    title = excluded.title,
                    author = excluded.author,
                    topic = excluded.topic,
                    content = excluded.content,
                    clicks = excluded.clicks,
                    likes = excluded.likes,
                    hearts = excluded.hearts,
                    watch_time_sec = excluded.watch_time_sec,
                    completion_rate = excluded.completion_rate,
                    save_shares = excluded.save_shares,
                    url = excluded.url,
                    created_at = excluded.created_at,
                    mock_summary = excluded.mock_summary,
                    mock_tags = excluded.mock_tags,
                    source = excluded.source,
                    content_hash = excluded.content_hash,
                    updated_at = excluded.updated_at
                """,
                {
                    **record,
                    "content_hash": digest,
                    "inserted_at": now,
                    "updated_at": now,
                },
            )

            embedding_is_current = (
                existing is not None
                and existing["embedding_model"] == MODEL_NAME
                and existing["embedding_hash"] == digest
            )
            if not embedding_is_current:
                vector = serialize_vector(embed_post(record))
                connection.execute(
                    """
                    INSERT INTO post_embeddings (
                        post_id, model, dimensions, vector, content_hash, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(post_id) DO UPDATE SET
                        model = excluded.model,
                        dimensions = excluded.dimensions,
                        vector = excluded.vector,
                        content_hash = excluded.content_hash,
                        updated_at = excluded.updated_at
                    """,
                    (record["post_id"], MODEL_NAME, DIMENSIONS, vector, digest, now),
                )
                stats["embedded"] += 1
        connection.commit()
    return stats


def upsert_dataframe(frame: pd.DataFrame, source: str) -> dict[str, int]:
    return upsert_posts(frame.to_dict(orient="records"), source=source)


def load_posts_dataframe() -> pd.DataFrame:
    initialize_database()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                p.post_id, p.title, p.author, p.topic, p.content,
                p.clicks, p.likes, p.hearts, p.watch_time_sec,
                p.completion_rate, p.save_shares, p.url, p.created_at,
                p.mock_summary, p.mock_tags, p.source,
                e.model AS embedding_model,
                e.dimensions AS embedding_dimensions,
                e.vector AS embedding_vector
            FROM posts p
            LEFT JOIN post_embeddings e ON e.post_id = p.post_id
            """
        ).fetchall()
    if not rows:
        return pd.DataFrame(columns=POST_COLUMNS + ["embedding_model", "embedding_dimensions", "embedding_vector"])
    return pd.DataFrame([dict(row) for row in rows])


def database_stats() -> dict[str, Any]:
    initialize_database()
    with connect() as connection:
        post_count = int(connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0])
        embedding_count = int(connection.execute("SELECT COUNT(*) FROM post_embeddings").fetchone()[0])
        source_rows = connection.execute(
            "SELECT source, COUNT(*) AS count FROM posts GROUP BY source ORDER BY source"
        ).fetchall()
        latest_sync = connection.execute(
            """
            SELECT source, status, posts_seen, posts_changed, message, finished_at
            FROM sync_runs ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    return {
        "database_path": str(database_path()),
        "post_count": post_count,
        "embedding_count": embedding_count,
        "embedding_model": MODEL_NAME,
        "sources": {str(row["source"]): int(row["count"]) for row in source_rows},
        "latest_sync": dict(latest_sync) if latest_sync else None,
    }


def record_sync_run(
    source: str,
    status: str,
    posts_seen: int,
    posts_changed: int,
    message: str,
    started_at: str,
) -> None:
    finished_at = utc_now()
    with WRITE_LOCK, connect() as connection:
        connection.execute(
            """
            INSERT INTO sync_runs (
                source, status, posts_seen, posts_changed, message, started_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (source, status, posts_seen, posts_changed, message, started_at, finished_at),
        )
        connection.commit()


def rebuild_embeddings() -> int:
    initialize_database()
    frame = load_posts_dataframe()
    if frame.empty:
        return 0
    with WRITE_LOCK, connect() as connection:
        connection.execute("DELETE FROM post_embeddings")
        connection.commit()
    stats = upsert_posts(frame.to_dict(orient="records"))
    return stats["embedded"]
