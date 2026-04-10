from __future__ import annotations

import argparse
import csv
import os
from itertools import cycle, islice
from pathlib import Path
from urllib.parse import urlencode

from survey.human_eval_paths import build_human_eval_paths

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HUMAN_EVAL_PATHS = build_human_eval_paths(PROJECT_ROOT)
DEFAULT_BASE_URL = "https://fywtwdfryvruudyvejwbrk.streamlit.app/"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate student distribution sheet with unique survey links.")
    parser.add_argument("--package-manifest", type=Path, default=HUMAN_EVAL_PATHS.student_package_manifest)
    parser.add_argument("--output-csv", type=Path, default=HUMAN_EVAL_PATHS.student_distribution_sheet)
    parser.add_argument("--base-url", default=os.environ.get("STUDENT_SURVEY_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--participant-count", type=int, default=60)
    parser.add_argument("--participant-prefix", default="S")
    return parser.parse_args()


def load_package_ids(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        package_ids: list[str] = []
        for row in reader:
            package_id = str(row.get("package_id") or "").strip()
            if package_id:
                package_ids.append(package_id)
        return package_ids


def normalize_base_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return DEFAULT_BASE_URL
    return text.rstrip("/") + "/"


def build_link(base_url: str, package_id: str, participant_id: str) -> str:
    query = urlencode({"package": package_id, "pid": participant_id})
    return f"{base_url}?{query}"


def main() -> None:
    args = parse_args()
    package_ids = load_package_ids(args.package_manifest)
    if not package_ids:
        raise FileNotFoundError(f"Package manifest not found or empty: {args.package_manifest}")

    base_url = normalize_base_url(args.base_url)
    selected_packages = list(islice(cycle(package_ids), max(0, int(args.participant_count))))

    rows: list[dict[str, str]] = []
    for index, package_id in enumerate(selected_packages, start=1):
        participant_id = f"{args.participant_prefix}{index:03d}"
        rows.append(
            {
                "姓名": "",
                "编号": participant_id,
                "package": package_id,
                "专属链接": build_link(base_url, package_id, participant_id),
            }
        )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["姓名", "编号", "package", "专属链接"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated distribution sheet -> {args.output_csv.resolve()}")
    print(f"Base URL: {base_url}")
    print(f"Packages: {len(package_ids)} | Participants: {len(rows)}")


if __name__ == "__main__":
    main()