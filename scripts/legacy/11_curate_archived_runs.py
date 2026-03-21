from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_ROOT = PROJECT_ROOT / "results" / "runs"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results" / "curated"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Curate archived pipeline runs into a final formal research pool."
    )
    parser.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--include-smoke", action="store_true")
    parser.add_argument("--random-seed", type=int, default=42)
    return parser.parse_args()


def safe_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_iso_timestamp(value: Any) -> datetime:
    if not value:
        return datetime.min
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.min


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def read_jsonl_with_errors(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if not path.exists():
        return rows, errors

    with path.open("r", encoding="utf-8-sig") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                errors.append(
                    {
                        "path": str(path),
                        "line_number": line_number,
                        "error": exc.msg,
                    }
                )
    return rows, errors


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def to_exercise_record(
    payload: dict[str, Any],
    source_type: str,
    reference_source: str,
    generation_prompt: str = "",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "exercise_id": payload.get("exercise_id", ""),
        "source_type": source_type,
        "topic": payload.get("topic", ""),
        "difficulty": payload.get("difficulty", ""),
        "exercise_type": payload.get("exercise_type", ""),
        "instruction_text": payload.get("instruction_text", ""),
        "starter_code": payload.get("starter_code", ""),
        "expected_output": payload.get("expected_output", ""),
        "constraints": payload.get("constraints", []),
        "solution": payload.get("solution", ""),
        "test_cases": payload.get("test_cases", []),
        "reference_source": reference_source,
        "generation_prompt": generation_prompt,
        "notes": notes or payload.get("notes", ""),
        "title": payload.get("title", ""),
        "programming_language": payload.get("programming_language", "Python"),
        "framework": payload.get("framework", ""),
        "has_code": payload.get("has_code"),
        "learning_objectives": payload.get("learning_objectives", []),
        "prerequisite_concepts": payload.get("prerequisite_concepts", []),
        "keywords": payload.get("keywords", []),
        "estimated_time_minutes": payload.get("estimated_time_minutes"),
        "target_learner_level": payload.get("target_learner_level", ""),
        "course_context": payload.get("course_context", ""),
        "prompt_id": payload.get("prompt_id", ""),
        "prompt_version": payload.get("prompt_version", ""),
        "provider": payload.get("provider", ""),
        "model_name": payload.get("model_name", ""),
        "generation_id": payload.get("generation_id", ""),
        "generated_at": payload.get("generated_at", ""),
        "matched_reference_exercise_id": payload.get("matched_reference_exercise_id", ""),
    }


def materialize_ai_dataset(pair_records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "v1",
        "dataset_name": "ai_exercises.curated.v1",
        "description": "Curated AI-generated deep learning programming exercises selected across archived runs.",
        "items": [dict(row["ai_payload"]) for row in pair_records],
    }


def build_exercises_all(pair_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for pair_row in pair_records:
        reference_payload = dict(pair_row["reference_payload"])
        reference_payload.setdefault("exercise_id", pair_row["reference_exercise_id"])
        ai_payload = dict(pair_row["ai_payload"])

        for record in [
            to_exercise_record(
                payload=reference_payload,
                source_type="Expert",
                reference_source=pair_row.get("reference_source", ""),
                generation_prompt="",
                notes=reference_payload.get("notes", ""),
            ),
            to_exercise_record(
                payload=ai_payload,
                source_type="AI",
                reference_source=pair_row.get("reference_source", ""),
                generation_prompt=ai_payload.get("generation_prompt", ""),
                notes=ai_payload.get("notes", ""),
            ),
        ]:
            if record["exercise_id"] in seen_ids:
                continue
            rows.append(record)
            seen_ids.add(record["exercise_id"])

    return sorted(rows, key=lambda row: (row.get("source_type", ""), row.get("exercise_id", "")))


def build_blind_mapping_rows(pair_records: list[dict[str, Any]], random_seed: int) -> list[dict[str, Any]]:
    blind_pool: list[dict[str, Any]] = []
    for pair_row in pair_records:
        blind_pool.append(
            {
                "exercise_id": pair_row["reference_exercise_id"],
                "source_type": "Expert",
                "topic": pair_row.get("topic", ""),
                "difficulty": pair_row.get("difficulty", ""),
                "exercise_type": pair_row.get("reference_exercise_type_original", ""),
            }
        )
        blind_pool.append(
            {
                "exercise_id": pair_row["ai_exercise_id"],
                "source_type": "AI",
                "topic": pair_row.get("topic", ""),
                "difficulty": pair_row.get("difficulty", ""),
                "exercise_type": pair_row.get("generation_exercise_type", ""),
            }
        )

    rng = random.Random(random_seed)
    rng.shuffle(blind_pool)
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(blind_pool, start=1):
        rows.append({"blind_exercise_id": f"B{index:04d}", **row})
    return rows


def summarize_distribution(
    pair_records: list[dict[str, Any]],
    field_name: str,
) -> list[dict[str, Any]]:
    counts = Counter((row.get(field_name, "") or "UNKNOWN") for row in pair_records)
    total = len(pair_records) or 1
    return [
        {
            "dimension": field_name,
            "value": value,
            "count": count,
            "rate": round(count / total, 4),
        }
        for value, count in sorted(counts.items())
    ]


def candidate_sort_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    row = candidate["pair_record"]
    return (
        safe_float(row.get("soft_rank_score")),
        safe_float(row.get("instruction_completeness_ratio")),
        safe_float(row.get("structure_completeness_ratio")),
        1 if row.get("code_validity_passed") else 0,
        parse_iso_timestamp(row.get("generated_at")),
        candidate["run_id"],
    )


def curated_ai_exercise_id(reference_exercise_id: str) -> str:
    return f"AI-CURATED-{reference_exercise_id}"


def curated_pair_id(reference_exercise_id: str) -> str:
    return f"PAIR-CURATED-{reference_exercise_id}"


def clone_curated_pair(
    candidate: dict[str, Any],
    selection_rank_global: int,
) -> dict[str, Any]:
    source_row = candidate["pair_record"]
    reference_id = source_row["reference_exercise_id"]
    ai_id = curated_ai_exercise_id(reference_id)
    pair_id = curated_pair_id(reference_id)

    cloned = dict(source_row)
    cloned["pair_id"] = pair_id
    cloned["ai_exercise_id"] = ai_id
    cloned["selection_reason"] = "curated_best_across_archived_runs"
    cloned["selection_rank_global"] = selection_rank_global
    cloned["selected_from_run_id"] = candidate["run_id"]
    cloned["selected_from_original_pair_id"] = source_row.get("pair_id", "")
    cloned["selected_from_archive_dir"] = str(candidate["run_dir"])

    ai_payload = dict(source_row.get("ai_payload") or {})
    ai_payload["exercise_id"] = ai_id
    ai_payload["matched_reference_exercise_id"] = reference_id
    ai_payload["source_type"] = "AI"
    ai_payload["source_subtype"] = "LLM-Generated"
    ai_payload["record_status"] = "accepted"
    ai_payload["comparison_status"] = "comparable"
    ai_payload["selected_from_run_id"] = candidate["run_id"]
    ai_payload["selected_from_original_pair_id"] = source_row.get("pair_id", "")
    cloned["ai_payload"] = ai_payload

    reference_payload = dict(source_row.get("reference_payload") or {})
    reference_payload.setdefault("exercise_id", reference_id)
    cloned["reference_payload"] = reference_payload
    return cloned


def build_curation_audit_rows(
    grouped_candidates: dict[str, list[dict[str, Any]]],
    curated_pairs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected_lookup = {row["reference_exercise_id"]: row for row in curated_pairs}
    rows: list[dict[str, Any]] = []

    for reference_id, candidates in sorted(grouped_candidates.items()):
        ordered = sorted(candidates, key=candidate_sort_key, reverse=True)
        selected_pair = selected_lookup.get(reference_id)
        selected_run_id = selected_pair.get("selected_from_run_id", "") if selected_pair else ""
        selected_original_pair_id = (
            selected_pair.get("selected_from_original_pair_id", "") if selected_pair else ""
        )
        for rank, candidate in enumerate(ordered, start=1):
            pair_row = candidate["pair_record"]
            rows.append(
                {
                    "reference_exercise_id": reference_id,
                    "topic": pair_row.get("topic", ""),
                    "difficulty": pair_row.get("difficulty", ""),
                    "exercise_type": pair_row.get("generation_exercise_type", ""),
                    "candidate_rank_within_reference": rank,
                    "run_id": candidate["run_id"],
                    "original_pair_id": pair_row.get("pair_id", ""),
                    "original_ai_exercise_id": pair_row.get("ai_exercise_id", ""),
                    "soft_rank_score": pair_row.get("soft_rank_score"),
                    "instruction_completeness_ratio": pair_row.get("instruction_completeness_ratio"),
                    "structure_completeness_ratio": pair_row.get("structure_completeness_ratio"),
                    "code_validity_passed": pair_row.get("code_validity_passed"),
                    "generated_at": pair_row.get("generated_at", ""),
                    "selected_for_curated_pool": (
                        candidate["run_id"] == selected_run_id
                        and pair_row.get("pair_id", "") == selected_original_pair_id
                    ),
                }
            )
    return rows


def load_run_candidates(
    runs_root: Path,
    include_smoke: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []

    if not runs_root.exists():
        return candidates, run_rows, parse_errors

    for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        run_id = run_dir.name
        if not include_smoke and run_id.endswith("-smoke"):
            run_rows.append(
                {
                    "run_id": run_id,
                    "status": "skipped_smoke",
                    "num_pairs": 0,
                    "topic_filter": "",
                    "difficulty_filter": "",
                    "exercise_type_filter": "",
                }
            )
            continue

        manifest_path = run_dir / "results" / "pipeline_manifest.v1.json"
        final_pairs_path = run_dir / "results" / "final_pairs.v1.jsonl"
        if not manifest_path.exists():
            run_rows.append(
                {
                    "run_id": run_id,
                    "status": "skipped_missing_manifest",
                    "num_pairs": 0,
                    "topic_filter": "",
                    "difficulty_filter": "",
                    "exercise_type_filter": "",
                }
            )
            continue

        manifest = read_json(manifest_path)
        row = {
            "run_id": run_id,
            "status": manifest.get("status", ""),
            "num_pairs": int(manifest.get("num_pairs", 0) or 0),
            "topic_filter": manifest.get("topic_filter", ""),
            "difficulty_filter": manifest.get("difficulty_filter", ""),
            "exercise_type_filter": manifest.get("exercise_type_filter", ""),
            "reference_id_filter": manifest.get("reference_id_filter", ""),
        }

        if manifest.get("status") != "completed":
            row["status"] = "skipped_incomplete"
            run_rows.append(row)
            continue
        if int(manifest.get("num_pairs", 0) or 0) <= 0:
            row["status"] = "skipped_zero_pairs"
            run_rows.append(row)
            continue
        if not final_pairs_path.exists():
            row["status"] = "skipped_missing_final_pairs"
            run_rows.append(row)
            continue

        pair_rows, errors = read_jsonl_with_errors(final_pairs_path)
        parse_errors.extend(errors)
        row["parsed_pair_rows"] = len(pair_rows)
        row["json_parse_errors"] = len(errors)
        row["status"] = "included"
        run_rows.append(row)

        for pair_row in pair_rows:
            reference_id = pair_row.get("reference_exercise_id", "")
            if not reference_id:
                continue
            candidates.append(
                {
                    "run_id": run_id,
                    "run_dir": run_dir,
                    "manifest": manifest,
                    "pair_record": pair_row,
                }
            )

    return candidates, run_rows, parse_errors


def main() -> None:
    args = parse_args()

    candidates, run_rows, parse_errors = load_run_candidates(args.runs_root, args.include_smoke)
    grouped_candidates: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        reference_id = candidate["pair_record"]["reference_exercise_id"]
        grouped_candidates.setdefault(reference_id, []).append(candidate)

    curated_pairs: list[dict[str, Any]] = []
    for index, reference_id in enumerate(sorted(grouped_candidates), start=1):
        best_candidate = max(grouped_candidates[reference_id], key=candidate_sort_key)
        curated_pairs.append(clone_curated_pair(best_candidate, selection_rank_global=index))

    curated_pairs = sorted(curated_pairs, key=lambda row: row["reference_exercise_id"])
    exercises_all = build_exercises_all(curated_pairs)
    ai_dataset = materialize_ai_dataset(curated_pairs)
    blind_mapping_rows = build_blind_mapping_rows(curated_pairs, args.random_seed)
    audit_rows = build_curation_audit_rows(grouped_candidates, curated_pairs)
    distribution_rows = (
        summarize_distribution(curated_pairs, "topic")
        + summarize_distribution(curated_pairs, "difficulty")
        + summarize_distribution(curated_pairs, "generation_exercise_type")
    )

    included_runs = [row for row in run_rows if row.get("status") == "included"]
    manifest = {
        "schema_version": "v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "runs_root": str(args.runs_root),
        "include_smoke": args.include_smoke,
        "random_seed": args.random_seed,
        "total_run_dirs_scanned": len(run_rows),
        "included_run_count": len(included_runs),
        "skipped_run_count": len(run_rows) - len(included_runs),
        "candidate_pair_rows_loaded": len(candidates),
        "curated_pair_count": len(curated_pairs),
        "curated_exercise_count": len(exercises_all),
        "curated_ai_item_count": len(ai_dataset["items"]),
        "unique_reference_count": len({row["reference_exercise_id"] for row in curated_pairs}),
        "json_parse_error_count": len(parse_errors),
        "topic_distribution": {
            row["value"]: row["count"]
            for row in distribution_rows
            if row["dimension"] == "topic"
        },
        "difficulty_distribution": {
            row["value"]: row["count"]
            for row in distribution_rows
            if row["dimension"] == "difficulty"
        },
        "exercise_type_distribution": {
            row["value"]: row["count"]
            for row in distribution_rows
            if row["dimension"] == "generation_exercise_type"
        },
    }

    output_dir = args.output_dir
    write_jsonl(curated_pairs, output_dir / "final_pairs.curated.v1.jsonl")
    write_jsonl(exercises_all, output_dir / "exercises_all.curated.v1.jsonl")
    write_json(ai_dataset, output_dir / "ai_exercises.curated.v1.json")
    write_csv(blind_mapping_rows, output_dir / "blind_mapping.curated.v1.csv")
    write_csv(audit_rows, output_dir / "curation_audit.v1.csv")
    write_csv(run_rows, output_dir / "run_inventory.v1.csv")
    write_csv(distribution_rows, output_dir / "distribution_summary.v1.csv")
    write_csv(parse_errors, output_dir / "parse_errors.v1.csv")
    write_json(manifest, output_dir / "curation_manifest.v1.json")

    print(f"Scanned {len(run_rows)} archived run directories.")
    print(f"Included {len(included_runs)} runs with usable final pairs.")
    print(f"Loaded {len(candidates)} candidate pair rows across archived runs.")
    print(f"Selected {len(curated_pairs)} curated final pairs -> {output_dir / 'final_pairs.curated.v1.jsonl'}")
    print(f"Wrote curated exercises -> {output_dir / 'exercises_all.curated.v1.jsonl'}")
    print(f"Wrote curated AI dataset -> {output_dir / 'ai_exercises.curated.v1.json'}")
    print(f"Wrote curation manifest -> {output_dir / 'curation_manifest.v1.json'}")


if __name__ == "__main__":
    main()
