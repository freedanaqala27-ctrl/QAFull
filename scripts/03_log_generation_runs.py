from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_GENERATIONS = PROJECT_ROOT / "outputs" / "raw_generations" / "generations.raw.v1.jsonl"
FILTERED_ACCEPTED = PROJECT_ROOT / "outputs" / "filtered" / "accepted" / "candidates.accepted.v1.jsonl"
FILTERED_REJECTED = PROJECT_ROOT / "outputs" / "filtered" / "rejected" / "candidates.rejected.v1.jsonl"
OUT_CSV = PROJECT_ROOT / "prompts" / "logs" / "generation_control_sheet.v1.csv"
OUT_JSON = PROJECT_ROOT / "prompts" / "logs" / "generation_run_summary.v1.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def group_by(records: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        grouped.setdefault(str(row.get(key, "")), []).append(row)
    return grouped


def count_values(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in records:
        value = str(row.get(key, "") or "MISSING")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def summarize_run(
    run_id: str,
    raw_records: list[dict[str, Any]],
    accepted_records: list[dict[str, Any]],
    rejected_records: list[dict[str, Any]],
) -> dict[str, Any]:
    sample = raw_records[0] if raw_records else {}
    latency_values = [int(r.get("latency_ms", 0) or 0) for r in raw_records]
    parse_fail_count = sum(r.get("parse_status") != "ok" for r in raw_records)
    schema_fail_count = sum(not bool(r.get("schema_valid")) for r in raw_records)

    return {
        "run_id": run_id,
        "provider": sample.get("provider", ""),
        "model_name": sample.get("model_name", ""),
        "temperature": sample.get("temperature"),
        "max_tokens": sample.get("max_tokens"),
        "candidates_requested": len(raw_records),
        "candidates_completed": len(raw_records),
        "parse_fail_count": parse_fail_count,
        "schema_fail_count": schema_fail_count,
        "accepted_count": len(accepted_records),
        "rejected_count": len(rejected_records),
        "mean_latency_ms": round(sum(latency_values) / max(1, len(latency_values)), 2) if latency_values else 0.0,
        "topics": json.dumps(count_values(raw_records, "topic"), ensure_ascii=False),
        "difficulties": json.dumps(count_values(raw_records, "difficulty"), ensure_ascii=False),
        "generation_exercise_types": json.dumps(count_values(raw_records, "generation_exercise_type"), ensure_ascii=False),
        "accepted_topics": json.dumps(count_values(accepted_records, "topic"), ensure_ascii=False),
        "accepted_difficulties": json.dumps(count_values(accepted_records, "difficulty"), ensure_ascii=False),
        "accepted_generation_exercise_types": json.dumps(
            count_values(accepted_records, "generation_exercise_type"),
            ensure_ascii=False,
        ),
        "raw_generation_file": str(RAW_GENERATIONS),
        "status": (
            "success"
            if raw_records and len(accepted_records) == len(raw_records) and schema_fail_count == 0
            else "partial"
            if accepted_records or raw_records
            else "failed"
        ),
        "notes": "",
    }


def build_run_summary_json(
    run_id: str,
    raw_records: list[dict[str, Any]],
    accepted_records: list[dict[str, Any]],
    rejected_records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "provider": raw_records[0].get("provider", "") if raw_records else "",
        "model_name": raw_records[0].get("model_name", "") if raw_records else "",
        "temperature": raw_records[0].get("temperature") if raw_records else None,
        "max_tokens": raw_records[0].get("max_tokens") if raw_records else None,
        "totals": {
            "raw_count": len(raw_records),
            "parse_fail_count": sum(r.get("parse_status") != "ok" for r in raw_records),
            "schema_fail_count": sum(not bool(r.get("schema_valid")) for r in raw_records),
            "accepted_count": len(accepted_records),
            "rejected_count": len(rejected_records),
        },
        "breakdowns": {
            "raw_by_topic": count_values(raw_records, "topic"),
            "raw_by_difficulty": count_values(raw_records, "difficulty"),
            "raw_by_generation_exercise_type": count_values(raw_records, "generation_exercise_type"),
            "accepted_by_topic": count_values(accepted_records, "topic"),
            "accepted_by_difficulty": count_values(accepted_records, "difficulty"),
            "accepted_by_generation_exercise_type": count_values(accepted_records, "generation_exercise_type"),
            "rejected_by_reason": count_rejection_reasons(rejected_records),
        },
    }


def count_rejection_reasons(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in records:
        for reason in row.get("rejection_reasons", []):
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-jsonl", default=str(RAW_GENERATIONS))
    parser.add_argument("--accepted-jsonl", default=str(FILTERED_ACCEPTED))
    parser.add_argument("--rejected-jsonl", default=str(FILTERED_REJECTED))
    parser.add_argument("--out-csv", default=str(OUT_CSV))
    parser.add_argument("--out-json", default=str(OUT_JSON))
    args = parser.parse_args()

    raw_records = read_jsonl(Path(args.raw_jsonl))
    accepted_records = read_jsonl(Path(args.accepted_jsonl))
    rejected_records = read_jsonl(Path(args.rejected_jsonl))

    grouped_raw = group_by(raw_records, "run_id")
    grouped_accepted = group_by(accepted_records, "run_id")
    grouped_rejected = group_by(rejected_records, "run_id")
    run_ids = sorted(set(grouped_raw) | set(grouped_accepted) | set(grouped_rejected))

    rows: list[dict[str, Any]] = []
    summary_doc = {
        "schema_version": "v1",
        "runs": [],
    }

    for run_id in run_ids:
        run_raw = grouped_raw.get(run_id, [])
        run_accepted = grouped_accepted.get(run_id, [])
        run_rejected = grouped_rejected.get(run_id, [])
        rows.append(summarize_run(run_id, run_raw, run_accepted, run_rejected))
        summary_doc["runs"].append(build_run_summary_json(run_id, run_raw, run_accepted, run_rejected))

    write_csv(rows, Path(args.out_csv))
    write_json(summary_doc, Path(args.out_json))
    print(f"Wrote {len(rows)} run summaries -> {args.out_csv}")
    print(f"Wrote structured run summary -> {args.out_json}")


if __name__ == "__main__":
    main()
