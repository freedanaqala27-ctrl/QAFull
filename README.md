# PythonProjectQA

Quality Assessment of LLM-Generated Deep Learning Programming Exercises: A Multi-Criteria Analysis

## Project Overview

This repository contains the code, data pipelines, survey tools, and analysis outputs for a thesis project comparing AI-generated deep learning programming exercises with expert-created reference exercises.

The current project focus is:

- automatic quality evaluation of curated exercise pairs
- student survey analysis
- Chapter 5 style statistical outputs and figures

The expert-rating branch of the workflow has been archived and is not part of the current main analysis path.

## Main Workflow

The repository is now organized around two formal result tracks:

- [`results/curated`](D:/Downloads/PythonProjectQA/results/curated)
  - formal curated exercise dataset
  - automatic metrics
  - curated statistics
  - curated figures and tables
  - human evaluation packet materials
- [`results/student_subsets`](D:/Downloads/PythonProjectQA/results/student_subsets)
  - cleaned student subset data
  - merged student analysis master table
  - Chapter 5 tables and figures

Historical pipeline outputs, expert-layer artifacts, and deployment snapshots have been moved to [`archive`](D:/Downloads/PythonProjectQA/archive).

## Key Entry Points

- [`survey/student_app.py`](D:/Downloads/PythonProjectQA/survey/student_app.py)
  - student-facing survey interface
- [`survey/student_survey_db.py`](D:/Downloads/PythonProjectQA/survey/student_survey_db.py)
  - student survey storage layer
- [`scripts/06_compute_auto_metrics.py`](D:/Downloads/PythonProjectQA/scripts/06_compute_auto_metrics.py)
  - automatic metric computation entry point for curated exercises
- [`scripts/18_build_student_analysis_master.py`](D:/Downloads/PythonProjectQA/scripts/18_build_student_analysis_master.py)
  - student-analysis master table entry point

Former root-level research entry points such as `app.py` and `run_pipeline.ps1` have been
archived under [`archive/minimal_trim/legacy_entrypoints`](D:/Downloads/PythonProjectQA/archive/minimal_trim/legacy_entrypoints).

## Scripts by Stage

### Data preparation and generation

- [`scripts/00_normalize_validate_dataset.py`](D:/Downloads/PythonProjectQA/scripts/00_normalize_validate_dataset.py)
- [`scripts/01_build_prompts.py`](D:/Downloads/PythonProjectQA/scripts/01_build_prompts.py)
- [`scripts/02_generate_candidates.py`](D:/Downloads/PythonProjectQA/scripts/02_generate_candidates.py)
- [`scripts/03_log_generation_runs.py`](D:/Downloads/PythonProjectQA/scripts/03_log_generation_runs.py)
- [`scripts/04_filter_candidates.py`](D:/Downloads/PythonProjectQA/scripts/04_filter_candidates.py)
- [`scripts/05_finalize_pairs.py`](D:/Downloads/PythonProjectQA/scripts/05_finalize_pairs.py)

These are preserved for reproducibility. They are not the main active path for the current thesis write-up.

### Automatic metrics and curated analysis

- [`scripts/06_compute_auto_metrics.py`](D:/Downloads/PythonProjectQA/scripts/06_compute_auto_metrics.py)
- [`scripts/07_statistical_analysis.py`](D:/Downloads/PythonProjectQA/scripts/07_statistical_analysis.py)
- [`scripts/10_visualize_results.py`](D:/Downloads/PythonProjectQA/scripts/10_visualize_results.py)
- [`scripts/_shared_io.py`](D:/Downloads/PythonProjectQA/scripts/_shared_io.py)

Recommended mode:

- run with curated inputs
- use outputs under [`results/curated`](D:/Downloads/PythonProjectQA/results/curated)

### Human-evaluation material preparation

- [`scripts/12_prepare_eval_packets.py`](D:/Downloads/PythonProjectQA/scripts/12_prepare_eval_packets.py)
- [`scripts/15_prepare_student_packets_zh_cn.py`](D:/Downloads/PythonProjectQA/scripts/15_prepare_student_packets_zh_cn.py)
- [`scripts/16_generate_student_qrcodes.py`](D:/Downloads/PythonProjectQA/scripts/16_generate_student_qrcodes.py)
- [`scripts/17_prepare_student_qrcode_print_sheets.py`](D:/Downloads/PythonProjectQA/scripts/17_prepare_student_qrcode_print_sheets.py)

### Student survey analysis

- [`scripts/17a_export_student_analysis_inputs.py`](D:/Downloads/PythonProjectQA/scripts/17a_export_student_analysis_inputs.py)
  - reproducible bridge from survey raw exports / Supabase tables to formal `*_30.csv` analysis inputs
- [`scripts/18_build_student_analysis_master.py`](D:/Downloads/PythonProjectQA/scripts/18_build_student_analysis_master.py)
- [`scripts/19_generate_student_chapter5_outputs.py`](D:/Downloads/PythonProjectQA/scripts/19_generate_student_chapter5_outputs.py)
- [`scripts/20_generate_student_significance_tables.py`](D:/Downloads/PythonProjectQA/scripts/20_generate_student_significance_tables.py)
- [`scripts/21_generate_auto_vs_student_correlations.py`](D:/Downloads/PythonProjectQA/scripts/21_generate_auto_vs_student_correlations.py)

These scripts produce the current student-facing analysis outputs used for the thesis.

Recommended command chain for the current student-analysis mainline:

```powershell
.\.venv\Scripts\python.exe scripts\17a_export_student_analysis_inputs.py --fetch-from-db
.\.venv\Scripts\python.exe scripts\18_build_student_analysis_master.py
.\.venv\Scripts\python.exe scripts\19_generate_student_chapter5_outputs.py
.\.venv\Scripts\python.exe scripts\20_generate_student_significance_tables.py
.\.venv\Scripts\python.exe scripts\21_generate_auto_vs_student_correlations.py
```

If you are reproducing the current frozen subset from existing CSVs rather than pulling from Supabase, run:

```powershell
.\.venv\Scripts\python.exe scripts\17a_export_student_analysis_inputs.py `
  --meta-csv results\student_subsets\participant_meta_30.csv `
  --item-csv results\student_subsets\item_ratings_30.csv `
  --batch-csv results\student_subsets\batch_feedback_30.csv
```

### Legacy / optional scripts

- [`scripts/legacy/08_merge_human_ratings.py`](D:/Downloads/PythonProjectQA/scripts/legacy/08_merge_human_ratings.py)
- [`scripts/legacy/09_reliability_analysis.py`](D:/Downloads/PythonProjectQA/scripts/legacy/09_reliability_analysis.py)
- [`scripts/legacy/11_curate_archived_runs.py`](D:/Downloads/PythonProjectQA/scripts/legacy/11_curate_archived_runs.py)
- [`scripts/legacy/13_prepare_human_eval_materials.py`](D:/Downloads/PythonProjectQA/scripts/legacy/13_prepare_human_eval_materials.py)
- [`scripts/legacy/14_prepare_wjx_question_bank.py`](D:/Downloads/PythonProjectQA/scripts/legacy/14_prepare_wjx_question_bank.py)
- [`scripts/legacy/22_restructure_human_eval_packets.py`](D:/Downloads/PythonProjectQA/scripts/legacy/22_restructure_human_eval_packets.py)

These are retained for traceability, historical material generation, or one-off maintenance,
but they are not part of the current thesis mainline.

## Prompt Templates

The active prompt set is under:

- [`prompts/v1`](D:/Downloads/PythonProjectQA/prompts/v1)

Key files:

- [`prompts/v1/master/MP-v1.md`](D:/Downloads/PythonProjectQA/prompts/v1/master/MP-v1.md)
  - master prompt defining research context, control variables, comparability constraints, and JSON-only output requirements
- [`prompts/v1/subtemplates/CC-v1.md`](D:/Downloads/PythonProjectQA/prompts/v1/subtemplates/CC-v1.md)
  - `code completion` constraints
- [`prompts/v1/subtemplates/MB-v1.md`](D:/Downloads/PythonProjectQA/prompts/v1/subtemplates/MB-v1.md)
  - `model building` constraints
- [`prompts/v1/subtemplates/MR-v1.md`](D:/Downloads/PythonProjectQA/prompts/v1/subtemplates/MR-v1.md)
  - `model revision` constraints
- [`prompts/v1/subtemplates/TA-v1.md`](D:/Downloads/PythonProjectQA/prompts/v1/subtemplates/TA-v1.md)
  - `training-analysis` constraints
- [`prompts/v1/logs/generation_control_sheet.v1.csv`](D:/Downloads/PythonProjectQA/prompts/v1/logs/generation_control_sheet.v1.csv)
  - run-level control sheet for prompt and candidate generation

Prompt rendering logic:

1. Start from `master/MP-v1.md`
2. Fill the reference-specific placeholders
3. Append exactly one subtemplate based on normalized exercise type
4. Keep the final output JSON-only and schema-compatible

## Recommended Outputs to Use in the Thesis

### Automatic metrics and formal curated outputs

Use files under:

- [`results/curated`](D:/Downloads/PythonProjectQA/results/curated)

Especially:

- [`exercise_metrics.curated.v1.csv`](D:/Downloads/PythonProjectQA/results/curated/exercise_metrics.curated.v1.csv)
- [`pair_similarity_metrics.curated.v1.csv`](D:/Downloads/PythonProjectQA/results/curated/pair_similarity_metrics.curated.v1.csv)
- [`metrics_manifest.curated.v1.json`](D:/Downloads/PythonProjectQA/results/curated/metrics_manifest.curated.v1.json)
- [`statistics`](D:/Downloads/PythonProjectQA/results/curated/statistics)
- [`figures`](D:/Downloads/PythonProjectQA/results/curated/figures)
- [`tables`](D:/Downloads/PythonProjectQA/results/curated/tables)

### Student analysis outputs

Use files under:

- [`results/student_subsets`](D:/Downloads/PythonProjectQA/results/student_subsets)

Especially:

- [`student_analysis_master_30.csv`](D:/Downloads/PythonProjectQA/results/student_subsets/student_analysis_master_30.csv)
- [`chapter5_outputs`](D:/Downloads/PythonProjectQA/results/student_subsets/chapter5_outputs)

## Archived Content

Archived content has been moved to:

- [`archive/legacy_pipeline`](D:/Downloads/PythonProjectQA/archive/legacy_pipeline)
- [`archive/expert_layer`](D:/Downloads/PythonProjectQA/archive/expert_layer)
- [`archive/legacy_default_outputs`](D:/Downloads/PythonProjectQA/archive/legacy_default_outputs)
- [`archive/deploy_snapshot`](D:/Downloads/PythonProjectQA/archive/deploy_snapshot)

These are kept for traceability, but should not be treated as the primary source of thesis results.

## Environment

Main Python environments:

- [`requirements.txt`](D:/Downloads/PythonProjectQA/requirements.txt)
  - main research environment for analysis, metrics, and thesis outputs
- [`survey/requirements.txt`](D:/Downloads/PythonProjectQA/survey/requirements.txt)
  - minimal environment for the student survey app

Student survey database schema:

- [`docs/supabase_student_survey_schema.sql`](D:/Downloads/PythonProjectQA/docs/supabase_student_survey_schema.sql)

## Recommended Working Order

For the current thesis workflow, the recommended order is:

1. Use the curated exercise outputs in [`results/curated`](D:/Downloads/PythonProjectQA/results/curated)
2. Export or reproduce the formal student subset inputs with [`scripts/17a_export_student_analysis_inputs.py`](D:/Downloads/PythonProjectQA/scripts/17a_export_student_analysis_inputs.py)
3. Build the student master table in [`results/student_subsets/student_analysis_master_30.csv`](D:/Downloads/PythonProjectQA/results/student_subsets/student_analysis_master_30.csv)
4. Use Chapter 5 tables and figures in [`results/student_subsets/chapter5_outputs`](D:/Downloads/PythonProjectQA/results/student_subsets/chapter5_outputs)
5. Treat archived directories as historical references only

## Notes

- The expert-rating analysis path is currently out of scope for the main thesis write-up.
- The original generation pipeline is preserved, but it is no longer the primary active workflow.
- The repository has been intentionally simplified so that the active thesis path is easy to identify from the directory structure.
- The student survey implementation now lives under [`survey`](D:/Downloads/PythonProjectQA/survey); root-level wrappers have been removed.
- Script grouping details and prompt-set notes have been consolidated into this root README so the repository keeps a single top-level project guide.
- Legacy and non-mainline scripts are grouped under [`scripts/legacy`](D:/Downloads/PythonProjectQA/scripts/legacy).


