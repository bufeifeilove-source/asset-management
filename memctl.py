from __future__ import annotations

import argparse
import sys

from memory_client import MemoryClient
from memory_config import load_config


def parse_tags(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mem", description="Memory CLI for Hermes and Claude Code")
    parser.add_argument("--client", choices=["claude_code", "hermes"], help="Override MEMORY_CLIENT_NAME")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search memory")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--type", choices=["preference", "fact", "decision", "correction"])
    search.add_argument("--no-shared", action="store_true")

    add = sub.add_parser("add", help="Queue a memory write and try to flush it")
    add.add_argument("text")
    add.add_argument("--type", choices=["preference", "fact", "decision", "correction"], default="fact")
    add.add_argument("--importance", type=int, default=3)
    add.add_argument("--tags", default="")
    add.add_argument("--scope", choices=["private", "shared"])
    add.add_argument("--target-id")
    add.add_argument("--no-flush", action="store_true")

    prefer = sub.add_parser("prefer", help="Add a user preference")
    prefer.add_argument("text")
    prefer.add_argument("--tags", default="preference")
    prefer.add_argument("--importance", type=int, default=4)
    prefer.add_argument("--no-flush", action="store_true")

    decision = sub.add_parser("decision", help="Add a decision record")
    decision.add_argument("text")
    decision.add_argument("--tags", default="decision")
    decision.add_argument("--importance", type=int, default=4)
    decision.add_argument("--no-flush", action="store_true")

    correct = sub.add_parser("correct", help="Add a correction")
    correct.add_argument("text")
    correct.add_argument("--target-id")
    correct.add_argument("--tags", default="correction")
    correct.add_argument("--importance", type=int, default=5)
    correct.add_argument("--no-flush", action="store_true")

    sub.add_parser("flush", help="Flush pending local queue writes")
    sub.add_parser("queue", help="Show local queue status")
    sub.add_parser("health", help="Check Qdrant, collections, and embedding API")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client = MemoryClient(load_config(args.client))

    if args.command == "search":
        results = client.search(
            args.query,
            limit=args.limit,
            memory_type=args.type,
            include_shared=not args.no_shared,
        )
        if not results:
            print("No memory found.")
            return 0
        for item in results:
            payload = item["payload"]
            print(
                f"[{payload.get('type', '?')}][importance={payload.get('importance', '?')}]"
                f"[{payload.get('created_at', '?')}][tags={','.join(payload.get('tags', []))}]"
            )
            print(payload.get("text", ""))
            print(f"id: {item['id']}  score: {item['score']:.4f}  collection: {item['collection']}")
            print()
        return 0

    if args.command in {"add", "prefer", "decision", "correct"}:
        if args.command == "add":
            memory_type = args.type
            target_id = args.target_id
            scope = args.scope
        elif args.command == "prefer":
            memory_type = "preference"
            target_id = None
            scope = None
        elif args.command == "decision":
            memory_type = "decision"
            target_id = None
            scope = None
        else:
            memory_type = "correction"
            target_id = args.target_id
            scope = None
        queue_id = client.enqueue_write(
            text=args.text,
            memory_type=memory_type,
            importance=args.importance,
            tags=parse_tags(args.tags),
            scope=scope,
            target_id=target_id,
        )
        print(f"Queued memory write: {queue_id}")
        if not args.no_flush:
            done, failed = client.flush(limit=20)
            print(f"Flush result: done={done} failed={failed}")
        return 0

    if args.command == "flush":
        done, failed = client.flush(limit=100)
        print(f"Flush result: done={done} failed={failed}")
        return 0

    if args.command == "queue":
        stats = client.queue.stats()
        print(f"Queue: pending={stats.get('pending', 0)} done={stats.get('done', 0)}")
        return 0

    if args.command == "health":
        for key, value in client.health().items():
            print(f"{key}: {value}")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
