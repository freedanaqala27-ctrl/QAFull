from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import py_compile
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FINAL_PAIRS = PROJECT_ROOT / "results" / "final_pairs.v1.jsonl"
EXERCISE_OUT_JSONL = PROJECT_ROOT / "results" / "exercise_metrics.v1.jsonl"
EXERCISE_OUT_CSV = PROJECT_ROOT / "results" / "exercise_metrics.v1.csv"
PAIR_OUT_JSONL = PROJECT_ROOT / "results" / "pair_similarity_metrics.v1.jsonl"
PAIR_OUT_CSV = PROJECT_ROOT / "results" / "pair_similarity_metrics.v1.csv"
METRICS_MANIFEST = PROJECT_ROOT / "results" / "metrics_manifest.v1.json"
CURATED_DIR = PROJECT_ROOT / "results" / "curated"
CURATED_FINAL_PAIRS = CURATED_DIR / "final_pairs.curated.v1.jsonl"
CURATED_EXERCISE_OUT_JSONL = CURATED_DIR / "exercise_metrics.curated.v1.jsonl"
CURATED_EXERCISE_OUT_CSV = CURATED_DIR / "exercise_metrics.curated.v1.csv"
CURATED_PAIR_OUT_JSONL = CURATED_DIR / "pair_similarity_metrics.curated.v1.jsonl"
CURATED_PAIR_OUT_CSV = CURATED_DIR / "pair_similarity_metrics.curated.v1.csv"
CURATED_METRICS_MANIFEST = CURATED_DIR / "metrics_manifest.curated.v1.json"

NAN = float("nan")
ENABLE_HEAVY_METRICS = False

TECHNICAL_TERM_LEXICON = {
    "CNN": [
        "convolution",
        "kernel",
        "filter",
        "stride",
        "padding",
        "pooling",
        "feature map",
        "batch normalization",
        "channel",
        "receptive field",
    ],
    "RNN": [
        "sequence",
        "recurrent",
        "hidden state",
        "cell state",
        "lstm",
        "gru",
        "embedding",
        "teacher forcing",
        "time step",
        "vocabulary",
    ],
    "Transformer": [
        "attention",
        "self-attention",
        "multi-head attention",
        "query",
        "key",
        "value",
        "positional encoding",
        "causal mask",
        "feed-forward network",
        "layer normalization",
    ],
    "Optimization": [
        "optimizer",
        "gradient",
        "learning rate",
        "weight decay",
        "regularization",
        "early stopping",
        "momentum",
        "scheduler",
        "validation loss",
        "convergence",
    ],
}


def optional_import(name: str):
    try:
        return __import__(name, fromlist=["*"])
    except Exception:
        return None


textstat = optional_import("textstat")
bert_score_mod = optional_import("bert_score")
rouge_score_mod = optional_import("rouge_score")
nltk = optional_import("nltk")
radon_complexity = optional_import("radon.complexity")
radon_metrics = optional_import("radon.metrics")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def flatten_dict(d: dict[str, Any], parent_key: str = "") -> dict[str, Any]:
    items: dict[str, Any] = {}
    for key, value in d.items():
        new_key = f"{parent_key}.{key}" if parent_key else key
        if isinstance(value, dict):
            items.update(flatten_dict(value, new_key))
        else:
            items[new_key] = value
    return items


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=True) + "\n")


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        return
    flat_rows = [flatten_dict(row) for row in rows]
    fieldnames = sorted({key for row in flat_rows for key in row.keys()})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_rows)


def write_json(doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2, allow_nan=True)


def touch_empty_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def token_split(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9_-]*", text.lower())


def sentence_split(text: str) -> list[str]:
    text = normalize_space(text)
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def safe_round(value: float | int | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return value
    return round(float(value), digits)


def nan_or_none(value: float | int | None) -> float | None:
    return NAN if value is None else value


def build_text_views(payload: dict[str, Any]) -> dict[str, str]:
    instruction_only = normalize_space(payload.get("instruction_text", ""))
    pedagogical_text = normalize_space(
        "\n".join(
            [
                payload.get("instruction_text", ""),
                "\n".join(payload.get("learning_objectives", [])),
                "\n".join(payload.get("prerequisite_concepts", [])),
                "\n".join(payload.get("constraints", [])),
                payload.get("expected_output", ""),
            ]
        )
    )
    full_text = normalize_space(
        "\n".join(
            [
                pedagogical_text,
                payload.get("starter_code", ""),
                payload.get("course_context", ""),
            ]
        )
    )
    return {
        "instruction_only": instruction_only,
        "pedagogical_text": pedagogical_text,
        "full_text": full_text,
    }


def compute_readability_metrics(text: str) -> dict[str, float]:
    if not textstat or not text.strip():
        return {
            "flesch_reading_ease": NAN,
            "flesch_kincaid_grade": NAN,
        }
    try:
        return {
            "flesch_reading_ease": safe_round(textstat.flesch_reading_ease(text)),
            "flesch_kincaid_grade": safe_round(textstat.flesch_kincaid_grade(text)),
        }
    except Exception:
        return {
            "flesch_reading_ease": NAN,
            "flesch_kincaid_grade": NAN,
        }


def compute_sentence_stats(text: str) -> dict[str, float]:
    sentences = sentence_split(text)
    if not sentences:
        return {
            "avg_sentence_length": NAN,
            "var_sentence_length": NAN,
            "max_sentence_length": NAN,
        }
    lengths = [len(token_split(sentence)) for sentence in sentences if token_split(sentence)]
    if not lengths:
        return {
            "avg_sentence_length": NAN,
            "var_sentence_length": NAN,
            "max_sentence_length": NAN,
        }
    avg_value = sum(lengths) / len(lengths)
    var_value = sum((length - avg_value) ** 2 for length in lengths) / len(lengths)
    return {
        "avg_sentence_length": safe_round(avg_value),
        "var_sentence_length": safe_round(var_value),
        "max_sentence_length": safe_round(max(lengths)),
    }


def compute_instruction_completeness_ratio(payload: dict[str, Any]) -> dict[str, Any]:
    instruction_text = normalize_space(payload.get("instruction_text", "")).lower()
    expected_output = normalize_space(payload.get("expected_output", "")).lower()
    constraints = payload.get("constraints", [])
    prereq = payload.get("prerequisite_concepts", [])

    artifact_patterns = [r"\bsubmit\b", r"\breturn\b", r"\bprovide\b", r"\bplot\b", r"\btable\b", r"\bexplanation\b"]
    success_patterns = [r"\bsuccess\b", r"\bcorrect\b", r"\bshould\b", r"\bmust\b", r"\bpass\b", r"\bexpected\b"]
    checks = {
        "instruction_has_task_goal": bool(payload.get("title")) and bool(payload.get("instruction_text")),
        "instruction_has_io_spec": bool(payload.get("expected_output")) or len(payload.get("test_cases", [])) > 0,
        "instruction_has_constraints": len(constraints) > 0,
        "instruction_has_eval_criteria": bool(re.search("|".join(success_patterns), instruction_text + " " + expected_output))
        or len(payload.get("test_cases", [])) > 0,
        "instruction_has_background_knowledge": len(prereq) > 0,
        "instruction_has_submission_format": bool(re.search("|".join(artifact_patterns), instruction_text + " " + expected_output)),
    }
    ratio = round(sum(bool(value) for value in checks.values()) / len(checks), 4)
    return {**checks, "instruction_completeness_ratio": ratio}


def compute_structure_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "title_present": bool(normalize_space(payload.get("title", ""))),
        "task_description_present": bool(normalize_space(payload.get("instruction_text", ""))),
        "io_spec_present": bool(normalize_space(payload.get("expected_output", ""))) or len(payload.get("test_cases", [])) > 0,
        "constraints_present": len(payload.get("constraints", [])) > 0,
        "starter_code_or_env_present": bool(normalize_space(payload.get("starter_code", ""))) or bool(normalize_space(payload.get("framework", ""))),
        "expected_goal_present": bool(normalize_space(payload.get("expected_output", ""))) or len(payload.get("learning_objectives", [])) > 0,
        "test_cases_present": len(payload.get("test_cases", [])) > 0,
        "solution_or_hint_present": bool(normalize_space(payload.get("solution", ""))) or bool(normalize_space(payload.get("notes", ""))),
    }
    weights = {
        "title_present": 1.0,
        "task_description_present": 1.5,
        "io_spec_present": 1.2,
        "constraints_present": 1.0,
        "starter_code_or_env_present": 1.0,
        "expected_goal_present": 1.0,
        "test_cases_present": 1.1,
        "solution_or_hint_present": 1.2,
    }
    total_weight = sum(weights.values())
    weighted_sum = sum(weights[key] for key, value in checks.items() if value)
    return {
        **checks,
        "structure_completeness_ratio": round(sum(bool(value) for value in checks.values()) / len(checks), 4),
        "structure_score_weighted": round(weighted_sum / total_weight, 4),
    }


def compute_technical_term_density(topic: str, text: str) -> float:
    terms = TECHNICAL_TERM_LEXICON.get(topic, [])
    tokens = token_split(text)
    if not terms or not tokens:
        return 0.0
    normalized_text = text.lower()
    match_count = 0
    for term in terms:
        pattern = rf"(?<!\w){re.escape(term.lower())}(?!\w)"
        if re.search(pattern, normalized_text):
            match_count += 1
    return round(match_count / max(1, len(tokens)), 4)


def compute_topic_coherence_score(topic: str, text: str) -> float:
    terms = TECHNICAL_TERM_LEXICON.get(topic, [])
    if not terms:
        return 0.0
    normalized_text = text.lower()
    matched = 0
    for term in terms:
        pattern = rf"(?<!\w){re.escape(term.lower())}(?!\w)"
        if re.search(pattern, normalized_text):
            matched += 1
    return round(matched / len(terms), 4)


def strip_markdown_fences(code: str) -> str:
    code = code.strip()
    code = re.sub(r"^```python\s*", "", code)
    code = re.sub(r"^```\s*", "", code)
    code = re.sub(r"\s*```$", "", code)
    return code.strip()


def run_ruff_metrics(py_file: str) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["ruff", "check", py_file, "--output-format", "json"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return {
            "ruff_error_count": NAN,
            "ruff_rule_ids": [],
        }

    if not proc.stdout.strip():
        return {
            "ruff_error_count": 0,
            "ruff_rule_ids": [],
        }

    try:
        rows = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "ruff_error_count": NAN,
            "ruff_rule_ids": [],
        }

    return {
        "ruff_error_count": len(rows),
        "ruff_rule_ids": sorted({row.get("code", "") for row in rows if row.get("code")}),
    }


def run_pylint_metrics(py_file: str) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["pylint", py_file, "--output-format=json"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return {
            "pylint_error_count": NAN,
            "pylint_warning_count": NAN,
            "pylint_symbols": [],
        }

    if not proc.stdout.strip():
        return {
            "pylint_error_count": 0,
            "pylint_warning_count": 0,
            "pylint_symbols": [],
        }

    try:
        rows = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "pylint_error_count": NAN,
            "pylint_warning_count": NAN,
            "pylint_symbols": [],
        }

    if not isinstance(rows, list):
        rows = rows.get("messages", []) if isinstance(rows, dict) else []

    error_count = sum(1 for row in rows if str(row.get("type", "")).lower() in {"error", "fatal"})
    warning_count = sum(
        1 for row in rows if str(row.get("type", "")).lower() in {"warning", "convention", "refactor", "info"}
    )
    return {
        "pylint_error_count": error_count,
        "pylint_warning_count": warning_count,
        "pylint_symbols": sorted({row.get("symbol", "") for row in rows if row.get("symbol")}),
    }


def analyze_code_snippet(code: str, prefix: str) -> dict[str, Any]:
    result = {
        f"{prefix}_syntax_parse_ok": NAN,
        f"{prefix}_static_analysis_ok": NAN,
        f"{prefix}_loc_total": NAN,
        f"{prefix}_function_count": NAN,
        f"{prefix}_max_function_loc": NAN,
        f"{prefix}_avg_function_loc": NAN,
        f"{prefix}_comment_line_ratio": NAN,
        f"{prefix}_docstring_count": NAN,
        f"{prefix}_has_docstring_flag": NAN,
        f"{prefix}_mccabe_max": NAN,
        f"{prefix}_mi": NAN,
        f"{prefix}_ruff_error_count": NAN,
        f"{prefix}_pylint_warning_count": NAN,
        f"{prefix}_long_function_flag": NAN,
        f"{prefix}_naming_violation_flag": NAN,
    }

    code = strip_markdown_fences(code)
    if not code:
        return result

    lines = code.splitlines()
    nonempty_lines = [line for line in lines if line.strip()]
    comment_lines = [line for line in lines if line.strip().startswith("#")]
    result[f"{prefix}_loc_total"] = len(nonempty_lines)
    result[f"{prefix}_comment_line_ratio"] = safe_round(len(comment_lines) / max(1, len(nonempty_lines)))

    try:
        tree = ast.parse(code)
        result[f"{prefix}_syntax_parse_ok"] = True
        function_nodes = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        function_lengths = []
        for node in function_nodes:
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", start)
            if start is not None and end is not None:
                function_lengths.append(end - start + 1)
        result[f"{prefix}_function_count"] = len(function_nodes)
        result[f"{prefix}_max_function_loc"] = max(function_lengths) if function_lengths else 0
        result[f"{prefix}_avg_function_loc"] = safe_round(sum(function_lengths) / len(function_lengths)) if function_lengths else 0.0

        docstring_count = 0
        if ast.get_docstring(tree):
            docstring_count += 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and ast.get_docstring(node):
                docstring_count += 1
        result[f"{prefix}_docstring_count"] = docstring_count
        result[f"{prefix}_has_docstring_flag"] = docstring_count > 0
    except Exception:
        result[f"{prefix}_syntax_parse_ok"] = False
        result[f"{prefix}_static_analysis_ok"] = False
        return result

    if radon_complexity:
        try:
            from radon.complexity import cc_visit

            blocks = cc_visit(code)
            complexities = [block.complexity for block in blocks]
            if complexities:
                result[f"{prefix}_mccabe_max"] = max(complexities)
                result[f"{prefix}_long_function_flag"] = max(complexities) >= 10
        except Exception:
            pass

    if radon_metrics:
        try:
            from radon.metrics import mi_visit

            result[f"{prefix}_mi"] = safe_round(mi_visit(code, multi=True))
        except Exception:
            pass

    with tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        py_compile.compile(tmp_path, doraise=True)
    except Exception:
        result[f"{prefix}_syntax_parse_ok"] = False
        result[f"{prefix}_static_analysis_ok"] = False
        return result

    ruff_metrics = run_ruff_metrics(tmp_path)
    pylint_metrics = run_pylint_metrics(tmp_path)
    result[f"{prefix}_ruff_error_count"] = ruff_metrics["ruff_error_count"]
    result[f"{prefix}_pylint_warning_count"] = pylint_metrics["pylint_warning_count"]
    ruff_rule_ids = ruff_metrics.get("ruff_rule_ids", [])
    pylint_symbols = pylint_metrics.get("pylint_symbols", [])
    result[f"{prefix}_naming_violation_flag"] = (
        any(str(rule_id).startswith("N") for rule_id in ruff_rule_ids) or "invalid-name" in pylint_symbols
    )

    static_checks: list[bool] = [True]
    ruff_count = result[f"{prefix}_ruff_error_count"]
    pylint_count = result[f"{prefix}_pylint_warning_count"]
    if not (isinstance(ruff_count, float) and math.isnan(ruff_count)):
        static_checks.append(float(ruff_count) == 0.0)
    if not (isinstance(pylint_count, float) and math.isnan(pylint_count)):
        static_checks.append(float(pylint_count) == 0.0)
    result[f"{prefix}_static_analysis_ok"] = all(static_checks)
    return result


def compute_code_quality_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    starter_metrics = analyze_code_snippet(payload.get("starter_code", ""), "starter_code")
    solution_metrics = analyze_code_snippet(payload.get("solution", ""), "solution_code")
    return {**starter_metrics, **solution_metrics}


def tfidf_cosine(text_a: str, text_b: str) -> float:
    text_a = normalize_space(text_a)
    text_b = normalize_space(text_b)
    if not text_a or not text_b:
        return 0.0
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), lowercase=True)
    matrix = vectorizer.fit_transform([text_a, text_b])
    return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])


def compute_rouge_l(reference_text: str, candidate_text: str) -> float:
    if not rouge_score_mod:
        return NAN
    try:
        from rouge_score import rouge_scorer

        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        return safe_round(scorer.score(reference_text, candidate_text)["rougeL"].fmeasure)
    except Exception:
        return NAN


def compute_meteor(reference_text: str, candidate_text: str) -> float:
    if not nltk:
        return NAN
    try:
        from nltk.translate.meteor_score import meteor_score

        return safe_round(meteor_score([token_split(reference_text)], token_split(candidate_text)))
    except Exception:
        return NAN


def compute_bertscore(reference_text: str, candidate_text: str) -> tuple[float, str]:
    if not ENABLE_HEAVY_METRICS:
        return NAN, ""
    if not bert_score_mod:
        return NAN, "bert_score_not_installed"
    try:
        from bert_score import score as bert_score

        _, _, f1 = bert_score([candidate_text], [reference_text], lang="en", verbose=False)
        return safe_round(float(f1.mean())), ""
    except Exception as exc:
        return NAN, f"{type(exc).__name__}: {exc}"


def compute_intrinsic_metrics(
    exercise_payload: dict[str, Any],
    source_type: str,
    exercise_id: str,
) -> dict[str, Any]:
    views = build_text_views(exercise_payload)
    readability = compute_readability_metrics(views["instruction_only"])
    sentence_stats = compute_sentence_stats(views["instruction_only"])
    instruction_metrics = compute_instruction_completeness_ratio(exercise_payload)
    structure_metrics = compute_structure_metrics(exercise_payload)
    code_quality_metrics = compute_code_quality_metrics(exercise_payload)
    topic = exercise_payload.get("topic", "")

    return {
        "exercise_id": exercise_id,
        "source_type": source_type,
        "topic": exercise_payload.get("topic", ""),
        "difficulty": exercise_payload.get("difficulty", ""),
        "exercise_type": exercise_payload.get("exercise_type", ""),
        "instruction_metrics": {
            "flesch_reading_ease": readability["flesch_reading_ease"],
            "flesch_kincaid_grade": readability["flesch_kincaid_grade"],
            **instruction_metrics,
            "technical_term_density_instruction": compute_technical_term_density(topic, views["instruction_only"]),
            "avg_sentence_length": sentence_stats["avg_sentence_length"],
            "var_sentence_length": sentence_stats["var_sentence_length"],
            "max_sentence_length": sentence_stats["max_sentence_length"],
        },
        "structure_metrics": structure_metrics,
        "code_quality_metrics": code_quality_metrics,
    }


def compute_pair_similarity_metrics(
    ai_payload: dict[str, Any],
    ref_payload: dict[str, Any],
    pair_id: str,
    reference_exercise_id: str,
    ai_exercise_id: str,
) -> dict[str, Any]:
    ref_views = build_text_views(ref_payload)
    ai_views = build_text_views(ai_payload)

    bertscore_f1, heavy_metric_error = compute_bertscore(
        ref_views["instruction_only"],
        ai_views["instruction_only"],
    )

    return {
        "pair_id": pair_id,
        "reference_exercise_id": reference_exercise_id,
        "ai_exercise_id": ai_exercise_id,
        "topic": ai_payload.get("topic") or ref_payload.get("topic", ""),
        "difficulty": ai_payload.get("difficulty") or ref_payload.get("difficulty", ""),
        "exercise_type": ai_payload.get("exercise_type") or ref_payload.get("exercise_type", ""),
        "tfidf_cosine_instruction_only": safe_round(
            tfidf_cosine(ref_views["instruction_only"], ai_views["instruction_only"])
        ),
        "tfidf_cosine_full_text": safe_round(
            tfidf_cosine(ref_views["full_text"], ai_views["full_text"])
        ),
        "rougeL_f1_instruction_only": compute_rouge_l(
            ref_views["instruction_only"],
            ai_views["instruction_only"],
        ),
        "meteor_instruction_only": compute_meteor(
            ref_views["instruction_only"],
            ai_views["instruction_only"],
        ),
        "bertscore_f1_instruction_only": bertscore_f1,
        "topic_coherence_score_ai": compute_topic_coherence_score(ai_payload.get("topic", ""), ai_views["pedagogical_text"]),
        "topic_coherence_score_reference": compute_topic_coherence_score(ref_payload.get("topic", ""), ref_views["pedagogical_text"]),
        "heavy_metric_error": heavy_metric_error,
    }


def main() -> None:
    global ENABLE_HEAVY_METRICS

    parser = argparse.ArgumentParser()
    parser.add_argument("--use-curated", action="store_true")
    parser.add_argument("--pairs-jsonl", default=str(FINAL_PAIRS))
    parser.add_argument("--enable-heavy-metrics", action="store_true")
    parser.add_argument(
        "--include-expert-metrics",
        "--compute-expert-metrics",
        dest="include_expert_metrics",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include intrinsic metrics for expert/reference exercises. Use --no-include-expert-metrics to disable.",
    )
    parser.add_argument("--exercise-output-jsonl", default=str(EXERCISE_OUT_JSONL))
    parser.add_argument("--exercise-output-csv", default=str(EXERCISE_OUT_CSV))
    parser.add_argument("--pair-output-jsonl", default=str(PAIR_OUT_JSONL))
    parser.add_argument("--pair-output-csv", default=str(PAIR_OUT_CSV))
    parser.add_argument("--manifest-output", default=str(METRICS_MANIFEST))
    parser.add_argument("--output-exercise-metrics", action="store_true")
    parser.add_argument("--output-pair-metrics", action="store_true")
    args = parser.parse_args()

    ENABLE_HEAVY_METRICS = args.enable_heavy_metrics

    if args.use_curated:
        args.pairs_jsonl = str(CURATED_FINAL_PAIRS)
        args.exercise_output_jsonl = str(CURATED_EXERCISE_OUT_JSONL)
        args.exercise_output_csv = str(CURATED_EXERCISE_OUT_CSV)
        args.pair_output_jsonl = str(CURATED_PAIR_OUT_JSONL)
        args.pair_output_csv = str(CURATED_PAIR_OUT_CSV)
        args.manifest_output = str(CURATED_METRICS_MANIFEST)

    pair_records = read_jsonl(Path(args.pairs_jsonl))
    exercise_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    seen_exercises: set[str] = set()
    manifest = {
        "num_exercises": 0,
        "num_pairs": len(pair_records),
        "heavy_metrics_enabled": ENABLE_HEAVY_METRICS,
        "include_expert_metrics": args.include_expert_metrics,
        "bertscore_attempted": 0,
        "bertscore_success_count": 0,
        "bertscore_fail_count": 0,
        "status": "ok",
        "reason": "",
    }

    if not pair_records:
        manifest["status"] = "empty_input"
        manifest["reason"] = "no_final_pairs"

    for row in pair_records:
        ai_payload = dict(row["ai_payload"])
        ref_payload = dict(row["reference_payload"])
        ai_id = row["ai_exercise_id"]
        ref_id = row["reference_exercise_id"]

        if ai_id not in seen_exercises:
            exercise_rows.append(compute_intrinsic_metrics(ai_payload, "AI", ai_id))
            seen_exercises.add(ai_id)

        if args.include_expert_metrics and ref_id not in seen_exercises:
            exercise_rows.append(compute_intrinsic_metrics(ref_payload, "Expert", ref_id))
            seen_exercises.add(ref_id)

        pair_rows.append(
            compute_pair_similarity_metrics(
                ai_payload=ai_payload,
                ref_payload=ref_payload,
                pair_id=row["pair_id"],
                reference_exercise_id=ref_id,
                ai_exercise_id=ai_id,
            )
        )

    if ENABLE_HEAVY_METRICS:
        manifest["bertscore_attempted"] = len(pair_rows)
        manifest["bertscore_success_count"] = sum(
            not (isinstance(row.get("bertscore_f1_instruction_only"), float) and math.isnan(row.get("bertscore_f1_instruction_only")))
            and not row.get("heavy_metric_error")
            for row in pair_rows
        )
        manifest["bertscore_fail_count"] = manifest["bertscore_attempted"] - manifest["bertscore_success_count"]

    exercise_rows = sorted(exercise_rows, key=lambda item: (item["source_type"], item["exercise_id"]))
    pair_rows = sorted(pair_rows, key=lambda item: item["pair_id"])
    manifest["num_exercises"] = len(exercise_rows)
    manifest["exercise_rows_by_source"] = {
        "AI": sum(1 for row in exercise_rows if row.get("source_type") == "AI"),
        "Expert": sum(1 for row in exercise_rows if row.get("source_type") == "Expert"),
    }
    if pair_records and not exercise_rows:
        manifest["status"] = "empty_input"
        manifest["reason"] = "no_exercises"

    write_jsonl(exercise_rows, Path(args.exercise_output_jsonl))
    if exercise_rows:
        write_csv(exercise_rows, Path(args.exercise_output_csv))
    else:
        touch_empty_file(Path(args.exercise_output_csv))
    write_jsonl(pair_rows, Path(args.pair_output_jsonl))
    if pair_rows:
        write_csv(pair_rows, Path(args.pair_output_csv))
    else:
        touch_empty_file(Path(args.pair_output_csv))
    write_json(manifest, Path(args.manifest_output))

    print(f"Wrote {len(exercise_rows)} exercise metric rows -> {args.exercise_output_jsonl}")
    print(f"Wrote exercise metric CSV -> {args.exercise_output_csv}")
    print(f"Wrote {len(pair_rows)} pair metric rows -> {args.pair_output_jsonl}")
    print(f"Wrote pair metric CSV -> {args.pair_output_csv}")
    print(f"Wrote metrics manifest -> {args.manifest_output}")


if __name__ == "__main__":
    main()
