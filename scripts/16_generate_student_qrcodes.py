from __future__ import annotations

import argparse
import csv
from pathlib import Path

import qrcode
from survey.human_eval_paths import build_human_eval_paths

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HUMAN_EVAL_PATHS = build_human_eval_paths(PROJECT_ROOT)
DISTRIBUTION_DIR = HUMAN_EVAL_PATHS.distribution_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate QR codes for student survey links.")
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=HUMAN_EVAL_PATHS.student_distribution_sheet,
        help="Input distribution sheet CSV.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=HUMAN_EVAL_PATHS.student_qrcodes_dir,
        help="Directory to write QR code PNG files.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=HUMAN_EVAL_PATHS.student_distribution_with_qrcodes,
        help="Output CSV with QR code file paths.",
    )
    return parser.parse_args()


def make_qr(data: str, output_path: Path) -> None:
    image = qrcode.make(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "姓名": (row.get("姓名") or "").strip(),
        "编号": (row.get("编号") or "").strip(),
        "package": (row.get("package") or "").strip(),
        "专属链接": (row.get("专属链接") or "").strip(),
    }


def main() -> None:
    args = parse_args()
    input_csv = args.input_csv
    output_dir = args.output_dir
    output_csv = args.output_csv

    rows_out: list[dict[str, str]] = []
    with input_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            normalized = normalize_row(row)
            participant_id = normalized["编号"]
            link = normalized["专属链接"]
            if not participant_id or not link:
                continue
            qr_path = output_dir / f"{participant_id}.png"
            make_qr(link, qr_path)
            rows_out.append(
                {
                    **normalized,
                    "二维码文件": str(qr_path.resolve()),
                }
            )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["姓名", "编号", "package", "专属链接", "二维码文件"])
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"Generated {len(rows_out)} QR code images -> {output_dir.resolve()}")
    print(f"Wrote distribution sheet with QR paths -> {output_csv.resolve()}")


if __name__ == "__main__":
    main()
