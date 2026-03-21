from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROMPT_RECORDS = PROJECT_ROOT / "data" / "processed" / "prompt_records.v1.jsonl"
OUT_JSONL = PROJECT_ROOT / "outputs" / "raw_generations" / "generations.raw.v1.jsonl"
SUMMARY_CSV = PROJECT_ROOT / "outputs" / "raw_generations" / "generation_summary.v1.csv"
MANIFEST_JSON = PROJECT_ROOT / "outputs" / "raw_generations" / "generation_manifest.v1.json"

ALLOWED_TOPICS = {"CNN", "RNN", "Transformer", "Optimization"}
ALLOWED_DIFFICULTIES = {
    "beginner",
    "beginner-intermediate",
    "intermediate",
    "intermediate-advanced",
    "advanced",
}
ALLOWED_GENERATION_TYPES = {
    "code completion",
    "model building",
    "model revision",
    "training-analysis",
}
REQUIRED_KEYS = {
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
    "learning_objectives",
    "prerequisite_concepts",
    "keywords",
    "estimated_time_minutes",
    "target_learner_level",
    "course_context",
    "notes",
}

PROVIDER_ALIASES = {
    "bailian": "bailian",
    "dashscope": "bailian",
    "aliyun": "bailian",
    "aliyun-bailian": "bailian",
    "qwen": "bailian",
    "mock": "mock",
}

TEST_CASE_OBJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string"},
        "description": {"type": "string"},
        "input": {"type": "string"},
        "expected_output": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["type", "description", "input", "expected_output", "notes"],
    "additionalProperties": False,
}

CANDIDATE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "topic": {"type": "string", "enum": sorted(ALLOWED_TOPICS)},
        "difficulty": {"type": "string", "enum": sorted(ALLOWED_DIFFICULTIES)},
        "exercise_type": {"type": "string", "enum": sorted(ALLOWED_GENERATION_TYPES)},
        "instruction_text": {"type": "string"},
        "programming_language": {"type": "string", "enum": ["Python"]},
        "framework": {"type": "string"},
        "has_code": {"type": "boolean"},
        "starter_code": {"type": "string"},
        "constraints": {"type": "array", "items": {"type": "string"}},
        "expected_output": {"type": "string"},
        "test_cases": {"type": "array", "items": TEST_CASE_OBJECT_SCHEMA},
        "solution": {"type": "string"},
        "learning_objectives": {"type": "array", "items": {"type": "string"}},
        "prerequisite_concepts": {"type": "array", "items": {"type": "string"}},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "estimated_time_minutes": {"type": "integer"},
        "target_learner_level": {"type": "string"},
        "course_context": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": sorted(REQUIRED_KEYS),
    "additionalProperties": False,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_id_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())


def build_candidate_id(reference_exercise_id: str, run_id: str, candidate_index: int) -> str:
    return f"GEN-{sanitize_id_part(reference_exercise_id)}-{sanitize_id_part(run_id)}-{candidate_index:02d}"


def build_prompt_excerpt(text: str, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def truncate_error(error: str, limit: int = 160) -> str:
    error = re.sub(r"\s+", " ", error or "").strip()
    if len(error) <= limit:
        return error
    return error[: limit - 3] + "..."


def iter_json_objects(raw_text: str):
    in_string = False
    escaped = False
    start_idx: int | None = None
    depth = 0

    for idx, char in enumerate(raw_text):
        if start_idx is None:
            if char == "{":
                start_idx = idx
                depth = 1
                in_string = False
                escaped = False
            continue

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                yield raw_text[start_idx : idx + 1]
                start_idx = None


def extract_json_object(raw_text: str) -> tuple[str | None, str]:
    raw_text = raw_text.strip()
    if not raw_text:
        return None, "json_not_found"

    for candidate in iter_json_objects(raw_text):
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            return candidate, "ok"

    return None, "json_not_found"


def normalize_test_cases(payload: dict[str, Any]) -> dict[str, Any]:
    test_cases = payload.get("test_cases", [])
    normalized: list[dict[str, Any]] = []
    if isinstance(test_cases, list):
        for tc in test_cases:
            if isinstance(tc, str):
                normalized.append(
                    {
                        "type": "inspection",
                        "description": tc,
                        "input": "",
                        "expected_output": "",
                        "notes": "",
                    }
                )
            elif isinstance(tc, dict):
                normalized.append(
                    {
                        "type": str(tc.get("type", "inspection")),
                        "description": str(tc.get("description", "")),
                        "input": str(tc.get("input", "")),
                        "expected_output": str(tc.get("expected_output", "")),
                        "notes": str(tc.get("notes", "")),
                    }
                )
    payload["test_cases"] = normalized
    payload.setdefault("solution", "")
    return payload


def validate_candidate_payload(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []

    missing = sorted(REQUIRED_KEYS - payload.keys())
    if missing:
        errors.append(f"missing_keys={missing}")

    if payload.get("topic") not in ALLOWED_TOPICS:
        errors.append(f"invalid_topic={payload.get('topic')}")
    if payload.get("difficulty") not in ALLOWED_DIFFICULTIES:
        errors.append(f"invalid_difficulty={payload.get('difficulty')}")
    if payload.get("exercise_type") not in ALLOWED_GENERATION_TYPES:
        errors.append(f"invalid_exercise_type={payload.get('exercise_type')}")
    if payload.get("programming_language") != "Python":
        errors.append("programming_language_must_be_Python")
    if not isinstance(payload.get("constraints", []), list):
        errors.append("constraints_must_be_list")
    if not isinstance(payload.get("learning_objectives", []), list):
        errors.append("learning_objectives_must_be_list")
    if not isinstance(payload.get("prerequisite_concepts", []), list):
        errors.append("prerequisite_concepts_must_be_list")
    if not isinstance(payload.get("keywords", []), list):
        errors.append("keywords_must_be_list")
    if not isinstance(payload.get("test_cases", []), list):
        errors.append("test_cases_must_be_list")
    if not isinstance(payload.get("has_code"), bool):
        errors.append("has_code_must_be_bool")
    if not isinstance(payload.get("estimated_time_minutes"), int):
        errors.append("estimated_time_minutes_must_be_int")

    return len(errors) == 0, errors


def normalize_provider_name(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[normalized]
    raise ValueError(f"Unsupported provider={provider!r}. Supported values: {sorted(PROVIDER_ALIASES)}")


def post_json(
    url: str,
    payload: dict[str, Any],
    timeout_seconds: int,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    max_retries = int(os.environ.get("BAILIAN_MAX_RETRIES", "4"))
    base_backoff_seconds = float(os.environ.get("BAILIAN_RETRY_BACKOFF_SECONDS", "2"))

    for attempt in range(1, max_retries + 1):
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in {408, 429, 500, 502, 503, 504} and attempt < max_retries:
                sleep_seconds = base_backoff_seconds * (2 ** (attempt - 1))
                print(f"HTTP {exc.code} from {url}; retrying in {sleep_seconds:.1f}s ({attempt}/{max_retries})")
                time.sleep(sleep_seconds)
                continue
            raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc
        except urllib.error.URLError as exc:
            if attempt < max_retries:
                sleep_seconds = base_backoff_seconds * (2 ** (attempt - 1))
                print(f"Network error from {url}; retrying in {sleep_seconds:.1f}s ({attempt}/{max_retries})")
                time.sleep(sleep_seconds)
                continue
            raise RuntimeError(f"Unable to reach {url}.") from exc

    raise RuntimeError(f"Unable to reach {url} after {max_retries} attempts.")


def get_env_api_key(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def extract_bailian_response_text(response: dict[str, Any]) -> str:
    choices = response.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            text_value = item.get("text")
            if isinstance(text_value, str):
                texts.append(text_value)
        return "\n".join(texts)
    return ""


def extract_bailian_usage(response: dict[str, Any]) -> dict[str, int]:
    usage = response.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens")
    if total_tokens is None:
        total_tokens = int(prompt_tokens or 0) + int(completion_tokens or 0)
    return {
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
        "total_tokens": int(total_tokens or 0),
    }


def call_bailian_generation_api(
    prompt_text: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    api_key = get_env_api_key("BAILIAN_API_KEY", "ALIYUN_BAILIAN_API_KEY", "DASHSCOPE_API_KEY")
    if not api_key:
        raise EnvironmentError("BAILIAN_API_KEY, ALIYUN_BAILIAN_API_KEY, or DASHSCOPE_API_KEY is not set.")

    base_url = os.environ.get("ALIYUN_BAILIAN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
    timeout_seconds = int(os.environ.get("ALIYUN_BAILIAN_TIMEOUT_SECONDS", "600"))
    schema_text = json.dumps(CANDIDATE_JSON_SCHEMA, ensure_ascii=False)
    grounded_prompt = (
        f"{prompt_text}\n\n"
        "Return exactly one JSON object that matches this JSON schema.\n"
        "Do not include markdown fences or any extra explanatory text.\n"
        f"JSON schema:\n{schema_text}\n"
    )
    response = post_json(
        f"{base_url}/chat/completions",
        {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You generate deep learning programming exercises. Always return exactly one JSON object.",
                },
                {"role": "user", "content": grounded_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout_seconds=timeout_seconds,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return {"text": extract_bailian_response_text(response), "usage": extract_bailian_usage(response)}


def call_mock_generation_api(prompt_record: dict[str, Any]) -> dict[str, Any]:
    topic = prompt_record.get("topic", "CNN")
    difficulty = prompt_record.get("difficulty", "intermediate")
    exercise_type = prompt_record.get("generation_exercise_type", "code completion")
    framework = prompt_record.get("framework", "PyTorch") or "PyTorch"
    learner_level = prompt_record.get("target_learner_level", difficulty)
    reference_id = prompt_record.get("reference_exercise_id", "REF-001")
    title_topic = topic.replace("Optimization", "Optimization")

    starter_code = (
        "def complete_exercise(input_tensor):\n"
        "    \"\"\"Complete the bounded task for this exercise.\"\"\"\n"
        "    # TODO: implement the required logic\n"
        "    return None\n"
    )
    solution = (
        "def complete_exercise(input_tensor):\n"
        "    \"\"\"Reference solution for the mock exercise.\"\"\"\n"
        "    return input_tensor\n"
    )
    payload = {
        "title": f"{title_topic} Mock Exercise for {reference_id}",
        "topic": topic,
        "difficulty": difficulty,
        "exercise_type": exercise_type,
        "instruction_text": (
            f"Complete a single bounded {topic} exercise aligned with {difficulty} difficulty. "
            "Fill in the TODO region and explain how the returned value should be checked."
        ),
        "programming_language": "Python",
        "framework": framework,
        "has_code": True,
        "starter_code": starter_code,
        "constraints": [
            "Keep the implementation self-contained.",
            "Solve the task using only the code scaffold and information included in the prompt.",
        ],
        "expected_output": "Return the completed function result and briefly state the validation criterion.",
        "test_cases": [
            {
                "type": "inspection",
                "description": "The function returns a non-None value.",
                "input": "input_tensor=[1,2,3]",
                "expected_output": "A value derived from input_tensor",
                "notes": "Sanity check only.",
            },
            {
                "type": "inspection",
                "description": "The solution keeps the function signature unchanged.",
                "input": "",
                "expected_output": "Function name and parameter list preserved",
                "notes": "",
            },
        ],
        "solution": solution,
        "learning_objectives": prompt_record.get("learning_objectives", []) or [f"Practice a bounded {topic} task."],
        "prerequisite_concepts": prompt_record.get("prerequisite_concepts", []) or [topic],
        "keywords": [topic, difficulty, exercise_type],
        "estimated_time_minutes": int(prompt_record.get("estimated_time_minutes", 20) or 20),
        "target_learner_level": learner_level,
        "course_context": prompt_record.get("course_context", f"Mock generation for {reference_id}"),
        "notes": "Generated by the local mock provider for pipeline debugging.",
    }
    raw_text = f"Here is the JSON you asked for:\n{json.dumps(payload, ensure_ascii=False)}\n"
    return {
        "text": raw_text,
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def call_generation_api(
    prompt_text: str,
    provider: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    prompt_record: dict[str, Any],
) -> dict[str, Any]:
    provider_name = normalize_provider_name(provider)
    if provider_name == "mock":
        return call_mock_generation_api(prompt_record)
    if provider_name == "bailian":
        return call_bailian_generation_api(
            prompt_text=prompt_text,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    raise ValueError(f"Unsupported normalized provider={provider_name!r}")


def matches_prompt_filters(
    prompt_record: dict[str, Any],
    topic: str | None,
    difficulty: str | None,
    exercise_type: str | None,
    prompt_id: str | None,
) -> bool:
    if topic and str(prompt_record.get("topic", "")).lower() != topic.lower():
        return False
    if difficulty and str(prompt_record.get("difficulty", "")).lower() != difficulty.lower():
        return False
    if exercise_type and str(prompt_record.get("generation_exercise_type", "")).lower() != exercise_type.lower():
        return False
    if prompt_id and str(prompt_record.get("prompt_id", "")).lower() != prompt_id.lower():
        return False
    return True


def build_generation_record_base(
    prompt_record: dict[str, Any],
    run_id: str,
    candidate_index: int,
    provider: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    generation_started_at: str,
    generation_finished_at: str,
    elapsed_ms: int,
) -> dict[str, Any]:
    candidate_id = build_candidate_id(prompt_record["reference_exercise_id"], run_id, candidate_index)
    prompt_text = prompt_record.get("generation_prompt") or prompt_record.get("rendered_prompt", "")
    return {
        "candidate_id": candidate_id,
        "generation_id": candidate_id,
        "run_id": run_id,
        "prompt_id": prompt_record["prompt_id"],
        "prompt_version": prompt_record.get("prompt_version", ""),
        "reference_exercise_id": prompt_record["reference_exercise_id"],
        "reference_exercise_type_original": prompt_record.get("reference_exercise_type_original", ""),
        "generation_exercise_type": prompt_record.get("generation_exercise_type", ""),
        "topic": prompt_record.get("topic", ""),
        "difficulty": prompt_record.get("difficulty", ""),
        "framework": prompt_record.get("framework", ""),
        "candidate_index": candidate_index,
        "provider": provider,
        "model_name": model_name,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "generation_started_at": generation_started_at,
        "generation_finished_at": generation_finished_at,
        "latency_ms": elapsed_ms,
        "generation_prompt_hash": prompt_record.get("prompt_text_hash", ""),
        "generation_prompt_excerpt": build_prompt_excerpt(prompt_text),
        "api_status": "not_started",
        "json_extract_status": "not_started",
        "schema_status": "not_started",
        "error_stage": "",
        "error_message_short": "",
        "schema_valid": False,
        "parse_status": "not_started",
        "validation_errors": [],
        "schema_errors": [],
        "raw_response_text": "",
        "extracted_json_text": "",
        "payload": None,
        "token_usage": {},
    }


def build_raw_generation_record(
    prompt_record: dict[str, Any],
    run_id: str,
    candidate_index: int,
    provider: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    api_response: dict[str, Any] | None,
    generation_started_at: str,
    generation_finished_at: str,
    elapsed_ms: int,
    error: str | None = None,
) -> dict[str, Any]:
    record = build_generation_record_base(
        prompt_record=prompt_record,
        run_id=run_id,
        candidate_index=candidate_index,
        provider=provider,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        generation_started_at=generation_started_at,
        generation_finished_at=generation_finished_at,
        elapsed_ms=elapsed_ms,
    )

    if error:
        record.update(
            {
                "api_status": "error",
                "json_extract_status": "skipped",
                "schema_status": "skipped",
                "error_stage": "api",
                "error_message_short": truncate_error(error),
                "parse_status": "api_error",
                "validation_errors": [error],
                "schema_errors": [error],
            }
        )
        return record

    api_response = api_response or {}
    raw_text = api_response.get("text", "")
    json_text, json_extract_status = extract_json_object(raw_text)
    record.update(
        {
            "api_status": "success",
            "raw_response_text": raw_text,
            "extracted_json_text": json_text or "",
            "json_extract_status": json_extract_status,
            "token_usage": api_response.get("usage", {}),
        }
    )

    if json_text is None:
        record.update(
            {
                "schema_status": "skipped",
                "error_stage": "json_extract",
                "error_message_short": "json_not_found",
                "parse_status": "json_not_found",
                "validation_errors": ["json_not_found"],
                "schema_errors": ["json_not_found"],
            }
        )
        return record

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        message = f"json_decode_error={exc}"
        record.update(
            {
                "schema_status": "skipped",
                "error_stage": "json_extract",
                "error_message_short": truncate_error(message),
                "parse_status": "invalid_json",
                "validation_errors": [message],
                "schema_errors": [message],
            }
        )
        return record

    payload = normalize_test_cases(payload)
    schema_valid, validation_errors = validate_candidate_payload(payload)
    record.update(
        {
            "payload": payload,
            "schema_valid": schema_valid,
            "schema_status": "valid" if schema_valid else "invalid",
            "parse_status": "ok" if schema_valid else "schema_invalid",
            "validation_errors": validation_errors,
            "schema_errors": validation_errors,
        }
    )
    if not schema_valid:
        record["error_stage"] = "schema"
        record["error_message_short"] = truncate_error("; ".join(validation_errors))
    return record


def summarize_generation_rows(
    rows: list[dict[str, Any]],
    provider: str,
    model_name: str,
    run_id: str,
    filters: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    total_prompts = len({row["prompt_id"] for row in rows})
    avg_latency_ms = round(sum(int(row.get("latency_ms", 0) or 0) for row in rows) / max(1, len(rows)), 2) if rows else 0.0
    summary_row = {
        "run_id": run_id,
        "provider": provider,
        "model": model_name,
        "total_prompts": total_prompts,
        "total_generations": len(rows),
        "api_success_count": sum(row.get("api_status") == "success" for row in rows),
        "api_error_count": sum(row.get("api_status") == "error" for row in rows),
        "json_extract_success_count": sum(row.get("json_extract_status") == "ok" for row in rows),
        "json_extract_fail_count": sum(row.get("json_extract_status") != "ok" for row in rows),
        "schema_valid_count": sum(bool(row.get("schema_valid")) for row in rows),
        "schema_invalid_count": sum(row.get("schema_status") == "invalid" for row in rows),
        "avg_latency_ms": avg_latency_ms,
    }
    manifest = {
        "run_id": run_id,
        "provider": provider,
        "model": model_name,
        "filters": filters,
        "summary": summary_row,
        "output_files": {
            "raw_generations": str(OUT_JSONL),
            "generation_summary": str(SUMMARY_CSV),
            "generation_manifest": str(MANIFEST_JSON),
        },
    }
    return [summary_row], manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--num-candidates", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=2200)
    parser.add_argument("--topic")
    parser.add_argument("--difficulty")
    parser.add_argument("--exercise-type")
    parser.add_argument("--prompt-id")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    prompt_records = read_jsonl(PROMPT_RECORDS)
    prompt_records = [
        row
        for row in prompt_records
        if matches_prompt_filters(
            row,
            topic=args.topic,
            difficulty=args.difficulty,
            exercise_type=args.exercise_type,
            prompt_id=args.prompt_id,
        )
    ]
    if args.limit > 0:
        prompt_records = prompt_records[: args.limit]

    all_rows: list[dict[str, Any]] = []
    for prompt_record in prompt_records:
        for candidate_index in range(1, args.num_candidates + 1):
            generation_started_at = utc_now_iso()
            start = time.perf_counter()
            api_response: dict[str, Any] | None = None
            error_message: str | None = None
            try:
                api_response = call_generation_api(
                    prompt_text=prompt_record.get("generation_prompt") or prompt_record["rendered_prompt"],
                    provider=args.provider,
                    model_name=args.model,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    prompt_record=prompt_record,
                )
            except Exception as exc:
                error_message = f"{type(exc).__name__}: {exc}"

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            generation_finished_at = utc_now_iso()
            all_rows.append(
                build_raw_generation_record(
                    prompt_record=prompt_record,
                    run_id=args.run_id,
                    candidate_index=candidate_index,
                    provider=args.provider,
                    model_name=args.model,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    api_response=api_response,
                    generation_started_at=generation_started_at,
                    generation_finished_at=generation_finished_at,
                    elapsed_ms=elapsed_ms,
                    error=error_message,
                )
            )

    append_jsonl(OUT_JSONL, all_rows)
    filters = {
        "topic": args.topic,
        "difficulty": args.difficulty,
        "exercise_type": args.exercise_type,
        "prompt_id": args.prompt_id,
        "limit": args.limit,
    }
    summary_rows, manifest = summarize_generation_rows(
        rows=all_rows,
        provider=args.provider,
        model_name=args.model,
        run_id=args.run_id,
        filters=filters,
    )
    write_csv(summary_rows, SUMMARY_CSV)
    write_json(manifest, MANIFEST_JSON)

    print(f"Appended {len(all_rows)} rows -> {OUT_JSONL}")
    print(f"Wrote generation summary -> {SUMMARY_CSV}")
    print(f"Wrote generation manifest -> {MANIFEST_JSON}")


if __name__ == "__main__":
    main()
