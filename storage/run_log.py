"""
Appends one JSON record per processed symbol to a JSON-Lines file — this
is the raw feed the dashboard reads to show "what happened, what
didn't" across every run (not just the ones that triggered a
notification).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

RUN_LOG_PATH = "storage/run_log.jsonl"
MAX_LOG_LINES = 2000  # keep the file bounded; oldest entries roll off


def append_run(record: dict) -> None:
    os.makedirs(os.path.dirname(RUN_LOG_PATH), exist_ok=True)
    record = {"logged_at": datetime.now(timezone.utc).isoformat(), **record}

    lines = []
    if os.path.exists(RUN_LOG_PATH):
        with open(RUN_LOG_PATH, "r") as f:
            lines = f.readlines()

    lines.append(json.dumps(record, default=str) + "\n")
    lines = lines[-MAX_LOG_LINES:]

    with open(RUN_LOG_PATH, "w") as f:
        f.writelines(lines)


def read_all() -> list[dict]:
    if not os.path.exists(RUN_LOG_PATH):
        return []
    records = []
    with open(RUN_LOG_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records
