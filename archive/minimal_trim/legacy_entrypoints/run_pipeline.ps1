param(
    [string]$Provider = "bailian",
    [string]$Model = "",
    [string]$RunId = "",
    [int]$NumCandidates = 1,
    [double]$Temperature = 0.7,
    [int]$MaxTokens = 0,
    [int]$Limit = 0,
    [string]$Topic = "",
    [string]$Difficulty = "",
    [string]$ExerciseType = "",
    [string]$ReferenceId = "",
    [switch]$SafeMode,
    [int]$SmokeLimit = 1,
    [int]$RandomSeed = 42,
    [switch]$StrictMode,
    [switch]$EnableHeavyMetrics,
    [switch]$SkipHumanEvalMerge,
    [switch]$SkipVisualization,
    [switch]$SkipStatistics
)

$ErrorActionPreference = "Stop"

$venvRoot = Join-Path $PSScriptRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$venvScripts = Join-Path $venvRoot "Scripts"
$venvSitePackages = Join-Path $venvRoot "Lib\site-packages"
$pyvenvCfg = Join-Path $venvRoot "pyvenv.cfg"

if (-not (Test-Path $pyvenvCfg)) {
    throw "Virtual environment metadata not found: $pyvenvCfg"
}

$basePython = (
    Get-Content $pyvenvCfg |
    Where-Object { $_ -like "executable = *" } |
    Select-Object -First 1
)

if (-not $basePython) {
    throw "Unable to find base Python executable in $pyvenvCfg"
}

$python = $basePython.Split("=", 2)[1].Trim()
if (-not (Test-Path $python)) {
    throw "Base Python executable not found: $python"
}

if (-not (Test-Path $venvSitePackages)) {
    throw "Virtual environment site-packages not found: $venvSitePackages"
}

$env:PATH = "$venvScripts;$env:PATH"
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$venvSitePackages;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $venvSitePackages
}

if ($Provider -eq "bailian" -and -not ($env:BAILIAN_API_KEY -or $env:ALIYUN_BAILIAN_API_KEY -or $env:DASHSCOPE_API_KEY)) {
    throw "BAILIAN_API_KEY, ALIYUN_BAILIAN_API_KEY, or DASHSCOPE_API_KEY is not set for this PowerShell process."
}

if (-not $RunId) {
    $RunId = "run-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")
}

$script:ActiveRunId = $RunId

if (-not $Model) {
    $Model = "qwen-plus"
}

if ($MaxTokens -le 0) {
    $MaxTokens = 2200
}

function Remove-PathPattern {
    param(
        [string]$RelativePattern
    )

    $target = Join-Path $PSScriptRoot $RelativePattern
    Get-Item -Path $target -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

function Clear-GeneratedArtifacts {
    $patterns = @(
        "outputs\raw_generations\generations.raw.v1.jsonl",
        "outputs\raw_generations\generation_summary.v1.csv",
        "outputs\raw_generations\generation_manifest.v1.json",
        "outputs\filtered\accepted\candidates.accepted.v1.jsonl",
        "outputs\filtered\rejected\candidates.rejected.v1.jsonl",
        "outputs\filtered\filter_summary.v1.csv",
        "outputs\filtered\filter_summary_by_reason.v1.csv",
        "outputs\filtered\filter_summary_by_category.v1.csv",
        "results\final_pairs.v1.jsonl",
        "results\pair_coverage.v1.csv",
        "results\exercises_all.v1.jsonl",
        "results\exercise_metrics.v1.jsonl",
        "results\exercise_metrics.v1.csv",
        "results\pair_similarity_metrics.v1.jsonl",
        "results\pair_similarity_metrics.v1.csv",
        "results\metrics_manifest.v1.json",
        "results\pipeline_manifest.v1.json",
        "results\auto_metrics.v1.jsonl",
        "results\auto_metrics.v1.csv",
        "results\metrics-run.log",
        "results\statistics\*",
        "results\figures\*",
        "results\tables\*",
        "results\human_eval_merged\*",
        "results\reliability\*",
        "data\ai_generated\accepted\ai_exercises.accepted.v1.json",
        "data\human_eval\blind_mapping.generated.v1.csv",
        "prompts\logs\generation_control_sheet.v1.csv",
        "prompts\logs\generation_run_summary.v1.json"
    )

    foreach ($pattern in $patterns) {
        Remove-PathPattern -RelativePattern $pattern
    }
}

function Invoke-PythonCommand {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw ("Python command failed with exit code {0}: {1}" -f $LASTEXITCODE, ($Arguments -join ' '))
    }
}

function Get-JsonlRowCount {
    param(
        [string]$RelativePath
    )

    $path = Join-Path $PSScriptRoot $RelativePath
    if (-not (Test-Path $path)) {
        return 0
    }

    $lines = Get-Content $path | Where-Object { $_.Trim() }
    return @($lines).Count
}

function Ensure-Directory {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Copy-RelativeArtifact {
    param(
        [string]$RelativePath,
        [string]$ArchiveRoot
    )

    $sourcePath = Join-Path $PSScriptRoot $RelativePath
    if (-not (Test-Path $sourcePath)) {
        return $false
    }

    $destinationPath = Join-Path $ArchiveRoot $RelativePath
    $destinationParent = Split-Path $destinationPath -Parent
    Ensure-Directory -Path $destinationParent

    Copy-Item -Path $sourcePath -Destination $destinationPath -Recurse -Force
    return $true
}

function Archive-RunArtifacts {
    param(
        [string]$ArchiveRunId
    )

    $archiveRoot = Join-Path $PSScriptRoot "results\runs\$ArchiveRunId"
    Ensure-Directory -Path $archiveRoot

    $artifactsToArchive = @(
        "data\processed\prompt_records.v1.jsonl",
        "data\processed\reference_index.v1.jsonl",
        "data\ai_generated\accepted\ai_exercises.accepted.v1.json",
        "data\human_eval\blind_mapping.generated.v1.csv",
        "outputs\raw_generations",
        "outputs\filtered",
        "prompts\logs\generation_control_sheet.v1.csv",
        "prompts\logs\generation_run_summary.v1.json",
        "results\final_pairs.v1.jsonl",
        "results\pair_coverage.v1.csv",
        "results\exercises_all.v1.jsonl",
        "results\exercise_metrics.v1.jsonl",
        "results\exercise_metrics.v1.csv",
        "results\pair_similarity_metrics.v1.jsonl",
        "results\pair_similarity_metrics.v1.csv",
        "results\metrics_manifest.v1.json",
        "results\pipeline_manifest.v1.json",
        "results\statistics",
        "results\figures",
        "results\tables",
        "results\human_eval_merged",
        "results\reliability"
    )

    $copiedArtifacts = @()
    foreach ($relativePath in $artifactsToArchive) {
        if (Copy-RelativeArtifact -RelativePath $relativePath -ArchiveRoot $archiveRoot) {
            $copiedArtifacts += $relativePath
        }
    }

    $archiveManifest = [ordered]@{
        archived_at = (Get-Date).ToString("s")
        run_id = $ArchiveRunId
        provider = $Provider
        model = $Model
        topic_filter = $Topic
        difficulty_filter = $Difficulty
        exercise_type_filter = $ExerciseType
        reference_id_filter = $ReferenceId
        archive_root = $archiveRoot
        copied_artifacts = $copiedArtifacts
    }

    $archiveManifestPath = Join-Path $archiveRoot "archive_manifest.v1.json"
    $archiveManifest | ConvertTo-Json -Depth 4 | Set-Content -Path $archiveManifestPath -Encoding UTF8
    Write-Host "Archived run artifacts -> $archiveRoot"
}

function Write-PipelineManifest {
    param(
        [string]$Status
    )

    $manifest = [ordered]@{
        run_timestamp = (Get-Date).ToString("s")
        run_id = $script:ActiveRunId
        provider = $Provider
        model = $Model
        topic_filter = $Topic
        difficulty_filter = $Difficulty
        exercise_type_filter = $ExerciseType
        reference_id_filter = $ReferenceId
        num_prompts = Get-JsonlRowCount "data\processed\prompt_records.v1.jsonl"
        num_raw_generations = Get-JsonlRowCount "outputs\raw_generations\generations.raw.v1.jsonl"
        num_accepted = Get-JsonlRowCount "outputs\filtered\accepted\candidates.accepted.v1.jsonl"
        num_pairs = Get-JsonlRowCount "results\final_pairs.v1.jsonl"
        num_exercise_metrics = Get-JsonlRowCount "results\exercise_metrics.v1.jsonl"
        num_pair_metrics = Get-JsonlRowCount "results\pair_similarity_metrics.v1.jsonl"
        status = $Status
    }

    $manifestPath = Join-Path $PSScriptRoot "results\pipeline_manifest.v1.json"
    $manifestDir = Split-Path $manifestPath -Parent
    if (-not (Test-Path $manifestDir)) {
        New-Item -ItemType Directory -Path $manifestDir | Out-Null
    }
    $manifest | ConvertTo-Json -Depth 4 | Set-Content -Path $manifestPath -Encoding UTF8
}

function Invoke-Generation {
    param(
        [string]$CurrentRunId,
        [int]$CurrentLimit
    )

    $generateArgs = @(
        "scripts\02_generate_candidates.py",
        "--provider", $Provider,
        "--model", $Model,
        "--run-id", $CurrentRunId,
        "--num-candidates", $NumCandidates,
        "--temperature", $Temperature,
        "--max-tokens", $MaxTokens
    )

    if ($CurrentLimit -gt 0) {
        $generateArgs += @("--limit", $CurrentLimit)
    }

    if ($Topic) {
        $generateArgs += @("--topic", $Topic)
    }
    if ($Difficulty) {
        $generateArgs += @("--difficulty", $Difficulty)
    }
    if ($ExerciseType) {
        $generateArgs += @("--exercise-type", $ExerciseType)
    }

    Invoke-PythonCommand @generateArgs
}

function Invoke-PostGenerationPipeline {
    $metricArgs = @(
        "scripts\06_compute_auto_metrics.py",
        "--compute-expert-metrics",
        "--output-exercise-metrics",
        "--output-pair-metrics"
    )

    if ($EnableHeavyMetrics) {
        $metricArgs += "--enable-heavy-metrics"
    }

    $filterArgs = @("scripts\04_filter_candidates.py")
    if ($StrictMode) {
        $filterArgs += "--strict"
    }

    Invoke-PythonCommand @filterArgs
    Invoke-PythonCommand "scripts\03_log_generation_runs.py"
    Invoke-PythonCommand "scripts\05_finalize_pairs.py" "--random-seed" $RandomSeed "--fail-on-empty-ai"

    $pairsPath = Join-Path $PSScriptRoot "results\final_pairs.v1.jsonl"
    if (-not (Test-Path $pairsPath) -or (Get-Item $pairsPath).Length -le 0) {
        Write-Host "No final pairs were generated. Stopping before metrics and downstream analysis."
        Write-PipelineManifest -Status "no_pairs"
        return
    }

    Invoke-PythonCommand @metricArgs

    if (-not $SkipStatistics) {
        Invoke-PythonCommand "scripts\07_statistical_analysis.py"
    }

    if (-not $SkipHumanEvalMerge) {
        Invoke-PythonCommand "scripts\08_merge_human_ratings.py"
        Invoke-PythonCommand "scripts\09_reliability_analysis.py"

        if (-not $SkipStatistics) {
            Invoke-PythonCommand "scripts\07_statistical_analysis.py"
        }
    }

    if (-not $SkipVisualization) {
        Invoke-PythonCommand "scripts\10_visualize_results.py"
    }

    Write-PipelineManifest -Status "completed"
}

Write-Host "Running pipeline with provider=$Provider model=$Model run_id=$RunId safe_mode=$SafeMode"

$promptArgs = @("scripts\01_build_prompts.py")
if ($Topic) {
    $promptArgs += @("--topic", $Topic)
}
if ($Difficulty) {
    $promptArgs += @("--difficulty", $Difficulty)
}
if ($ExerciseType) {
    $promptArgs += @("--exercise-type", $ExerciseType)
}
if ($ReferenceId) {
    $promptArgs += @("--reference-id", $ReferenceId)
}

Invoke-PythonCommand @promptArgs

if ($SafeMode) {
    $smokeRunId = "$RunId-smoke"
    $script:ActiveRunId = $smokeRunId
    Write-Host "Starting smoke test with run_id=$smokeRunId limit=$SmokeLimit"
    Clear-GeneratedArtifacts
    Invoke-Generation -CurrentRunId $smokeRunId -CurrentLimit $SmokeLimit
    Invoke-PostGenerationPipeline
    Archive-RunArtifacts -ArchiveRunId $smokeRunId
    Write-Host "Smoke test succeeded. SafeMode stops here without starting the full run."
    return
}

$script:ActiveRunId = $RunId
Clear-GeneratedArtifacts
Invoke-Generation -CurrentRunId $RunId -CurrentLimit $Limit
Invoke-PostGenerationPipeline
Archive-RunArtifacts -ArchiveRunId $RunId

Write-Host "Pipeline finished."
