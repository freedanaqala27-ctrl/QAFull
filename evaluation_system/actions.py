from __future__ import annotations

from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


ACTION_REGISTRY: dict[str, dict[str, Any]] = {
    "start_generation": {
        "label": "生成候选题",
        "mode": "script_chain",
        "can_execute": True,
        "scripts": [
            "scripts/01_build_prompts.py",
            "scripts/02_generate_candidates.py",
            "scripts/04_filter_candidates.py",
            "scripts/03_log_generation_runs.py",
        ],
        "inputs": [
            "prompts/v1/master/MP-v1.md",
            "data/frozen/expert_exercises.main_frozen.v1.json",
        ],
        "outputs": [
            "outputs/raw_generations/generations.raw.v1.jsonl",
            "outputs/raw_generations/generation_manifest.v1.json",
            "outputs/filtered/accepted/candidates.accepted.v1.jsonl",
            "outputs/filtered/rejected/candidates.rejected.v1.jsonl",
            "prompts/logs/generation_run_summary.v1.json",
        ],
        "manifest": "outputs/raw_generations/generation_manifest.v1.json",
    },
    "finalize_review_batch": {
        "label": "定稿入库",
        "mode": "script_chain",
        "can_execute": True,
        "scripts": [
            "scripts/05_finalize_pairs.py",
            "scripts/28_generate_dynamic_eval_assets.py",
            "scripts/23_populate_code_completion_overlays.py",
            "scripts/24_populate_model_revision_overlays.py",
            "scripts/25_populate_concept_to_code_overlays.py",
            "scripts/26_populate_model_building_overlays.py",
            "scripts/27_populate_training_analysis_overlays.py",
        ],
        "inputs": [
            "outputs/filtered/accepted/candidates.accepted.v1.jsonl",
            "data/processed/reference_index.v1.jsonl",
            "data/processed/prompt_records.v1.jsonl",
        ],
        "outputs": [
            "results/curated/final_pairs.curated.v1.jsonl",
            "results/curated/exercises_all.curated.v1.jsonl",
            "results/curated/ai_exercises.curated.v1.json",
            "results/curated/blind_mapping.curated.v1.csv",
            "results/curated/reference_solutions.curated.v1.jsonl",
            "results/curated/executable_tests.curated.v1.jsonl",
            "results/curated/dynamic_eval_assets.manifest.v1.json",
        ],
        "manifest": "results/curated/final_pairs.curated.v1.jsonl",
    },
    "open_review_center": {
        "label": "进入审核中心",
        "mode": "navigation",
        "can_execute": False,
        "scripts": ["outputs/system/workflow_state.v1.json"],
        "inputs": ["outputs/system/workflow_state.v1.json"],
        "outputs": ["outputs/system/workflow_state.v1.json"],
        "manifest": "outputs/system/workflow_state.v1.json",
    },
    "approve_candidate": {
        "label": "通过",
        "mode": "state",
        "can_execute": False,
        "scripts": ["outputs/system/workflow_state.v1.json"],
        "inputs": ["outputs/system/workflow_state.v1.json"],
        "outputs": ["outputs/system/workflow_state.v1.json"],
        "manifest": "outputs/system/workflow_state.v1.json",
    },
    "reject_candidate": {
        "label": "驳回",
        "mode": "state",
        "can_execute": False,
        "scripts": ["outputs/system/workflow_state.v1.json"],
        "inputs": ["outputs/system/workflow_state.v1.json"],
        "outputs": ["outputs/system/workflow_state.v1.json"],
        "manifest": "outputs/system/workflow_state.v1.json",
    },
    "request_assets": {
        "label": "提交补资产任务",
        "mode": "script_chain",
        "can_execute": True,
        "scripts": [
            "scripts/23_populate_code_completion_overlays.py",
            "scripts/24_populate_model_revision_overlays.py",
            "scripts/25_populate_concept_to_code_overlays.py",
            "scripts/26_populate_model_building_overlays.py",
            "scripts/27_populate_training_analysis_overlays.py",
        ],
        "inputs": [
            "results/curated/final_pairs.curated.v1.jsonl",
            "outputs/system/workflow_state.v1.json",
        ],
        "outputs": [
            "results/curated/reference_solutions.curated.v1.jsonl",
            "results/curated/executable_tests.curated.v1.jsonl",
            "results/curated/dynamic_eval_assets.manifest.v1.json",
        ],
        "manifest": "results/curated/final_pairs.curated.v1.jsonl",
    },
    "regenerate_candidate": {
        "label": "打回重生成",
        "mode": "state",
        "can_execute": False,
        "scripts": [
            "scripts/01_build_prompts.py",
            "scripts/02_generate_candidates.py",
        ],
        "inputs": [
            "outputs/filtered/rejected/candidates.rejected.v1.jsonl",
            "prompts/v1/master/MP-v1.md",
        ],
        "outputs": [
            "outputs/raw_generations/generations.raw.v1.jsonl",
            "outputs/system/workflow_state.v1.json",
        ],
        "manifest": "outputs/system/workflow_state.v1.json",
    },
    "run_auto_evaluation": {
        "label": "开始自动评测",
        "mode": "script_chain",
        "can_execute": True,
        "scripts": [
            "scripts/06c_validate_reference_solutions.py",
            "scripts/06d_run_functional_correctness.py",
            "scripts/06_compute_auto_metrics.py",
            "scripts/07_statistical_analysis.py",
            "scripts/10_visualize_results.py",
        ],
        "inputs": [
            "results/curated/final_pairs.curated.v1.jsonl",
            "results/curated/reference_solutions.curated.v1.jsonl",
            "results/curated/executable_tests.curated.v1.jsonl",
            "results/curated/dynamic_eval_assets.manifest.v1.json",
        ],
        "outputs": [
            "results/curated/reference_solution_validation.curated.v1.csv",
            "results/curated/exercise_correctness_metrics.curated.v1.csv",
            "results/curated/exercise_metrics.curated.v1.csv",
            "results/curated/statistics/analysis_status.v1.json",
            "results/curated/statistics/ttest.ai_vs_expert.v1.csv",
            "results/curated/statistics/correctness.ttest.ai_vs_expert.v1.csv",
            "results/curated/statistics/pair_similarity.overall.v1.csv",
            "results/curated/figures/bar_ai_vs_expert.png",
            "results/curated/figures/correctness_pass_rate.png",
            "results/curated/figures/pair_similarity_boxplot.png",
        ],
        "manifest": "results/curated/metrics_manifest.curated.v1.json",
    },
    "generate_student_packets": {
        "label": "\u751f\u6210\u5b66\u751f\u53d1\u653e\u5305",
        "mode": "script_chain",
        "can_execute": True,
        "scripts": [
            "scripts/12_prepare_eval_packets.py",
            "scripts/15_prepare_student_distribution_sheet.py",
            "scripts/16_generate_student_qrcodes.py",
            "scripts/17_prepare_student_qrcode_print_sheets.py",
        ],
        "inputs": [
            "results/curated/final_pairs.curated.v1.jsonl",
            "results/curated/blind_mapping.curated.v1.csv",
            "results/curated/exercises_all.curated.v1.jsonl",
        ],
        "outputs": [
            "results/curated/human_eval_packets/packets/student_eval_packet.curated.v1.csv",
            "results/curated/human_eval_packets/packets/student_package_manifest.curated.v1.csv",
            "results/curated/human_eval_packets/distribution/student_distribution_sheet.curated.v1.csv",
            "results/curated/human_eval_packets/distribution/student_qrcode_print_sheets.curated.html",
        ],
        "manifest": "results/curated/human_eval_packets/distribution/student_distribution_sheet.curated.v1.csv",
    },
    "freeze_analysis_input": {
        "label": "冻结分析输入",
        "mode": "script_chain",
        "can_execute": True,
        "scripts": [
            "scripts/17a_export_student_analysis_inputs.py",
            "scripts/18_build_student_analysis_master.py",
        ],
        "inputs": [
            "results/student_subsets/participant_meta_30.csv",
            "results/student_subsets/item_ratings_30.csv",
            "results/student_subsets/batch_feedback_30.csv",
        ],
        "outputs": [
            "results/student_subsets/student_subset_export_manifest.json",
            "results/student_subsets/student_analysis_master_30.csv",
            "results/student_subsets/student_analysis_master_30.manifest.json",
        ],
        "manifest": "results/student_subsets/student_subset_export_manifest.json",
    },
    "generate_analysis_report": {
        "label": "生成分析报告",
        "mode": "script_chain",
        "can_execute": True,
        "scripts": [
            "scripts/19_generate_student_chapter5_outputs.py",
            "scripts/20_generate_student_significance_tables.py",
            "scripts/21_generate_auto_vs_student_correlations.py",
        ],
        "inputs": [
            "results/student_subsets/student_analysis_master_30.csv",
            "results/curated/exercise_metrics.curated.v1.csv",
            "results/curated/pair_similarity_metrics.curated.v1.csv",
        ],
        "outputs": [
            "results/student_subsets/chapter5_outputs/chapter5_outputs_manifest.json",
            "results/student_subsets/chapter5_outputs/tables/significance_outputs_manifest.json",
            "results/student_subsets/chapter5_outputs/tables/correlation_auto_vs_student.manifest.json",
            "outputs/system/report_summary.v1.json",
        ],
        "manifest": "outputs/system/report_summary.v1.json",
    },
    "publish_snapshot": {
        "label": "发布完整快照",
        "mode": "builtin",
        "can_execute": True,
        "scripts": [],
        "inputs": [
            "results/curated/statistics/analysis_status.v1.json",
            "results/student_subsets/chapter5_outputs/chapter5_outputs_manifest.json",
        ],
        "outputs": [
            "outputs/system/snapshots",
            "outputs/system/report_summary.v1.json",
            "outputs/system/workflow_state.v1.json",
        ],
        "manifest": "outputs/system/workflow_state.v1.json",
    },
    "save_settings": {
        "label": "保存系统设置",
        "mode": "state",
        "can_execute": False,
        "scripts": ["outputs/system/workflow_state.v1.json"],
        "inputs": ["outputs/system/workflow_state.v1.json"],
        "outputs": ["outputs/system/workflow_state.v1.json"],
        "manifest": "outputs/system/workflow_state.v1.json",
    },
}



def _abs_paths(values: list[str]) -> list[Path]:
    return [PROJECT_ROOT / value.replace("\\", "/") for value in values if value]



def get_action(action_key: str) -> dict[str, Any]:
    base = ACTION_REGISTRY.get(action_key, {})
    manifest_value = base.get("manifest", "")
    manifest_path = PROJECT_ROOT / str(manifest_value).replace("\\", "/") if manifest_value else None
    return {
        **base,
        "action_key": action_key,
        "label": base.get("label", action_key),
        "mode": base.get("mode", "state"),
        "can_execute": bool(base.get("can_execute", False)),
        "input_paths": _abs_paths(base.get("inputs", [])),
        "output_paths": _abs_paths(base.get("outputs", [])),
        "script_paths": _abs_paths(base.get("scripts", [])),
        "manifest_path": manifest_path,
    }
