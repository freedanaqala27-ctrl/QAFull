from __future__ import annotations

import ast
import importlib.util
import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

EVAL_RESULT_BEGIN = "---EVAL_RESULT_BEGIN---"
EVAL_RESULT_END = "---EVAL_RESULT_END---"
DEFAULT_MAX_MEMORY_BYTES = 512 * 1024 * 1024


def strip_markdown_fences(code: str) -> str:
    code = str(code or "").strip()
    code = re.sub(r"^```python\s*", "", code)
    code = re.sub(r"^```\s*", "", code)
    code = re.sub(r"\s*```$", "", code)
    return code.strip()


def ensure_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    items: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("code", "") or item.get("test", "") or item.get("assertion", "")).strip()
        else:
            text = str(item).strip()
        if text:
            items.append(text)
    return items


def ensure_surface_checks(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    checks: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, str):
            code = item.strip()
            check_type = "surface_check"
            name = ""
        elif isinstance(item, dict):
            code = str(item.get("code", "") or "").strip()
            check_type = str(item.get("type", "") or "surface_check").strip() or "surface_check"
            name = str(item.get("name", "") or item.get("description", "") or "").strip()
        else:
            continue
        if code:
            checks.append({"type": check_type, "code": code, "name": name})
    return checks


def detect_solution_format(payload: dict[str, Any]) -> str:
    explicit = str(payload.get("solution_format", "") or "").strip()
    if explicit:
        return explicit
    starter_code = strip_markdown_fences(payload.get("starter_code", ""))
    if starter_code and any(token in starter_code for token in ["TODO", "YOUR CODE HERE", "END OF YOUR CODE"]):
        return "replace_todo_region"
    return "full_code"


def indent_block(code: str, indent: str) -> str:
    code = textwrap.dedent(code).strip("\n")
    if not code:
        return ""
    return "\n".join(f"{indent}{line}" if line else "" for line in code.splitlines())


def replace_todo_region(
    starter_code: str,
    solution_code: str,
    start_marker: str = "",
    end_marker: str = "",
) -> tuple[str, bool]:
    lines = starter_code.splitlines()
    if not lines:
        return starter_code, False

    effective_start_marker = start_marker or "TODO"
    effective_end_marker = end_marker or "END OF YOUR CODE"

    start_idx = next((idx for idx, line in enumerate(lines) if effective_start_marker in line), -1)
    end_idx = next((idx for idx, line in enumerate(lines) if idx >= start_idx and effective_end_marker in line), -1)

    if start_idx < 0:
        return starter_code, False
    if end_idx < 0:
        base_indent = re.match(r"^\s*", lines[start_idx]).group(0)
        end_idx = start_idx
        for idx in range(start_idx + 1, len(lines)):
            stripped = lines[idx].strip()
            current_indent = re.match(r"^\s*", lines[idx]).group(0)
            if not stripped:
                end_idx = idx
                continue
            if (
                stripped.startswith("#")
                or stripped.startswith('"""')
                or stripped.startswith("'''")
                or any(token in stripped for token in ["TODO", "YOUR CODE HERE", "END OF YOUR CODE"])
            ) and len(current_indent) >= len(base_indent):
                end_idx = idx
                continue
            break

    indent = re.match(r"^\s*", lines[start_idx]).group(0)
    replacement_lines = indent_block(solution_code, indent).splitlines()
    merged = lines[:start_idx] + replacement_lines + lines[end_idx + 1 :]
    return "\n".join(merged).strip() + "\n", True


def required_packages_status(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    required_packages = ensure_string_list(payload.get("required_packages", []))
    missing = [name for name in required_packages if importlib.util.find_spec(name) is None]
    return not missing, missing


def assemble_solution_code(payload: dict[str, Any]) -> dict[str, Any]:
    starter_code = strip_markdown_fences(payload.get("starter_code", ""))
    solution_code = strip_markdown_fences(payload.get("solution", ""))
    setup_code = strip_markdown_fences(payload.get("setup_code", ""))
    solution_format = detect_solution_format(payload)

    result = {
        "assembled_code": "",
        "solution_format": solution_format,
        "assembly_status": "ok",
        "assembly_strategy": solution_format,
        "assembly_message": "",
    }

    if not solution_code:
        result["assembly_status"] = "missing_solution"
        result["assembly_message"] = "solution field is empty"
        return result

    if solution_format == "replace_todo_region" and starter_code:
        combined, replaced = replace_todo_region(
            starter_code,
            solution_code,
            str(payload.get("todo_start_marker", "") or ""),
            str(payload.get("todo_end_marker", "") or ""),
        )
        if replaced:
            body = combined
        else:
            body = solution_code
            result["assembly_strategy"] = "replace_todo_region_fallback_full_code"
            result["assembly_message"] = "TODO region not found; used solution as full code"
    elif solution_format == "standalone_function":
        body = solution_code
    else:
        body = solution_code

    pieces = [piece for piece in [setup_code, body] if piece.strip()]
    result["assembled_code"] = "\n\n".join(pieces).strip() + "\n"
    return result


def _build_resource_limiter(max_memory_bytes: int):
    if os.name != "posix" or max_memory_bytes <= 0:
        return None

    def _limit_resources() -> None:
        try:
            import resource

            for limit_name in ("RLIMIT_AS", "RLIMIT_DATA"):
                if hasattr(resource, limit_name):
                    limit = getattr(resource, limit_name)
                    resource.setrlimit(limit, (max_memory_bytes, max_memory_bytes))
        except Exception:
            return

    return _limit_resources


def run_subprocess_code(code: str, timeout_seconds: int, max_memory_bytes: int = DEFAULT_MAX_MEMORY_BYTES) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="exec_eval_") as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        script_path = tmp_dir / "candidate_exec.py"
        script_path.write_text(code, encoding="utf-8")
        try:
            preexec_fn = _build_resource_limiter(max_memory_bytes)
            proc = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=str(tmp_dir),
                preexec_fn=preexec_fn,
            )
            return {
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "timed_out": False,
                "resource_limits_requested": max_memory_bytes > 0,
                "resource_limits_applied": preexec_fn is not None,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "returncode": None,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "timed_out": True,
                "resource_limits_requested": max_memory_bytes > 0,
                "resource_limits_applied": preexec_fn is not None,
            }


def validate_code_artifact(code: str) -> dict[str, Any]:
    result = {
        "syntax_parse_ok": False,
        "compile_ok": False,
        "syntax_error_type": "",
        "syntax_error_message": "",
    }
    if not code.strip():
        result["syntax_error_type"] = "missing_code"
        result["syntax_error_message"] = "no code assembled"
        return result

    try:
        ast.parse(code)
        result["syntax_parse_ok"] = True
    except SyntaxError as exc:
        result["syntax_error_type"] = type(exc).__name__
        result["syntax_error_message"] = str(exc)
        return result

    with tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False) as handle:
        handle.write(code)
        tmp_path = handle.name

    try:
        py_compile.compile(tmp_path, doraise=True)
        result["compile_ok"] = True
    except Exception as exc:
        result["syntax_error_type"] = type(exc).__name__
        result["syntax_error_message"] = str(exc)

    return result


def build_test_harness(
    assembled_code: str,
    test_snippets: list[str],
    surface_checks: list[dict[str, str]],
) -> str:
    payload = {
        "assembled_code": assembled_code,
        "tests": test_snippets,
        "surface_checks": surface_checks,
    }
    return f"""
import json
import traceback

EVAL_RESULT_BEGIN = {json.dumps(EVAL_RESULT_BEGIN)}
EVAL_RESULT_END = {json.dumps(EVAL_RESULT_END)}

payload = {json.dumps(payload, ensure_ascii=False)}
assembled_code = payload["assembled_code"]
tests = payload["tests"]
surface_checks = payload["surface_checks"]
compiled_assembled_code = compile(assembled_code, "<assembled_code>", "exec")

summary = {{
    "exec_ok": False,
    "exec_error_type": "",
    "exec_error_message": "",
    "test_results": [],
    "surface_results": [],
}}

def emit_summary() -> None:
    print(EVAL_RESULT_BEGIN)
    print(json.dumps(summary, ensure_ascii=False))
    print(EVAL_RESULT_END)

def build_namespace():
    namespace = {{}}
    namespace["source_code"] = assembled_code
    exec(compiled_assembled_code, namespace, namespace)
    return namespace

try:
    build_namespace()
    summary["exec_ok"] = True
except Exception as exc:
    summary["exec_error_type"] = type(exc).__name__
    summary["exec_error_message"] = str(exc)
    emit_summary()
    raise SystemExit(0)

for snippet in tests:
    record = {{"code": snippet, "passed": False, "error_type": "", "error_message": ""}}
    try:
        namespace = build_namespace()
        exec(snippet, namespace, namespace)
        record["passed"] = True
    except Exception as exc:
        record["error_type"] = type(exc).__name__
        record["error_message"] = str(exc)
    summary["test_results"].append(record)

for check in surface_checks:
    record = {{
        "name": check.get("name", ""),
        "type": check.get("type", "surface_check"),
        "code": check.get("code", ""),
        "passed": False,
        "error_type": "",
        "error_message": "",
    }}
    try:
        namespace = build_namespace()
        exec(record["code"], namespace, namespace)
        record["passed"] = True
    except Exception as exc:
        record["error_type"] = type(exc).__name__
        record["error_message"] = str(exc)
    summary["surface_results"].append(record)

emit_summary()
""".strip()
