from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Any

from survey.human_eval_paths import build_human_eval_paths

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HUMAN_EVAL_PATHS = build_human_eval_paths(PROJECT_ROOT)

DEFAULT_EXPERT_PACKET = HUMAN_EVAL_PATHS.expert_packet
DEFAULT_STUDENT_PACKET = HUMAN_EVAL_PATHS.student_packet
DEFAULT_OUTPUT_DIR = HUMAN_EVAL_PATHS.human_eval_packets_dir

BOOKLET_VISIBLE_COLUMNS = [
    "blind_exercise_id",
    "title",
    "topic",
    "difficulty",
    "exercise_type",
    "instruction_text",
    "starter_code",
    "expected_output",
    "constraints_text",
    "test_cases_text",
]

EXPERT_RESPONSE_COLUMNS = [
    "rating_id",
    "evaluator_id",
    "blind_exercise_id",
    "instruction_clarity",
    "information_completeness",
    "content_accuracy",
    "structure_completeness",
    "difficulty_appropriateness",
    "pedagogical_effectiveness",
    "course_suitability",
    "practical_value",
    "code_quality",
    "overall_score",
    "needs_improvement",
    "issue_flags",
    "notes",
    "dataset_split",
]

STUDENT_RESPONSE_COLUMNS = [
    "rating_id",
    "student_id",
    "blind_exercise_id",
    "goal_orientation",
    "support_sufficiency",
    "course_relevance",
    "learning_helpfulness",
    "intrinsic_load",
    "extraneous_load",
    "active_engagement",
    "mental_effort",
    "notes",
    "dataset_split",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build blind review booklets and merge-friendly response templates from curated evaluation packets."
    )
    parser.add_argument("--expert-packet", type=Path, default=DEFAULT_EXPERT_PACKET)
    parser.add_argument("--student-packet", type=Path, default=DEFAULT_STUDENT_PACKET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(rows: list[dict[str, Any]], path: Path, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def normalize_multiline(value: Any) -> str:
    return str(value or "").strip().replace("\r\n", "\n")


def build_booklet_rows(packet_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: row.get(key, "") for key in BOOKLET_VISIBLE_COLUMNS} for row in packet_rows]


def format_markdown_card(index: int, row: dict[str, Any]) -> str:
    parts = [
        f"## 练习 {index}: {row.get('blind_exercise_id', '')}",
        "",
        f"**练习编号**：{row.get('blind_exercise_id', '')}",
        f"**主题**：{row.get('topic', '')}",
        f"**难度**：{row.get('difficulty', '')}",
        f"**题型**：{row.get('exercise_type', '')}",
        "",
        "### 题目全文",
        f"题目标题：{row.get('title', '')}",
        "",
        "题目描述：",
        normalize_multiline(row.get("instruction_text", "")),
        "",
        "输入输出要求：",
        normalize_multiline(row.get("expected_output", "")),
    ]

    constraints = normalize_multiline(row.get("constraints_text", ""))
    if constraints:
        parts.extend(["", "约束条件：", constraints])

    starter_code = normalize_multiline(row.get("starter_code", ""))
    if starter_code:
        parts.extend(["", "起始代码（如有）：", "```python", starter_code, "```"])

    test_cases = normalize_multiline(row.get("test_cases_text", ""))
    if test_cases:
        parts.extend(["", "测试样例（如有）：", test_cases])

    parts.extend(["", "---", ""])
    return "\n".join(parts)


def build_markdown_booklet(rows: list[dict[str, Any]]) -> str:
    sections = [
        "# 盲评材料册",
        "",
        "本材料用于匿名人评。",
        "请仅根据练习本身进行评价，不要猜测其来源。",
        "",
    ]
    for index, row in enumerate(rows, start=1):
        sections.append(format_markdown_card(index, row))
    return "\n".join(sections)


def render_text_block(title: str, value: str) -> str:
    if not value.strip():
        return ""
    return (
        f"<section class=\"block\"><h3>{html.escape(title)}</h3>"
        f"<div class=\"text\">{html.escape(value).replace(chr(10), '<br>')}</div></section>"
    )


def render_code_block(title: str, value: str) -> str:
    if not value.strip():
        return ""
    return (
        f"<section class=\"block\"><h3>{html.escape(title)}</h3>"
        f"<pre><code>{html.escape(value)}</code></pre></section>"
    )


def build_html_booklet(rows: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for index, row in enumerate(rows, start=1):
        body = "".join(
            [
                render_text_block("题目标题", str(row.get("title", ""))),
                render_text_block("题目描述", normalize_multiline(row.get("instruction_text", ""))),
                render_text_block("输入输出要求", normalize_multiline(row.get("expected_output", ""))),
                render_text_block("约束条件", normalize_multiline(row.get("constraints_text", ""))),
                render_code_block("起始代码（如有）", normalize_multiline(row.get("starter_code", ""))),
                render_text_block("测试样例（如有）", normalize_multiline(row.get("test_cases_text", ""))),
            ]
        )
        cards.append(
            f"""
            <article class="card">
              <header class="card-header">
                <div class="eyebrow">练习 {index}</div>
                <h2>{html.escape(str(row.get('blind_exercise_id', '')))}</h2>
                <p class="meta">
                  <span>主题：{html.escape(str(row.get('topic', '')))}</span>
                  <span>难度：{html.escape(str(row.get('difficulty', '')))}</span>
                  <span>题型：{html.escape(str(row.get('exercise_type', '')))}</span>
                </p>
              </header>
              {body}
            </article>
            """
        )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>盲评材料册</title>
  <style>
    body {{
      font-family: 'Noto Serif SC', 'Microsoft YaHei', serif;
      margin: 24px;
      color: #1f2933;
      line-height: 1.6;
      background: #faf8f4;
    }}
    .intro {{
      background: #fffdf8;
      border: 1px solid #d9d1c3;
      padding: 16px 18px;
      margin-bottom: 24px;
    }}
    .card {{
      page-break-after: always;
      break-after: page;
      background: white;
      border: 1px solid #d5dbe3;
      padding: 24px;
      margin-bottom: 24px;
    }}
    .card-header {{
      border-bottom: 2px solid #e6ebf1;
      margin-bottom: 18px;
      padding-bottom: 12px;
    }}
    .eyebrow {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #6b7280;
    }}
    .meta {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      color: #52606d;
      font-size: 14px;
    }}
    .block {{
      margin-bottom: 16px;
    }}
    pre {{
      white-space: pre-wrap;
      background: #f7f9fb;
      border: 1px solid #e5e7eb;
      padding: 14px;
      overflow-x: auto;
    }}
  </style>
</head>
<body>
  <section class="intro">
    <h1>盲评材料册</h1>
    <p>请仅根据题面内容、代码上下文和教学适配性进行评价，不要猜测题目来源。</p>
  </section>
  {''.join(cards)}
</body>
</html>"""


def build_response_template(packet_rows: list[dict[str, Any]], response_columns: list[str]) -> list[dict[str, Any]]:
    template_rows: list[dict[str, Any]] = []
    for row in packet_rows:
        template_rows.append({column: row.get(column, "") for column in response_columns})
    return template_rows


def generate_package_materials(base_dir: Path, audience: str) -> list[dict[str, Any]]:
    manifest_rows: list[dict[str, Any]] = []
    if not base_dir.exists():
        return manifest_rows

    packet_filename = "expert_eval_packet.curated.v1.csv" if audience == "expert" else "student_eval_packet.curated.v1.csv"
    response_filename = "expert_response_template.curated.v1.csv" if audience == "expert" else "student_response_template.curated.v1.csv"
    response_columns = EXPERT_RESPONSE_COLUMNS if audience == "expert" else STUDENT_RESPONSE_COLUMNS

    for package_dir in sorted(path for path in base_dir.iterdir() if path.is_dir()):
        packet_rows = read_csv(package_dir / packet_filename)
        if not packet_rows:
            continue
        booklet_rows = build_booklet_rows(packet_rows)
        write_text(package_dir / "blind_review_booklet.curated.md", build_markdown_booklet(booklet_rows))
        write_text(package_dir / "blind_review_booklet.curated.html", build_html_booklet(booklet_rows))
        write_csv(
            build_response_template(packet_rows, response_columns),
            package_dir / response_filename,
            response_columns,
        )
        manifest_rows.append(
            {
                "package_id": package_dir.name,
                "audience": audience,
                "exercise_count": len(packet_rows),
                "output_dir": str(package_dir),
            }
        )
    return manifest_rows


def main() -> None:
    args = parse_args()
    expert_packet_rows = read_csv(args.expert_packet)
    student_packet_rows = read_csv(args.student_packet)
    output_dir = args.output_dir
    packets_dir = output_dir / "packets"
    materials_dir = output_dir / "materials"
    templates_dir = output_dir / "templates"
    audit_dir = output_dir / "audit"
    audit_materials_dir = audit_dir / "materials"

    booklet_rows = build_booklet_rows(expert_packet_rows or student_packet_rows)
    write_text(
        materials_dir / "blind_review_booklet.curated.md",
        build_markdown_booklet(booklet_rows),
    )
    write_text(
        materials_dir / "blind_review_booklet.curated.html",
        build_html_booklet(booklet_rows),
    )

    write_csv(
        build_response_template(expert_packet_rows, EXPERT_RESPONSE_COLUMNS),
        templates_dir / "expert_response_template.curated.v1.csv",
        EXPERT_RESPONSE_COLUMNS,
    )
    write_csv(
        build_response_template(student_packet_rows, STUDENT_RESPONSE_COLUMNS),
        templates_dir / "student_response_template.curated.v1.csv",
        STUDENT_RESPONSE_COLUMNS,
    )

    package_manifest_rows: list[dict[str, Any]] = []
    package_manifest_rows.extend(generate_package_materials(packets_dir / "expert_packages", "expert"))
    package_manifest_rows.extend(generate_package_materials(packets_dir / "student_packages", "student"))
    write_csv(
        package_manifest_rows,
        audit_materials_dir / "package_materials_manifest.curated.v1.csv",
        ["package_id", "audience", "exercise_count", "output_dir"],
    )

    manifest = {
        "expert_packet_rows": len(expert_packet_rows),
        "student_packet_rows": len(student_packet_rows),
        "booklet_row_count": len(booklet_rows),
        "package_material_count": len(package_manifest_rows),
        "outputs": {
            "booklet_markdown": str(materials_dir / "blind_review_booklet.curated.md"),
            "booklet_html": str(materials_dir / "blind_review_booklet.curated.html"),
            "expert_response_template": str(
                templates_dir / "expert_response_template.curated.v1.csv"
            ),
            "student_response_template": str(
                templates_dir / "student_response_template.curated.v1.csv"
            ),
            "package_material_manifest": str(
                audit_materials_dir / "package_materials_manifest.curated.v1.csv"
            ),
        },
    }
    write_text(
        audit_materials_dir / "human_eval_materials_manifest.v1.json",
        json.dumps(manifest, ensure_ascii=False, indent=2),
    )

    print(f"Wrote booklet markdown -> {materials_dir / 'blind_review_booklet.curated.md'}")
    print(f"Wrote booklet html -> {materials_dir / 'blind_review_booklet.curated.html'}")
    print(f"Wrote expert response template -> {templates_dir / 'expert_response_template.curated.v1.csv'}")
    print(f"Wrote student response template -> {templates_dir / 'student_response_template.curated.v1.csv'}")


if __name__ == "__main__":
    main()
