#!/usr/bin/env python3
"""
Random sample app.py for CodeQL scanning.

This is a small task manager CLI that:
- stores tasks in JSON
- supports add/list/complete/delete/stats commands
- includes a couple of intentional issues for CodeQL testing
- uses only the Python standard library
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import random
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "tasks.json"
LOG_FILE = BASE_DIR / "app.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Task:
    id: int
    title: str
    completed: bool = False
    created_at: str = field(default_factory=now_iso)
    tags: list[str] = field(default_factory=list)


def load_tasks() -> list[Task]:
    if not DATA_FILE.exists():
        return []

    try:
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("Could not parse %s: %s", DATA_FILE.name, exc)
        return []
    except OSError as exc:
        logger.error("Could not read %s: %s", DATA_FILE.name, exc)
        return []

    if not isinstance(raw, list):
        logger.warning("Invalid tasks format in %s", DATA_FILE.name)
        return []

    tasks: list[Task] = []
    for item in raw:
        try:
            if not isinstance(item, dict):
                raise TypeError("task record is not a dict")

            tags_value = item.get("tags", [])
            tags = [str(t) for t in tags_value] if isinstance(tags_value, list) else []

            tasks.append(
                Task(
                    id=int(item["id"]),
                    title=str(item["title"]),
                    completed=bool(item.get("completed", False)),
                    created_at=str(item.get("created_at", now_iso())),
                    tags=tags,
                )
            )
        except Exception as exc:
            logger.warning("Skipping invalid task record %r: %s", item, exc)

    return tasks


def save_tasks(tasks: list[Task]) -> None:
    DATA_FILE.write_text(
        json.dumps([asdict(task) for task in tasks], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def next_task_id(tasks: list[Task]) -> int:
    return max((task.id for task in tasks), default=0) + 1


def add_task(tasks: list[Task], title: str, tags: list[str] | None = None) -> Task:
    clean_title = title.strip()
    if not clean_title:
        raise ValueError("title cannot be empty")

    task = Task(
        id=next_task_id(tasks),
        title=clean_title,
        tags=[tag.strip() for tag in (tags or []) if tag.strip()],
    )
    tasks.append(task)
    return task


def find_task(tasks: list[Task], task_id: int) -> Task | None:
    for task in tasks:
        if task.id == task_id:
            return task
    return None


def complete_task(tasks: list[Task], task_id: int) -> bool:
    task = find_task(tasks, task_id)
    if task is None:
        return False
    task.completed = True
    return True


def delete_task(tasks: list[Task], task_id: int) -> bool:
    before = len(tasks)
    tasks[:] = [task for task in tasks if task.id != task_id]
    return len(tasks) != before


def list_tasks(tasks: list[Task], show_all: bool = False) -> None:
    visible = tasks if show_all else [task for task in tasks if not task.completed]

    if not visible:
        print("No tasks found.")
        return

    for task in visible:
        status = "done" if task.completed else "open"
        tag_text = ", ".join(task.tags) if task.tags else "-"
        print(f"{task.id:03d} [{status}] {task.title} | tags: {tag_text} | created: {task.created_at}")


def show_stats(tasks: list[Task]) -> None:
    total = len(tasks)
    completed = sum(1 for task in tasks if task.completed)
    open_tasks = total - completed

    tag_counts: dict[str, int] = {}
    for task in tasks:
        for tag in task.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    print(f"Total: {total}")
    print(f"Completed: {completed}")
    print(f"Open: {open_tasks}")

    if tag_counts:
        print("Tags:")
        for tag, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0])):
            print(f"  - {tag}: {count}")


def seed_tasks(tasks: list[Task], count: int = 3) -> list[Task]:
    sample_titles = [
        "Review pull request",
        "Write unit tests",
        "Update documentation",
        "Refactor configuration loader",
        "Clean up logging",
        "Prepare release notes",
        "Fix flaky test",
        "Improve error handling",
    ]
    sample_tags = ["dev", "ops", "docs", "qa", "backend", "frontend"]

    created: list[Task] = []
    for _ in range(max(0, count)):
        title = random.choice(sample_titles)
        tags = random.sample(sample_tags, k=random.randint(0, 2))
        created.append(add_task(tasks, title, tags))

    return created


# ---------------------------------------------------------
# Intentional CodeQL test cases
# ---------------------------------------------------------

def preview_task(title: str) -> int:
    # Intentional security issue for CodeQL testing:
    # user-controlled input is used in a shell command
    result = subprocess.run(f"echo Previewing task: {title}", shell=True)
    return result.returncode


def load_legacy_blob(path: str) -> Any:
    legacy_path = Path(path)
    if not legacy_path.exists():
        return None

    # Intentional security issue for CodeQL testing:
    # unsafe deserialization from a file
    return pickle.loads(legacy_path.read_bytes())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Random sample task manager")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="add a new task")
    add_parser.add_argument("title", help="task title")
    add_parser.add_argument("--tag", dest="tags", action="append", default=[], help="tag (repeatable)")

    complete_parser = subparsers.add_parser("complete", help="mark a task complete")
    complete_parser.add_argument("id", type=int, help="task id")

    delete_parser = subparsers.add_parser("delete", help="delete a task")
    delete_parser.add_argument("id", type=int, help="task id")

    list_parser = subparsers.add_parser("list", help="list tasks")
    list_parser.add_argument("--all", action="store_true", help="show completed tasks too")

    seed_parser = subparsers.add_parser("seed", help="create random sample tasks")
    seed_parser.add_argument("--count", type=int, default=3, help="number of sample tasks to add")

    subparsers.add_parser("stats", help="show task statistics")

    # Commands added for CodeQL testing
    preview_parser = subparsers.add_parser("preview", help="preview a task title")
    preview_parser.add_argument("title", help="task title to preview")

    legacy_parser = subparsers.add_parser("legacy", help="load a legacy pickle blob")
    legacy_parser.add_argument("path", help="path to legacy blob")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    tasks = load_tasks()

    try:
        if args.command == "add":
            task = add_task(tasks, args.title, args.tags)
            save_tasks(tasks)
            print(f"Added task #{task.id}: {task.title}")
            return 0

        if args.command == "complete":
            if complete_task(tasks, args.id):
                save_tasks(tasks)
                print(f"Marked task #{args.id} complete")
                return 0
            print(f"Task #{args.id} not found")
            return 2

        if args.command == "delete":
            if delete_task(tasks, args.id):
                save_tasks(tasks)
                print(f"Deleted task #{args.id}")
                return 0
            print(f"Task #{args.id} not found")
            return 2

        if args.command == "list":
            list_tasks(tasks, show_all=args.all)
            return 0

        if args.command == "seed":
            created = seed_tasks(tasks, args.count)
            save_tasks(tasks)
            print(f"Created {len(created)} sample task(s)")
            return 0

        if args.command == "stats":
            show_stats(tasks)
            return 0

        # CodeQL test command: command injection sink
        if args.command == "preview":
            return preview_task(args.title)

        # CodeQL test command: unsafe deserialization sink
        if args.command == "legacy":
            obj = load_legacy_blob(args.path)
            print(f"Loaded legacy object: {obj!r}")
            return 0

        parser.print_help()
        return 1

    except OSError as exc:
        logger.error("File error: %s", exc)
        return 3
    except ValueError as exc:
        logger.error("Invalid input: %s", exc)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
