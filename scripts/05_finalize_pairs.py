from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REFERENCE_INDEX = PROJECT_ROOT / "data" / "processed" / "reference_index.v1.jsonl"
PROMPT_RECORDS = PROJECT_ROOT / "data" / "processed" / "prompt_records.v1.jsonl"
ACCEPTED = PROJECT_ROOT / "outputs" / "filtered" / "accepted" / "candidates.accepted.v1.jsonl"
FINAL_PAIRS = PROJECT_ROOT / "results" / "final_pairs.v1.jsonl"
EXERCISES_ALL = PROJECT_ROOT / "results" / "exercises_all.v1.jsonl"
AI_DATASET = PROJECT_ROOT / "data" / "ai_generated" / "accepted" / "ai_exercises.accepted.v1.json"
BLIND_MAPPING = PROJECT_ROOT / "data" / "human_eval" / "blind_mapping.generated.v1.csv"
PAIR_COVERAGE = PROJECT_ROOT / "results" / "pair_coverage.v1.csv"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


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
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_reference_index(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    return {row["exercise_id"]: row for row in rows}


def load_prompt_index(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    return {row["prompt_id"]: row for row in rows}


def group_by_reference(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        grouped.setdefault(row["reference_exercise_id"], []).append(row)
    return grouped


def rank_score(record: dict[str, Any]) -> float:
    return float(record.get("soft_rank_score", 0.0) or 0.0)


def rank_accepted_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=rank_score, reverse=True)


def build_ai_exercise_id(reference_exercise_id: str, rank: int) -> str:
    return f"AI-{reference_exercise_id}-{rank:02d}"


def build_final_pair_record(
    accepted_record: dict[str, Any],
    reference_item: dict[str, Any],
    prompt_record: dict[str, Any] | None,
    rank: int,
) -> dict[str, Any]:
    ai_exercise_id = build_ai_exercise_id(reference_item["exercise_id"], rank)
    generation_prompt = ""
    prompt_version = accepted_record.get("prompt_version", "")
    if prompt_record:
        generation_prompt = prompt_record.get("generation_prompt") or prompt_record.get("rendered_prompt", "")
        prompt_version = prompt_record.get("prompt_version", prompt_version)

    ai_payload = dict(accepted_record.get("payload") or {})
    ai_payload.update(
        {
            "exercise_id": ai_exercise_id,
            "source_type": "AI",
            "source_subtype": "LLM-Generated",
            "record_status": "accepted",
            "comparison_status": "comparable",
            "prompt_id": accepted_record.get("prompt_id", ""),
            "prompt_version": prompt_version,
            "provider": accepted_record.get("provider", ""),
            "model_name": accepted_record.get("model_name", ""),
            "generation_id": accepted_record.get("generation_id", ""),
            "generated_at": accepted_record.get("generation_finished_at", ""),
            "generation_prompt": generation_prompt,
            "reference_source": reference_item.get("reference_source", ""),
            "matched_reference_exercise_id": reference_item["exercise_id"],
        }
    )

    return {
        "pair_id": f"PAIR-{reference_item['exercise_id']}-{rank:02d}",
        "reference_exercise_id": reference_item["exercise_id"],
        "ai_exercise_id": ai_exercise_id,
        "generation_id": accepted_record.get("generation_id", ""),
        "prompt_id": accepted_record.get("prompt_id", ""),
        "prompt_version": prompt_version,
        "provider": accepted_record.get("provider", ""),
        "model_name": accepted_record.get("model_name", ""),
        "generated_at": accepted_record.get("generation_finished_at", ""),
        "topic": reference_item["topic"],
        "difficulty": reference_item["difficulty"],
        "reference_exercise_type_original": reference_item["reference_exercise_type_original"],
        "generation_exercise_type": reference_item["generation_exercise_type"],
        "reference_source_type": "Expert",
        "ai_source_type": "AI",
        "reference_source": reference_item.get("reference_source", ""),
        "matched_reference_exercise_id": reference_item["exercise_id"],
        "pair_match_basis": "topic+difficulty+exercise_type",
        "pair_quality_rank_score": rank_score(accepted_record),
        "selection_rank": rank,
        "soft_rank_score": accepted_record.get("soft_rank_score", rank_score(accepted_record)),
        "instruction_completeness_ratio": accepted_record.get("instruction_ratio"),
        "structure_completeness_ratio": accepted_record.get("structure_ratio"),
        "code_validity_passed": accepted_record.get("code_parse_ok"),
        "duplicate_risk_flag": float(accepted_record.get("duplicate_penalty", 0.0) or 0.0) >= 0.85,
        "selection_reason": "highest_ranked_after_hard_filter",
        "reference_payload": reference_item["reference_payload"],
        "ai_payload": ai_payload,
    }


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
    items = []
    for row in pair_records:
        payload = dict(row["ai_payload"])
        items.append(payload)

    return {
        "schema_version": "v1",
        "dataset_name": "ai_exercises.accepted.v1",
        "description": "Accepted AI-generated deep learning programming exercises.",
        "items": items,
    }


def build_exercises_all(
    pair_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
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
    rows: list[dict[str, Any]] = []
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
    for index, row in enumerate(blind_pool, start=1):
        rows.append({"blind_exercise_id": f"B{index:04d}", **row})
    return rows


def build_pair_coverage_rows(
    reference_index: dict[str, dict[str, Any]],
    grouped_accepted: dict[str, list[dict[str, Any]]],
    final_pairs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected_by_reference = {row["reference_exercise_id"]: row for row in final_pairs}
    rows: list[dict[str, Any]] = []
    for reference_id, reference_item in sorted(reference_index.items()):
        accepted_rows = grouped_accepted.get(reference_id, [])
        ranked_rows = rank_accepted_candidates(accepted_rows)
        selected_pair = selected_by_reference.get(reference_id)
        rows.append(
            {
                "reference_exercise_id": reference_id,
                "topic": reference_item.get("topic", ""),
                "difficulty": reference_item.get("difficulty", ""),
                "reference_exercise_type": reference_item.get("reference_exercise_type_original", ""),
                "accepted_candidate_count": len(accepted_rows),
                "selected_ai_exercise_id": selected_pair.get("ai_exercise_id", "") if selected_pair else "",
                "pair_built": bool(selected_pair),
                "top_soft_rank_score": ranked_rows[0].get("soft_rank_score") if ranked_rows else None,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k-per-reference", type=int, default=1)
    parser.add_argument("--fail-on-empty-ai", action="store_true")
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args()

    reference_index = load_reference_index(REFERENCE_INDEX)
    prompt_index = load_prompt_index(PROMPT_RECORDS)
    accepted_records = read_jsonl(ACCEPTED)
    if not accepted_records and args.fail_on_empty_ai:
        raise SystemExit("No accepted AI candidates found. Aborting pair finalization.")

    grouped = group_by_reference(accepted_records)
    final_pairs: list[dict[str, Any]] = []

    for reference_exercise_id, rows in sorted(grouped.items()):
        ranked = rank_accepted_candidates(rows)[: args.top_k_per_reference]
        reference_item = reference_index[reference_exercise_id]
        for rank, row in enumerate(ranked, start=1):
            prompt_record = prompt_index.get(row.get("prompt_id", ""))
            final_pairs.append(build_final_pair_record(row, reference_item, prompt_record, rank))

    pair_coverage_rows = build_pair_coverage_rows(reference_index, grouped, final_pairs)
    ai_dataset = materialize_ai_dataset(final_pairs)
    exercises_all = build_exercises_all(final_pairs)
    blind_mapping_rows = build_blind_mapping_rows(final_pairs, args.random_seed)

    write_jsonl(final_pairs, FINAL_PAIRS)
    write_json(ai_dataset, AI_DATASET)
    write_jsonl(exercises_all, EXERCISES_ALL)
    write_csv(blind_mapping_rows, BLIND_MAPPING)
    write_csv(pair_coverage_rows, PAIR_COVERAGE)

    print(f"Wrote {len(final_pairs)} final pairs -> {FINAL_PAIRS}")
    print(f"Wrote accepted AI dataset -> {AI_DATASET}")
    print(f"Wrote {len(exercises_all)} exercises -> {EXERCISES_ALL}")
    print(f"Wrote blind mapping template -> {BLIND_MAPPING}")
    print(f"Wrote pair coverage report -> {PAIR_COVERAGE}")


if __name__ == "__main__":
    main()
