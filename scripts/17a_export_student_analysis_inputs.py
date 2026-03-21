from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


META_COLUMNS = [
    "participant_id",
    "package_id",
    "consent",
    "study_stage",
    "programming_background",
    "python_familiarity",
    "framework_familiarity",
    "dl_course_taken",
    "familiar_topics",
    "started_at",
    "submitted_at",
    "attention_check_score",
    "attention_check_passed",
    "created_at",
    "updated_at",
]

ITEM_COLUMNS = [
    "participant_id",
    "package_id",
    "blind_exercise_id",
    "item_order",
    "task_goal_clarity",
    "key_support",
    "course_relevance",
    "learning_help",
    "info_load",
    "search_effort",
    "active_engagement",
    "mental_effort",
    "open_comment",
    "saved_at",
]

BATCH_COLUMNS = [
    "participant_id",
    "package_id",
    "overall_usefulness",
    "overall_ease",
    "continued_use_intention",
    "overall_quality",
    "final_comment",
    "rating_time_seconds",
    "saved_at",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export reproducible student analysis input CSVs from survey DB or raw CSV snapshots."
    )
    parser.add_argument(
        "--meta-csv",
        type=Path,
        default=None,
        help="Optional raw participant_meta CSV source. If omitted, the script can fetch from Supabase.",
    )
    parser.add_argument(
        "--item-csv",
        type=Path,
        default=None,
        help="Optional raw item_ratings CSV source. If omitted, the script can fetch from Supabase.",
    )
    parser.add_argument(
        "--batch-csv",
        type=Path,
        default=None,
        help="Optional raw batch_feedback CSV source. If omitted, the script can fetch from Supabase.",
    )
    parser.add_argument(
        "--fetch-from-db",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Fetch raw survey tables directly from Supabase when local CSV inputs are not provided.",
    )
    parser.add_argument(
        "--write-raw-snapshots",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When fetching from DB, also save raw table snapshots under data/human_eval/survey_raw_exports.",
    )
    parser.add_argument(
        "--raw-snapshot-dir",
        type=Path,
        default=Path("data/human_eval/survey_raw_exports"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/student_subsets"),
    )
    parser.add_argument(
        "--participant-ids-csv",
        type=Path,
        default=None,
        help="Optional CSV containing a participant_id column to freeze the formal subset.",
    )
    parser.add_argument(
        "--require-submitted",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Keep only participants with non-empty submitted_at in participant_meta.",
    )
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def normalize_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def normalize_frame(df: pd.DataFrame, columns: list[str], aliases: dict[str, str] | None = None) -> pd.DataFrame:
    if aliases:
        rename_map = {source: target for source, target in aliases.items() if source in df.columns and target not in df.columns}
        if rename_map:
            df = df.rename(columns=rename_map)
    if df.empty:
        return pd.DataFrame(columns=columns)
    working = df.copy()
    for column in columns:
        if column not in working.columns:
            working[column] = ""
    return working[columns].copy()


def normalize_meta(df: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "student_id": "participant_id",
    }
    working = normalize_frame(df, META_COLUMNS, aliases=aliases)
    if "attention_check_passed" in working.columns:
        working["attention_check_passed"] = working["attention_check_passed"].map(
            lambda x: "" if normalize_text(x) == "" else normalize_text(x)
        )
    return working


def normalize_item(df: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "student_id": "participant_id",
        "notes": "open_comment",
        "questionnaire_suggestions": "open_comment",
    }
    working = normalize_frame(df, ITEM_COLUMNS, aliases=aliases)
    return working


def normalize_batch(df: pd.DataFrame) -> pd.DataFrame:
    aliases = {
        "student_id": "participant_id",
        "questionnaire_suggestions": "final_comment",
        "overall_batch_quality": "overall_quality",
    }
    working = normalize_frame(df, BATCH_COLUMNS, aliases=aliases)
    return working


def fetch_raw_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    from survey.student_survey_db import (
        BATCH_FEEDBACK_TABLE,
        ITEM_RATINGS_TABLE,
        PARTICIPANT_META_TABLE,
        _fetch_all_rows,
        init_db,
    )

    init_db()
    meta_df = pd.DataFrame(_fetch_all_rows(PARTICIPANT_META_TABLE))
    item_df = pd.DataFrame(_fetch_all_rows(ITEM_RATINGS_TABLE))
    batch_df = pd.DataFrame(_fetch_all_rows(BATCH_FEEDBACK_TABLE))
    return meta_df, item_df, batch_df


def write_raw_snapshots(meta_df: pd.DataFrame, item_df: pd.DataFrame, batch_df: pd.DataFrame, out_dir: Path) -> dict[str, str]:
    ensure_dir(out_dir)
    outputs = {
        "participant_meta_raw": out_dir / "participant_meta.raw.csv",
        "item_ratings_raw": out_dir / "item_ratings.raw.csv",
        "batch_feedback_raw": out_dir / "batch_feedback.raw.csv",
    }
    meta_df.to_csv(outputs["participant_meta_raw"], index=False, encoding="utf-8-sig")
    item_df.to_csv(outputs["item_ratings_raw"], index=False, encoding="utf-8-sig")
    batch_df.to_csv(outputs["batch_feedback_raw"], index=False, encoding="utf-8-sig")
    return {key: str(path) for key, path in outputs.items()}


def submitted_participant_ids(meta_df: pd.DataFrame) -> set[str]:
    if meta_df.empty or "participant_id" not in meta_df.columns:
        return set()
    if "submitted_at" not in meta_df.columns:
        return set(meta_df["participant_id"].astype(str))
    submitted_mask = meta_df["submitted_at"].map(lambda x: normalize_text(x) != "")
    return set(meta_df.loc[submitted_mask, "participant_id"].astype(str))


def participant_ids_from_csv(path: Path | None) -> set[str] | None:
    if path is None:
        return None
    df = pd.read_csv(path)
    if "participant_id" not in df.columns:
        raise ValueError(f"{path} must contain a participant_id column.")
    return set(df["participant_id"].astype(str))


def select_formal_participants(
    meta_df: pd.DataFrame,
    item_df: pd.DataFrame,
    batch_df: pd.DataFrame,
    *,
    require_submitted: bool,
    frozen_ids: set[str] | None,
) -> tuple[list[str], dict[str, Any]]:
    meta_ids = set(meta_df["participant_id"].astype(str)) if "participant_id" in meta_df.columns else set()
    item_ids = set(item_df["participant_id"].astype(str)) if "participant_id" in item_df.columns else set()
    batch_ids = set(batch_df["participant_id"].astype(str)) if "participant_id" in batch_df.columns else set()

    eligible_ids = meta_ids & item_ids & batch_ids
    submitted_ids = submitted_participant_ids(meta_df) if require_submitted else meta_ids
    eligible_ids &= submitted_ids

    if frozen_ids is not None:
        eligible_ids &= frozen_ids

    selected = sorted(eligible_ids)
    summary = {
        "meta_participants": len(meta_ids),
        "item_participants": len(item_ids),
        "batch_participants": len(batch_ids),
        "submitted_participants": len(submitted_ids),
        "selected_participants": len(selected),
        "used_frozen_participant_list": frozen_ids is not None,
    }
    return selected, summary


def filter_by_participants(df: pd.DataFrame, participant_ids: list[str]) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    return df[df["participant_id"].astype(str).isin(participant_ids)].copy()


def main() -> None:
    args = parse_args()

    meta_df = read_csv(args.meta_csv)
    item_df = read_csv(args.item_csv)
    batch_df = read_csv(args.batch_csv)
    source_mode = "csv"
    raw_snapshot_outputs: dict[str, str] = {}

    if meta_df.empty or item_df.empty or batch_df.empty:
        if not args.fetch_from_db:
            raise SystemExit(
                "Missing one or more input CSVs. Provide --meta-csv/--item-csv/--batch-csv or enable --fetch-from-db."
            )
        source_mode = "supabase"
        meta_df, item_df, batch_df = fetch_raw_tables()
        if args.write_raw_snapshots:
            raw_snapshot_outputs = write_raw_snapshots(meta_df, item_df, batch_df, args.raw_snapshot_dir)

    meta_df = normalize_meta(meta_df)
    item_df = normalize_item(item_df)
    batch_df = normalize_batch(batch_df)

    frozen_ids = participant_ids_from_csv(args.participant_ids_csv)
    participant_ids, selection_summary = select_formal_participants(
        meta_df,
        item_df,
        batch_df,
        require_submitted=args.require_submitted,
        frozen_ids=frozen_ids,
    )

    meta_out = filter_by_participants(meta_df, participant_ids)
    item_out = filter_by_participants(item_df, participant_ids)
    batch_out = filter_by_participants(batch_df, participant_ids)

    ensure_dir(args.output_dir)
    participant_meta_path = args.output_dir / "participant_meta_30.csv"
    item_ratings_path = args.output_dir / "item_ratings_30.csv"
    batch_feedback_path = args.output_dir / "batch_feedback_30.csv"

    meta_out.to_csv(participant_meta_path, index=False, encoding="utf-8-sig")
    item_out.to_csv(item_ratings_path, index=False, encoding="utf-8-sig")
    batch_out.to_csv(batch_feedback_path, index=False, encoding="utf-8-sig")

    manifest = {
        "source_mode": source_mode,
        "source_inputs": {
            "meta_csv": str(args.meta_csv) if args.meta_csv else "",
            "item_csv": str(args.item_csv) if args.item_csv else "",
            "batch_csv": str(args.batch_csv) if args.batch_csv else "",
        },
        "raw_snapshot_outputs": raw_snapshot_outputs,
        "output_dir": str(args.output_dir),
        "filters": {
            "require_submitted": args.require_submitted,
            "participant_ids_csv": str(args.participant_ids_csv) if args.participant_ids_csv else "",
        },
        "selection_summary": selection_summary,
        "outputs": {
            "participant_meta": str(participant_meta_path),
            "item_ratings": str(item_ratings_path),
            "batch_feedback": str(batch_feedback_path),
        },
        "row_counts": {
            "participant_meta": int(len(meta_out)),
            "item_ratings": int(len(item_out)),
            "batch_feedback": int(len(batch_out)),
        },
        "selected_participant_ids": participant_ids,
    }

    manifest_path = args.output_dir / "student_subset_export_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
