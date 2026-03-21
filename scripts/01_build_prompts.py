from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FROZEN_MAIN = PROJECT_ROOT / "data" / "frozen" / "expert_exercises.main_frozen.v1.json"
MASTER_TEMPLATE = PROJECT_ROOT / "prompts" / "v1" / "master" / "MP-v1.md"
SUBTEMPLATE_DIR = PROJECT_ROOT / "prompts" / "v1" / "subtemplates"
OUT_JSONL = PROJECT_ROOT / "data" / "processed" / "prompt_records.v1.jsonl"
REFERENCE_INDEX_OUT = PROJECT_ROOT / "data" / "processed" / "reference_index.v1.jsonl"

SUPPORTED_GENERATION_TYPES = {
    "code completion",
    "model building",
    "model revision",
    "training-analysis",
}

REFERENCE_TO_GENERATION_TYPE = {
    "code completion": "code completion",
    "concept-to-code": "code completion",
    "model building": "model building",
    "model revision": "model revision",
    "training-analysis": "training-analysis",
}

SUBTEMPLATE_NAME_MAP = {
    "code completion": "CC-v1.md",
    "model building": "MB-v1.md",
    "model revision": "MR-v1.md",
    "training-analysis": "TA-v1.md",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_generation_exercise_type(reference_type: str) -> str:
    if reference_type not in REFERENCE_TO_GENERATION_TYPE:
        raise ValueError(f"Unsupported reference exercise_type: {reference_type}")
    return REFERENCE_TO_GENERATION_TYPE[reference_type]


def replace_placeholders(template_text: str, mapping: dict[str, Any]) -> str:
    rendered = template_text
    for key, value in mapping.items():
        placeholder = "{" + key + "}"
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False)
        rendered = rendered.replace(placeholder, str(value))
    return rendered


def infer_reference_source(item: dict[str, Any]) -> str:
    if item.get("reference_source"):
        return str(item["reference_source"])
    if item.get("source_url"):
        return str(item["source_url"])
    if item.get("source_subtype"):
        return str(item["source_subtype"])
    return str(item.get("course_context", ""))


def infer_source_title(item: dict[str, Any]) -> str:
    return str(item.get("source_title") or item.get("course_context") or item.get("title") or "")


def infer_chapter_or_section(item: dict[str, Any]) -> str:
    if item.get("chapter_or_section"):
        return str(item["chapter_or_section"])
    return str(item.get("course_context", ""))


def build_control_variables(reference_item: dict[str, Any]) -> dict[str, Any]:
    generation_type = normalize_generation_exercise_type(reference_item["exercise_type"])
    return {
        "REFERENCE_EXERCISE_ID": reference_item["exercise_id"],
        "TOPIC": reference_item["topic"],
        "DIFFICULTY": reference_item["difficulty"],
        "EXERCISE_TYPE": generation_type,
        "FRAMEWORK": reference_item.get("framework", ""),
        "TARGET_LEARNER_LEVEL": reference_item.get("target_learner_level", ""),
        "ESTIMATED_TIME_MINUTES": reference_item.get("estimated_time_minutes", 0),
        "LEARNING_OBJECTIVES": reference_item.get("learning_objectives", []),
        "PREREQUISITE_CONCEPTS": reference_item.get("prerequisite_concepts", []),
        "COURSE_CONTEXT": reference_item.get("course_context", ""),
    }


def summarize_generation_constraints(reference_item: dict[str, Any], generation_type: str) -> str:
    parts = [
        f"topic={reference_item.get('topic', '')}",
        f"difficulty={reference_item.get('difficulty', '')}",
        f"exercise_type={generation_type}",
        f"target_learner_level={reference_item.get('target_learner_level', '')}",
        f"estimated_time_minutes={reference_item.get('estimated_time_minutes', 0)}",
        "must_match_reference_scope=true",
        "must_be_single_bounded_task=true",
        "must_return_json=true",
    ]
    return "; ".join(parts)


def build_selection_signature(reference_item: dict[str, Any], generation_type: str, prompt_version: str) -> str:
    parts = [
        reference_item["exercise_id"],
        reference_item.get("topic", ""),
        reference_item.get("difficulty", ""),
        generation_type,
        prompt_version,
    ]
    return "|".join(parts)


def build_prompt_record(
    reference_item: dict[str, Any],
    prompt_version: str,
    master_template_text: str,
    subtemplate_text: str,
    subtemplate_name: str,
) -> dict[str, Any]:
    generation_type = normalize_generation_exercise_type(reference_item["exercise_type"])
    control_vars = build_control_variables(reference_item)
    rendered_prompt = replace_placeholders(master_template_text, control_vars)
    rendered_prompt = rendered_prompt.rstrip() + "\n\n" + subtemplate_text.strip() + "\n"
    created_at = timestamp_now()
    generation_constraints_summary = summarize_generation_constraints(reference_item, generation_type)
    selection_signature = build_selection_signature(reference_item, generation_type, prompt_version)

    return {
        "prompt_id": f"{reference_item['exercise_id']}__{prompt_version}",
        "prompt_version": prompt_version,
        "reference_exercise_id": reference_item["exercise_id"],
        "reference_exercise_type_original": reference_item["exercise_type"],
        "generation_exercise_type": generation_type,
        "selection_signature": selection_signature,
        "generation_constraints_hash": sha256_text(generation_constraints_summary),
        "topic": reference_item["topic"],
        "difficulty": reference_item["difficulty"],
        "framework": reference_item.get("framework", ""),
        "target_learner_level": reference_item.get("target_learner_level", ""),
        "estimated_time_minutes": reference_item.get("estimated_time_minutes", 0),
        "learning_objectives": reference_item.get("learning_objectives", []),
        "prerequisite_concepts": reference_item.get("prerequisite_concepts", []),
        "course_context": reference_item.get("course_context", ""),
        "control_variables": control_vars,
        "master_template_name": MASTER_TEMPLATE.name,
        "master_template_version": MASTER_TEMPLATE.stem,
        "subtemplate_name": subtemplate_name,
        "subtemplate_version": Path(subtemplate_name).stem,
        "rendered_prompt": rendered_prompt,
        "generation_prompt": rendered_prompt,
        "prompt_text_hash": sha256_text(rendered_prompt),
        "created_at": created_at,
        "generation_constraints_summary": generation_constraints_summary,
        "expected_output_keys": [
            "title",
            "topic",
            "difficulty",
            "exercise_type",
            "instruction_text",
            "programming_language",
            "framework",
            "has_code",
            "starter_code",
            "constraints",
            "expected_output",
            "test_cases",
            "solution",
            "learning_objectives",
            "prerequisite_concepts",
            "keywords",
            "estimated_time_minutes",
            "target_learner_level",
            "course_context",
            "notes",
        ],
    }


def flatten_reference_items(frozen_doc: dict[str, Any]) -> list[dict[str, Any]]:
    items = frozen_doc.get("items", [])
    if not isinstance(items, list):
        raise TypeError("Frozen dataset must contain top-level 'items' list.")
    return items


def matches_filters(
    item: dict[str, Any],
    topic: str | None,
    difficulty: str | None,
    exercise_type: str | None,
    reference_id: str | None,
) -> bool:
    generation_type = normalize_generation_exercise_type(item["exercise_type"])

    if topic and str(item.get("topic", "")).lower() != topic.lower():
        return False
    if difficulty and str(item.get("difficulty", "")).lower() != difficulty.lower():
        return False
    if exercise_type:
        requested = exercise_type.lower()
        if generation_type.lower() != requested and str(item.get("exercise_type", "")).lower() != requested:
            return False
    if reference_id and str(item.get("exercise_id", "")).lower() != reference_id.lower():
        return False
    return True


def build_reference_index_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        generation_type = normalize_generation_exercise_type(item["exercise_type"])
        rows.append(
            {
                "exercise_id": item["exercise_id"],
                "source_type": "Expert",
                "source_subtype": item.get("source_subtype", ""),
                "reference_source": infer_reference_source(item),
                "source_title": infer_source_title(item),
                "source_url": item.get("source_url", ""),
                "chapter_or_section": infer_chapter_or_section(item),
                "has_solution": bool(item.get("solution")),
                "has_code": bool(item.get("has_code")),
                "collected_at": item.get("created_at", ""),
                "title": item.get("title", ""),
                "topic": item["topic"],
                "difficulty": item["difficulty"],
                "reference_exercise_type_original": item["exercise_type"],
                "generation_exercise_type": generation_type,
                "instruction_text": item.get("instruction_text", ""),
                "starter_code": item.get("starter_code", ""),
                "expected_output": item.get("expected_output", ""),
                "constraints": item.get("constraints", []),
                "solution": item.get("solution", ""),
                "test_cases": item.get("test_cases", []),
                "learning_objectives": item.get("learning_objectives", []),
                "prerequisite_concepts": item.get("prerequisite_concepts", []),
                "keywords": item.get("keywords", []),
                "estimated_time_minutes": item.get("estimated_time_minutes", 0),
                "framework": item.get("framework", ""),
                "target_learner_level": item.get("target_learner_level", ""),
                "course_context": item.get("course_context", ""),
                "programming_language": item.get("programming_language", ""),
                "notes": item.get("notes", ""),
                "reference_payload": item,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-version", default="v1")
    parser.add_argument("--topic")
    parser.add_argument("--difficulty")
    parser.add_argument("--exercise-type")
    parser.add_argument("--reference-id")
    args = parser.parse_args()

    frozen_doc = load_json(FROZEN_MAIN)
    items = flatten_reference_items(frozen_doc)
    filtered_items = [
        item
        for item in items
        if matches_filters(
            item,
            topic=args.topic,
            difficulty=args.difficulty,
            exercise_type=args.exercise_type,
            reference_id=args.reference_id,
        )
    ]

    master_template_text = load_text(MASTER_TEMPLATE)
    prompt_records: list[dict[str, Any]] = []

    for item in filtered_items:
        generation_type = normalize_generation_exercise_type(item["exercise_type"])
        if generation_type not in SUPPORTED_GENERATION_TYPES:
            continue

        subtemplate_name = SUBTEMPLATE_NAME_MAP[generation_type]
        subtemplate_text = load_text(SUBTEMPLATE_DIR / subtemplate_name)
        prompt_records.append(
            build_prompt_record(
                reference_item=item,
                prompt_version=args.prompt_version,
                master_template_text=master_template_text,
                subtemplate_text=subtemplate_text,
                subtemplate_name=subtemplate_name,
            )
        )

    reference_index_rows = build_reference_index_rows(filtered_items)
    write_jsonl(prompt_records, OUT_JSONL)
    write_jsonl(reference_index_rows, REFERENCE_INDEX_OUT)

    print(f"Wrote {len(prompt_records)} prompt records -> {OUT_JSONL}")
    print(f"Wrote {len(reference_index_rows)} reference index rows -> {REFERENCE_INDEX_OUT}")


if __name__ == "__main__":
    main()
