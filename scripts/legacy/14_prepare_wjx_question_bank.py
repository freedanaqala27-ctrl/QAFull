from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from survey.human_eval_paths import build_human_eval_paths

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HUMAN_EVAL_PATHS = build_human_eval_paths(PROJECT_ROOT)

DEFAULT_EXPERT_PACKET = HUMAN_EVAL_PATHS.expert_packet
DEFAULT_STUDENT_PACKET = HUMAN_EVAL_PATHS.student_packet
DEFAULT_OUTPUT_DIR = HUMAN_EVAL_PATHS.human_eval_packets_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare WJX-friendly questionnaire text and outlines from curated human evaluation packets."
    )
    parser.add_argument("--expert-packet", type=Path, default=DEFAULT_EXPERT_PACKET)
    parser.add_argument("--student-packet", type=Path, default=DEFAULT_STUDENT_PACKET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--attention-check-interval", type=int, default=3)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def normalize_text(value: Any) -> str:
    return str(value or "").strip().replace("\r\n", "\n")


def format_exercise_text(row: dict[str, Any]) -> str:
    parts = [
        f"练习编号：{row.get('blind_exercise_id', '')}",
        f"主题：{row.get('topic', '')}",
        "请阅读以下练习内容后完成评价。",
        "",
        "题目标题：",
        normalize_text(row.get("title", "")),
        "",
        "题目描述：",
        normalize_text(row.get("instruction_text", "")),
        "",
        "输入输出要求：",
        normalize_text(row.get("expected_output", "")),
        "",
        "约束条件：",
        normalize_text(row.get("constraints_text", "")),
        "",
        "起始代码（如有）：",
        normalize_text(row.get("starter_code", "")),
        "",
        "测试样例（如有）：",
        normalize_text(row.get("test_cases_text", "")),
    ]
    return "\n".join(parts)


def maybe_attention_check(index: int, interval: int) -> list[str]:
    if interval <= 0 or index % interval != 0:
        return []
    return [
        "【注意力检测题】",
        "为确认您在认真作答，请本题选择“同意”。",
        "1 非常不同意",
        "2 不同意",
        "3 一般",
        "4 同意",
        "5 非常同意",
        "",
    ]


def expert_intro() -> list[str]:
    return [
        "问卷标题：",
        "深度学习练习题质量专家评估问卷（盲评）",
        "",
        "问卷说明：",
        "尊敬的老师/助教：",
        "您好！本问卷用于评价深度学习课程练习题的质量。您将看到若干道练习题，并根据题目本身进行评分。",
        "为保证研究客观性，题目来源信息不向评审者展示。请您仅依据题面内容、代码上下文和教学适配性进行判断。",
        "本问卷仅用于学术研究，所有数据匿名处理。感谢您的支持。",
        "",
        "第一部分：知情同意与背景信息（只答一次）",
        "Q1. 您是否知情同意参与本研究？",
        "1 是，我同意参与",
        "2 否，我不同意参与",
        "",
        "Q2. 您目前的身份是？",
        "高校教师 / 助教或教学辅助人员 / 博士研究生 / 硕士研究生 / 其他",
        "",
        "Q3. 您是否具有与编程、机器学习或深度学习相关的教学/助教经验？",
        "有 / 没有",
        "",
        "Q4. 您的相关教学/助教经验时长为？",
        "少于 1 年 / 1–2 年 / 3–5 年 / 5 年以上",
        "",
        "Q5. 您对深度学习框架（如 PyTorch、TensorFlow）的熟悉程度如何？",
        "1 非常不熟悉 / 2 不太熟悉 / 3 一般 / 4 比较熟悉 / 5 非常熟悉",
        "",
        "Q6. 您平时评阅/设计课程练习题的频率如何？",
        "几乎没有 / 偶尔 / 有时 / 经常 / 非常频繁",
        "",
        "第二部分：单道练习题评价（每道题重复一次）",
        "评分选项统一为：1 非常不同意 / 2 不同意 / 3 一般 / 4 同意 / 5 非常同意 / 6 不适用或无法判断",
        "",
    ]


def expert_block(row: dict[str, Any], index: int) -> list[str]:
    return [
        "-" * 40,
        f"练习评价块 E{index:02d}",
        "-" * 40,
        "【说明题】",
        format_exercise_text(row),
        "",
        "Q7. 该练习题清楚说明了学习者需要完成的任务。",
        "Q8. 该练习题提供了完成任务所需的关键信息（如背景、输入输出要求、限制条件、评价标准等）。",
        "Q9. 该练习题在深度学习概念、方法和表述上基本准确，没有明显错误。",
        "Q10. 该练习题的组成较完整，具备合理的题干、任务要求、必要上下文及预期输出导向。",
        "Q11. 该练习题的难度与目标学习者水平基本匹配。",
        "Q12. 该练习题能够有效帮助学生练习或理解相应的深度学习知识或技能。",
        "Q13. 该练习题适合纳入深度学习相关课程的教学或作业场景。",
        "Q14. 该练习题在实际教学中具有较高的可使用性和可操作性。",
        "Q15. 若该练习题涉及代码，现有代码上下文足以支持理解、修改或调试。",
        "Q16. 总体而言，这是一道高质量的深度学习练习题。",
        "",
        "Q17. 这道题最需要改进的地方是什么？",
        "Q18. 这道题是否存在歧义、信息缺失或错误？如有，请简要说明。",
        "",
    ]


def expert_outro() -> list[str]:
    return [
        "第四部分：整批题目完成后（只答一次）",
        "Q19. 从整体看，本批练习题的总体质量如何？",
        "1 很差 / 2 较差 / 3 一般 / 4 较好 / 5 很好",
        "",
        "Q20. 您认为高质量深度学习练习题最重要的三个特征是什么？",
        "最多选 3 项：指令清晰 / 信息充分 / 内容准确 / 难度适中 / 结构完整 / 教学价值高 / 代码上下文充分 / 与课程目标契合 / 具有实践性 / 其他（填空）",
        "",
        "Q21. 您对本问卷本身还有什么建议？",
    ]


def student_intro() -> list[str]:
    return [
        "问卷标题：",
        "深度学习练习题学习体验与可接受度评估问卷（学生版，盲评）",
        "",
        "问卷说明：",
        "您好！本问卷用于了解学生对深度学习练习题的学习体验与评价。",
        "您将阅读若干道深度学习练习题，并根据自己的真实感受进行评分。",
        "本问卷匿名填写，仅用于学术研究。请根据题目本身作答，不必猜测题目来源。感谢您的参与。",
        "",
        "第一部分：知情同意与背景信息（只需填写一次）",
        "Q1. 您是否知情同意参与本研究？",
        "是 / 否",
        "",
        "Q2. 您目前所处的学习阶段是？",
        "本科低年级 / 本科高年级 / 硕士研究生 / 博士研究生 / 其他",
        "",
        "Q3. 您的编程学习背景如何？",
        "几乎没有编程基础 / 学过基础编程 / 学过机器学习或深度学习基础 / 有较多相关课程或项目经验",
        "",
        "Q4. 您对 Python 的熟悉程度如何？",
        "1 非常不熟悉 / 2 不太熟悉 / 3 一般 / 4 比较熟悉 / 5 非常熟悉",
        "",
        "Q5. 您对深度学习框架（如 PyTorch、TensorFlow）的熟悉程度如何？",
        "1 非常不熟悉 / 2 不太熟悉 / 3 一般 / 4 比较熟悉 / 5 非常熟悉",
        "",
        "Q6. 您是否学习过深度学习相关课程？",
        "是 / 否",
        "",
        "Q7. 您对以下哪个主题相对更熟悉？（可多选）",
        "CNN / RNN-LSTM / Transformer / 优化与训练分析 / 都不太熟悉",
        "",
        "请先阅读练习题内容，再根据你的真实感受评分。",
        "第二部分：单道练习题评价（每道题重复一次）",
        "除特别说明外，以下题目均采用 5 点量表：1 非常不同意 / 2 不同意 / 3 一般 / 4 同意 / 5 非常同意",
        "",
    ]


def student_block(row: dict[str, Any], index: int) -> list[str]:
    return [
        "-" * 40,
        f"练习评价块 S{index:02d}",
        "-" * 40,
        "【说明题】",
        format_exercise_text(row),
        "",
        "Q8. 请根据你对这道练习题的阅读体验，对以下说法进行评分。[矩阵量表题]",
        "这道题清楚说明了我需要完成的任务目标。",
        "这道题提供了开始作答所需的关键信息与支持。",
        "这道题与深度学习课程内容或实际编程任务相关。",
        "这道题对我的学习有明显帮助。",
        "完成这道题时，我需要同时处理很多信息。",
        "阅读这道题时，我需要额外花力气去找出最重要的信息。",
        "完成这道题时，我会主动投入思考和理解。",
        "总体来说，完成这道题需要我投入较高的心理努力。",
        "",
    ]


def student_outro() -> list[str]:
    return [
        "以下题目请基于你刚刚完成的这一批练习题整体体验作答。",
        "Q9. 请根据你对本批练习题的整体感受进行评分。[矩阵量表题]",
        "这批练习题有助于提高我对深度学习知识的理解。",
        "整体上，这批练习题比较容易上手。",
        "如果后续课程继续使用这类练习题，我愿意继续使用。",
        "总体而言，这批练习题的质量较高。",
        "",
        "Q10. 你对本问卷或本批练习题还有什么建议？",
    ]


def build_expert_question_bank(rows: list[dict[str, Any]], interval: int) -> str:
    lines = expert_intro()
    for index, row in enumerate(rows, start=1):
        lines.extend(expert_block(row, index))
        lines.extend(maybe_attention_check(index, interval))
    lines.extend(expert_outro())
    return "\n".join(lines)


def build_student_question_bank(rows: list[dict[str, Any]], interval: int) -> str:
    lines = student_intro()
    for index, row in enumerate(rows, start=1):
        lines.extend(student_block(row, index))
        lines.extend(maybe_attention_check(index, interval))
    lines.extend(student_outro())
    return "\n".join(lines)


def build_outline(rows: list[dict[str, Any]], audience: str) -> list[dict[str, Any]]:
    outline_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        outline_rows.append(
            {
                "audience": audience,
                "sequence_no": index,
                "blind_exercise_id": row.get("blind_exercise_id", ""),
                "topic": row.get("topic", ""),
                "difficulty": row.get("difficulty", ""),
                "exercise_type": row.get("exercise_type", ""),
                "title": row.get("title", ""),
                "question_block_label": f"{'E' if audience == 'expert' else 'S'}{index:02d}",
                "display_text": format_exercise_text(row),
            }
        )
    return outline_rows


def generate_package_question_banks(base_dir: Path, audience: str, interval: int) -> list[dict[str, Any]]:
    manifest_rows: list[dict[str, Any]] = []
    if not base_dir.exists():
        return manifest_rows

    packet_filename = "expert_eval_packet.curated.v1.csv" if audience == "expert" else "student_eval_packet.curated.v1.csv"
    for package_dir in sorted(path for path in base_dir.iterdir() if path.is_dir()):
        packet_rows = read_csv(package_dir / packet_filename)
        if not packet_rows:
            continue
        question_bank = (
            build_expert_question_bank(packet_rows, interval)
            if audience == "expert"
            else build_student_question_bank(packet_rows, interval)
        )
        write_text(package_dir / "wjx_question_bank.curated.txt", question_bank)
        write_csv(build_outline(packet_rows, audience), package_dir / "wjx_question_outline.curated.csv")
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
    expert_rows = read_csv(args.expert_packet)
    student_rows = read_csv(args.student_packet)
    output_dir = args.output_dir
    packets_dir = output_dir / "packets"
    materials_dir = output_dir / "materials"
    audit_dir = output_dir / "audit"

    write_text(
        materials_dir / "wjx_expert_question_bank.curated.txt",
        build_expert_question_bank(expert_rows, args.attention_check_interval),
    )
    write_text(
        materials_dir / "wjx_student_question_bank.curated.txt",
        build_student_question_bank(student_rows, args.attention_check_interval),
    )
    write_csv(
        build_outline(expert_rows, "expert"),
        materials_dir / "wjx_expert_question_outline.curated.csv",
    )
    write_csv(
        build_outline(student_rows, "student"),
        materials_dir / "wjx_student_question_outline.curated.csv",
    )

    package_manifest_rows: list[dict[str, Any]] = []
    package_manifest_rows.extend(
        generate_package_question_banks(
            packets_dir / "expert_packages", "expert", args.attention_check_interval
        )
    )
    package_manifest_rows.extend(
        generate_package_question_banks(
            packets_dir / "student_packages", "student", args.attention_check_interval
        )
    )
    write_csv(package_manifest_rows, audit_dir / "wjx_package_manifest.curated.v1.csv")

    manifest = {
        "expert_packet_rows": len(expert_rows),
        "student_packet_rows": len(student_rows),
        "attention_check_interval": args.attention_check_interval,
        "package_question_bank_count": len(package_manifest_rows),
        "outputs": {
            "expert_question_bank": str(materials_dir / "wjx_expert_question_bank.curated.txt"),
            "student_question_bank": str(materials_dir / "wjx_student_question_bank.curated.txt"),
            "expert_question_outline": str(
                materials_dir / "wjx_expert_question_outline.curated.csv"
            ),
            "student_question_outline": str(
                materials_dir / "wjx_student_question_outline.curated.csv"
            ),
            "package_manifest": str(audit_dir / "wjx_package_manifest.curated.v1.csv"),
        },
    }
    write_text(
        audit_dir / "wjx_question_bank_manifest.v1.json",
        json.dumps(manifest, ensure_ascii=False, indent=2),
    )

    print(f"Wrote expert WJX question bank -> {materials_dir / 'wjx_expert_question_bank.curated.txt'}")
    print(f"Wrote student WJX question bank -> {materials_dir / 'wjx_student_question_bank.curated.txt'}")


if __name__ == "__main__":
    main()
