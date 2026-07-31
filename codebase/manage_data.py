from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import sqlite_storage


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def migrate() -> dict[str, Any]:
    from main import ensure_database_ready

    ensure_database_ready()
    return sqlite_storage.database_stats()


def reindex() -> dict[str, Any]:
    migrate()
    rebuilt = sqlite_storage.rebuild_embeddings()
    stats = sqlite_storage.database_stats()
    stats["rebuilt_embeddings"] = rebuilt
    return stats


def sync_discord() -> dict[str, Any]:
    from main import sync_discord_once

    migrate()
    sync_discord_once(force=True)
    return sqlite_storage.database_stats()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Quản lý SQLite, embedding và đồng bộ Discord."
    )
    parser.add_argument(
        "command",
        choices=("migrate", "stats", "reindex", "sync"),
        help=(
            "migrate: nhập CSV vào SQLite; stats: xem trạng thái; "
            "reindex: tạo lại embedding; sync: đồng bộ Discord ngay"
        ),
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    command = parse_args().command
    if command == "migrate":
        result = migrate()
    elif command == "reindex":
        result = reindex()
    elif command == "sync":
        result = sync_discord()
    else:
        sqlite_storage.initialize_database()
        result = sqlite_storage.database_stats()

    print_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
