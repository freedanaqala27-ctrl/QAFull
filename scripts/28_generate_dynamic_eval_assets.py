from __future__ import annotations

import ast
import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from _shared_io import index_rows_by_key, read_jsonl_rows, write_json_doc, write_jsonl_rows

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
CURATED_DIR = RESULTS_DIR / "curated"
DEFAULT_FINAL_PAIRS = RESULTS_DIR / "final_pairs.v1.jsonl"
CURATED_FINAL_PAIRS = CURATED_DIR / "final_pairs.curated.v1.jsonl"
CURATED_REFERENCE_SOLUTIONS = CURATED_DIR / "reference_solutions.curated.v1.jsonl"
CURATED_EXECUTABLE_TESTS = CURATED_DIR / "executable_tests.curated.v1.jsonl"
CURATED_MANIFEST_PATH = CURATED_DIR / "dynamic_eval_assets.manifest.v1.json"

DEFAULT_MODEL = "qwen-plus"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 2200

ASSET_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "solution": {"type": "string"},
        "evaluation_mode": {"type": "string"},
        "entry_point": {"type": "string"},
        "solution_format": {"type": "string"},
        "setup_code": {"type": "string"},
        "todo_start_marker": {"type": "string"},
        "todo_end_marker": {"type": "string"},
        "timeout_seconds": {"type": "integer"},
        "required_packages": {"type": "array", "items": {"type": "string"}},
        "public_tests_py": {"type": "array", "items": {"type": "string"}},
        "hidden_tests_py": {"type": "array", "items": {"type": "string"}},
        "surface_checks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "name": {"type": "string"},
                    "code": {"type": "string"},
                },
                "required": ["type", "name", "code"],
                "additionalProperties": False,
            },
        },
        "reference_solution_authority": {"type": "string"},
    },
    "required": [
        "solution",
        "evaluation_mode",
        "entry_point",
        "solution_format",
        "setup_code",
        "timeout_seconds",
        "required_packages",
        "public_tests_py",
        "hidden_tests_py",
        "surface_checks",
        "reference_solution_authority",
    ],
    "additionalProperties": False,
}


def safe_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def ensure_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    rows: list[str] = []
    for item in value:
        if isinstance(item, dict):
            text = str(item.get("code", "") or item.get("description", "") or "").strip()
        else:
            text = str(item or "").strip()
        if text:
            rows.append(text)
    return rows


def ensure_surface_checks(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    checks: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            code = str(item.get("code", "") or "").strip()
            if not code:
                continue
            checks.append(
                {
                    "type": str(item.get("type", "surface_check") or "surface_check"),
                    "name": str(item.get("name", "") or item.get("description", "") or "surface_check"),
                    "code": code,
                }
            )
        elif isinstance(item, str) and item.strip():
            checks.append({"type": "surface_check", "name": "surface_check", "code": item.strip()})
    return checks


def post_json(url: str, payload: dict[str, Any], timeout_seconds: int, headers: dict[str, str] | None = None) -> dict[str, Any]:
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
                time.sleep(base_backoff_seconds * (2 ** (attempt - 1)))
                continue
            raise RuntimeError(f"HTTP {exc.code} from {url}: {body}") from exc
        except urllib.error.URLError as exc:
            if attempt < max_retries:
                time.sleep(base_backoff_seconds * (2 ** (attempt - 1)))
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
        parts: list[str] = []
        for item in content:
            text_value = item.get("text")
            if isinstance(text_value, str):
                parts.append(text_value)
        return "\n".join(parts)
    return ""


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


def extract_json_object(raw_text: str) -> dict[str, Any] | None:
    raw_text = raw_text.strip()
    if not raw_text:
        return None
    for candidate in iter_json_objects(raw_text):
        try:
            loaded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            return loaded
    return None


def call_bailian_asset_api(prompt_text: str, model_name: str, temperature: float, max_tokens: int) -> dict[str, Any]:
    api_key = get_env_api_key("BAILIAN_API_KEY", "ALIYUN_BAILIAN_API_KEY", "DASHSCOPE_API_KEY")
    if not api_key:
        raise EnvironmentError("BAILIAN_API_KEY, ALIYUN_BAILIAN_API_KEY, or DASHSCOPE_API_KEY is not set.")
    base_url = os.environ.get("ALIYUN_BAILIAN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
    timeout_seconds = int(os.environ.get("ALIYUN_BAILIAN_TIMEOUT_SECONDS", "600"))
    schema_text = json.dumps(ASSET_JSON_SCHEMA, ensure_ascii=False)
    grounded_prompt = (
        f"{prompt_text}\n\n"
        "Return exactly one JSON object that matches this schema.\n"
        "Do not include markdown fences or extra commentary.\n"
        f"JSON schema:\n{schema_text}\n"
    )
    response = post_json(
        f"{base_url}/chat/completions",
        {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You generate executable evaluation assets for deep learning programming exercises. Always return exactly one JSON object.",
                },
                {"role": "user", "content": grounded_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout_seconds=timeout_seconds,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    text = extract_bailian_response_text(response)
    loaded = extract_json_object(text)
    if not loaded:
        raise RuntimeError("Asset generation response did not contain a valid JSON object.")
    return loaded


def infer_entry_point(payload: dict[str, Any]) -> str:
    explicit = normalize_space(payload.get("entry_point", ""))
    if explicit:
        return explicit
    for source in [payload.get("solution", ""), payload.get("starter_code", "")]:
        code = str(source or "")
        if not code.strip():
            continue
        try:
            tree = ast.parse(code)
        except Exception:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                return node.name
    return ""


def infer_eval_mode(payload: dict[str, Any], entry_point: str) -> str:
    explicit = normalize_space(payload.get("evaluation_mode", ""))
    if explicit:
        return explicit
    exercise_type = normalize_space(payload.get("exercise_type", "")).lower()
    if exercise_type == "model revision":
        return "model_revision"
    if exercise_type == "model building":
        return "model_building"
    if exercise_type in {"training-analysis", "training analysis"}:
        return "training_analysis"
    if exercise_type == "concept-to-code":
        return "concept_to_code"
    if entry_point:
        if entry_point[:1].isupper():
            return "class_implementation"
        return "function_completion"
    return "full_code"


def generic_surface_check(entry_point: str, eval_mode: str) -> list[dict[str, str]]:
    if not entry_point:
        return []
    if eval_mode in {"class_implementation", "model_building", "model_revision", "training_analysis"} or entry_point[:1].isupper():
        code = f"assert isinstance({entry_point}, type)"
    else:
        code = f"assert callable({entry_point})"
    return [{"type": "api_check", "name": "entry_point_exists", "code": code}]


def build_existing_solution_row(exercise_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    solution = str(payload.get("solution", "") or "").strip()
    if not solution:
        return None
    entry_point = infer_entry_point(payload)
    return {
        "exercise_id": exercise_id,
        "evaluation_mode": infer_eval_mode(payload, entry_point),
        "entry_point": entry_point,
        "solution": solution,
        "solution_format": normalize_space(payload.get("solution_format", "")) or "full_code",
        "setup_code": str(payload.get("setup_code", "") or ""),
        "todo_start_marker": str(payload.get("todo_start_marker", "") or ""),
        "todo_end_marker": str(payload.get("todo_end_marker", "") or ""),
        "timeout_seconds": safe_int(payload.get("timeout_seconds"), 10),
        "required_packages": ensure_string_list(payload.get("required_packages", [])),
        "reference_solution_authority": normalize_space(payload.get("reference_solution_authority", "")) or "payload_provided",
        "overlay_status": "dynamic_existing_payload",
    }


def build_existing_tests_row(exercise_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    public_tests = ensure_string_list(payload.get("public_tests_py", []))
    hidden_tests = ensure_string_list(payload.get("hidden_tests_py", []))
    surface_checks = ensure_surface_checks(payload.get("surface_checks", []))
    entry_point = infer_entry_point(payload)
    eval_mode = infer_eval_mode(payload, entry_point)
    if not public_tests and not hidden_tests and not surface_checks:
        surface_checks = generic_surface_check(entry_point, eval_mode)
    if not public_tests and not hidden_tests and not surface_checks:
        return None
    return {
        "exercise_id": exercise_id,
        "public_tests_py": public_tests,
        "hidden_tests_py": hidden_tests,
        "surface_checks": surface_checks,
        "overlay_status": "dynamic_existing_payload",
    }


def build_asset_prompt(exercise_id: str, payload: dict[str, Any]) -> str:
    prompt_doc = {
        "exercise_id": exercise_id,
        "title": payload.get("title", ""),
        "topic": payload.get("topic", ""),
        "difficulty": payload.get("difficulty", ""),
        "exercise_type": payload.get("exercise_type", ""),
        "framework": payload.get("framework", ""),
        "instruction_text": payload.get("instruction_text", ""),
        "starter_code": payload.get("starter_code", ""),
        "expected_output": payload.get("expected_output", ""),
        "constraints": payload.get("constraints", []),
        "test_cases": payload.get("test_cases", []),
        "learning_objectives": payload.get("learning_objectives", []),
        "prerequisite_concepts": payload.get("prerequisite_concepts", []),
        "keywords": payload.get("keywords", []),
    }
    return (
        "Generate executable evaluation assets for this deep learning programming exercise.\n"
        "Requirements:\n"
        "1. Provide a correct reference solution as Python code.\n"
        "2. Provide public tests, hidden tests, and surface checks that can run in the current lightweight evaluation harness.\n"
        "3. Prefer small deterministic tests.\n"
        "4. Use only packages explicitly required by the exercise when possible.\n"
        "5. If the task is open-ended, provide at least executable API/surface checks that verify the core object or function exists.\n"
        "6. entry_point must be the callable or class name used by the tests.\n"
        "Exercise payload:\n"
        f"{json.dumps(prompt_doc, ensure_ascii=False, indent=2)}"
    )


def build_llm_rows(exercise_id: str, payload: dict[str, Any], model_name: str, temperature: float, max_tokens: int) -> tuple[dict[str, Any], dict[str, Any]]:
    generated = call_bailian_asset_api(build_asset_prompt(exercise_id, payload), model_name, temperature, max_tokens)
    entry_point = normalize_space(generated.get("entry_point", "")) or infer_entry_point(payload)
    evaluation_mode = normalize_space(generated.get("evaluation_mode", "")) or infer_eval_mode(payload, entry_point)
    solution = str(generated.get("solution", "") or "").strip()
    if not solution:
        raise RuntimeError(f"Generated asset bundle for {exercise_id} did not include a usable solution.")

    solution_row = {
        "exercise_id": exercise_id,
        "evaluation_mode": evaluation_mode,
        "entry_point": entry_point,
        "solution": solution,
        "solution_format": normalize_space(generated.get("solution_format", "")) or "full_code",
        "setup_code": str(generated.get("setup_code", "") or ""),
        "todo_start_marker": str(generated.get("todo_start_marker", "") or ""),
        "todo_end_marker": str(generated.get("todo_end_marker", "") or ""),
        "timeout_seconds": safe_int(generated.get("timeout_seconds"), 10),
        "required_packages": ensure_string_list(generated.get("required_packages", [])),
        "reference_solution_authority": normalize_space(generated.get("reference_solution_authority", "")) or "llm_generated_auto_eval_assets",
        "overlay_status": "dynamic_llm_generated",
    }

    surface_checks = ensure_surface_checks(generated.get("surface_checks", []))
    if not surface_checks:
        surface_checks = generic_surface_check(entry_point, evaluation_mode)
    tests_row = {
        "exercise_id": exercise_id,
        "public_tests_py": ensure_string_list(generated.get("public_tests_py", [])),
        "hidden_tests_py": ensure_string_list(generated.get("hidden_tests_py", [])),
        "surface_checks": surface_checks,
        "overlay_status": "dynamic_llm_generated",
    }

    if not tests_row["public_tests_py"] and not tests_row["hidden_tests_py"] and not tests_row["surface_checks"]:
        raise RuntimeError(f"Generated asset bundle for {exercise_id} did not include executable tests or surface checks.")

    return solution_row, tests_row


def upsert_row(index: dict[str, dict[str, Any]], row: dict[str, Any] | None) -> None:
    if row and row.get("exercise_id"):
        index[str(row["exercise_id"])] = row


def process_payload(
    exercise_id: str,
    payload: dict[str, Any],
    solution_index: dict[str, dict[str, Any]],
    tests_index: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
    model_name: str,
    temperature: float,
    max_tokens: int,
) -> None:
    if exercise_id in solution_index and exercise_id in tests_index:
        manifest["existing_hits"] += 1
        return

    existing_solution = build_existing_solution_row(exercise_id, payload)
    existing_tests = build_existing_tests_row(exercise_id, payload)

    if existing_solution:
        upsert_row(solution_index, existing_solution)
        manifest["payload_solution_rows"] += 1
    if existing_tests:
        upsert_row(tests_index, existing_tests)
        manifest["payload_test_rows"] += 1
    if existing_solution and existing_tests:
        manifest["payload_derived_complete"] += 1
        return

    llm_solution, llm_tests = build_llm_rows(exercise_id, payload, model_name, temperature, max_tokens)
    if not existing_solution:
        upsert_row(solution_index, llm_solution)
        manifest["llm_solution_rows"] += 1
    if not existing_tests:
        upsert_row(tests_index, llm_tests)
        manifest["llm_test_rows"] += 1
    manifest["llm_generated_exercises"] += 1


def _sorted_rows(index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [index[key] for key in sorted(index.keys())]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate dynamic executable evaluation assets for finalized pairs.")
    parser.add_argument("--pairs-jsonl", default="")
    parser.add_argument("--reference-solutions-jsonl", default=str(CURATED_REFERENCE_SOLUTIONS))
    parser.add_argument("--executable-tests-jsonl", default=str(CURATED_EXECUTABLE_TESTS))
    parser.add_argument("--manifest-output", default=str(CURATED_MANIFEST_PATH))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args()

    pairs_path = Path(args.pairs_jsonl) if args.pairs_jsonl else CURATED_FINAL_PAIRS
    pair_rows = read_jsonl_rows(pairs_path)
    if not pair_rows and pairs_path == CURATED_FINAL_PAIRS:
        pair_rows = read_jsonl_rows(DEFAULT_FINAL_PAIRS)
        pairs_path = DEFAULT_FINAL_PAIRS

    solution_path = Path(args.reference_solutions_jsonl)
    tests_path = Path(args.executable_tests_jsonl)
    manifest_path = Path(args.manifest_output)

    solution_index = index_rows_by_key(read_jsonl_rows(solution_path), "exercise_id")
    tests_index = index_rows_by_key(read_jsonl_rows(tests_path), "exercise_id")

    manifest = {
        "num_pairs": len(pair_rows),
        "num_exercises_seen": 0,
        "existing_hits": 0,
        "payload_derived_complete": 0,
        "payload_solution_rows": 0,
        "payload_test_rows": 0,
        "llm_generated_exercises": 0,
        "llm_solution_rows": 0,
        "llm_test_rows": 0,
        "pair_source": str(pairs_path),
        "model_name": args.model,
    }

    seen: set[str] = set()
    for pair in pair_rows:
        for exercise_id_key, payload_key in (("reference_exercise_id", "reference_payload"), ("ai_exercise_id", "ai_payload")):
            exercise_id = str(pair.get(exercise_id_key, "") or "").strip()
            payload = pair.get(payload_key, {}) if isinstance(pair.get(payload_key), dict) else {}
            if not exercise_id or exercise_id in seen:
                continue
            seen.add(exercise_id)
            manifest["num_exercises_seen"] += 1
            process_payload(exercise_id, payload, solution_index, tests_index, manifest, args.model, args.temperature, args.max_tokens)

    write_jsonl_rows(_sorted_rows(solution_index), solution_path)
    write_jsonl_rows(_sorted_rows(tests_index), tests_path)
    write_json_doc(manifest, manifest_path)
    print(f"Dynamic eval assets written -> {solution_path}")
    print(f"Dynamic executable tests written -> {tests_path}")
    print(f"Dynamic asset manifest -> {manifest_path}")


if __name__ == "__main__":
    main()