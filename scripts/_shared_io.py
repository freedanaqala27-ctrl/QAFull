from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def read_csv_rows(path: Path, *, encoding: str = "utf-8-sig") -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding=encoding, newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl_rows(path: Path, *, encoding: str = "utf-8-sig") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding=encoding) as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_csv_rows(
    rows: list[dict[str, Any]],
    path: Path,
    *,
    encoding: str = "utf-8",
    fieldnames: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding=encoding)
        return

    ordered_fieldnames = list(fieldnames or [])
    if not ordered_fieldnames:
        seen: set[str] = set()
        for row in rows:
            for key in row.keys():
                if key not in seen:
                    ordered_fieldnames.append(key)
                    seen.add(key)

    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ordered_fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl_rows(
    rows: list[dict[str, Any]],
    path: Path,
    *,
    encoding: str = "utf-8",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding) as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=True) + "\n")


def write_json_doc(
    doc: dict[str, Any],
    path: Path,
    *,
    encoding: str = "utf-8",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2, allow_nan=True), encoding=encoding)


def index_rows_by_key(
    rows: list[dict[str, Any]],
    key_field: str,
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(key_field, "") or "").strip()
        if key:
            index[key] = row
    return index
