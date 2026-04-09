$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$outputDir = Join-Path $projectRoot "docs\thesis_revision_materials"
$null = New-Item -ItemType Directory -Force -Path $outputDir

$masterCsv = Join-Path $projectRoot "results\student_subsets\student_analysis_master_30.csv"
$pairsJsonl = Join-Path $projectRoot "results\curated\final_pairs.curated.v1.jsonl"
$generationManifest = Join-Path $projectRoot "outputs\raw_generations\generation_manifest.v1.json"
$generationSummary = Join-Path $projectRoot "outputs\raw_generations\generation_summary.v1.csv"
$packetDistribution = Join-Path $projectRoot "results\curated\human_eval_packets\distribution\student_distribution_sheet.curated.v1.csv"

function Convert-LineToJsonSafely {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Line
    )

    try {
        Add-Type -AssemblyName System.Web.Extensions
        $serializer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
        $serializer.MaxJsonLength = 67108864
        return ConvertTo-PSObject -InputObject ($serializer.DeserializeObject($Line))
    } catch {
        return $null
    }
}

function ConvertTo-PSObject {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject
    )

    if ($InputObject -is [System.Collections.IDictionary]) {
        $result = [ordered]@{}
        foreach ($key in $InputObject.Keys) {
            $result[$key] = ConvertTo-PSObject -InputObject $InputObject[$key]
        }
        return [pscustomobject]$result
    }

    if ($InputObject -is [System.Collections.IEnumerable] -and -not ($InputObject -is [string])) {
        $items = @()
        foreach ($item in $InputObject) {
            $items += ConvertTo-PSObject -InputObject $item
        }
        return $items
    }

    return $InputObject
}

function Join-UniqueText {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Values
    )

    $clean = @()
    foreach ($value in $Values) {
        if ($null -eq $value) {
            continue
        }
        $text = ([string]$value).Trim()
        if (-not $text) {
            continue
        }
        if ($clean -notcontains $text) {
            $clean += $text
        }
    }
    return ($clean -join "; ")
}

function Convert-GroupToRows {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Rows,
        [Parameter(Mandatory = $true)]
        [string]$Field,
        [Parameter(Mandatory = $true)]
        [string]$Category,
        [Parameter(Mandatory = $true)]
        [int]$Denominator
    )

    return $Rows |
        Group-Object $Field |
        Sort-Object Count -Descending |
        ForEach-Object {
            [pscustomobject]@{
                category = $Category
                item = [string]$_.Name
                count = $_.Count
                percentage = [math]::Round(($_.Count / $Denominator) * 100, 2)
            }
        }
}

$masterRows = Import-Csv $masterCsv
$validRows = $masterRows | Where-Object {
    $_.attention_check_passed -eq "True" -and $_.participant_fast_flag_under_180s -ne "True"
}

$validParticipants = $validRows |
    Group-Object participant_id |
    ForEach-Object { $_.Group[0] }

$selectedPairIds = $validRows |
    Where-Object { $_.source_type -eq "AI" } |
    Select-Object -ExpandProperty pair_id -Unique |
    Sort-Object

$pairIdLookup = @{}
foreach ($pairId in $selectedPairIds) {
    $pairIdLookup[$pairId] = $true
}

$selectedPairs = @()
$pairPattern = ($selectedPairIds | ForEach-Object { [regex]::Escape($_) }) -join "|"
foreach ($match in (Select-String -Path $pairsJsonl -Pattern $pairPattern)) {
    $parsed = Convert-LineToJsonSafely -Line $match.Line
    if ($null -ne $parsed) {
        $selectedPairs += $parsed
    }
}

$selectedPairs = $selectedPairs | Sort-Object reference_exercise_id

$expertSourceRows = foreach ($pair in $selectedPairs) {
    $reference = $pair.reference_payload
    $knowledgePoints = Join-UniqueText -Values @(
        @($reference.learning_objectives)
        @($reference.prerequisite_concepts)
    )

    [pscustomobject]@{
        pair_id = [string]$pair.pair_id
        reference_exercise_id = [string]$pair.reference_exercise_id
        topic = [string]$pair.topic
        difficulty = [string]$pair.difficulty
        exercise_type = [string]$pair.reference_exercise_type_original
        source_subtype = [string]$reference.source_subtype
        source_title = [string]$reference.title
        source_locator = Join-UniqueText -Values @(
            [string]$reference.source_url,
            [string]$pair.reference_source,
            [string]$reference.course_context
        )
        course_context = [string]$reference.course_context
        knowledge_points = $knowledgePoints
    }
}

$expertSourceCsv = Join-Path $outputDir "expert_source_statistics.csv"
$expertSourceRows | Export-Csv -NoTypeInformation -Encoding UTF8 $expertSourceCsv

$topicSummaryRows = @(
    foreach ($group in ($expertSourceRows | Group-Object topic | Sort-Object Name)) {
        [pscustomobject]@{
            category = "topic"
            item = $group.Name
            count = $group.Count
        }
    }
    foreach ($group in ($expertSourceRows | Group-Object difficulty | Sort-Object Name)) {
        [pscustomobject]@{
            category = "difficulty"
            item = $group.Name
            count = $group.Count
        }
    }
    foreach ($group in ($expertSourceRows | Group-Object exercise_type | Sort-Object Name)) {
        [pscustomobject]@{
            category = "exercise_type"
            item = $group.Name
            count = $group.Count
        }
    }
    foreach ($group in ($expertSourceRows | Group-Object source_subtype | Sort-Object Name)) {
        [pscustomobject]@{
            category = "source_subtype"
            item = $group.Name
            count = $group.Count
        }
    }
)

$topicSummaryCsv = Join-Path $outputDir "expert_topic_distribution.csv"
$topicSummaryRows | Export-Csv -NoTypeInformation -Encoding UTF8 $topicSummaryCsv

$submittedParticipantCount = ($masterRows | Where-Object { $_.submitted_at } | Select-Object -ExpandProperty participant_id -Unique).Count
$rawParticipantCount = ($masterRows | Select-Object -ExpandProperty participant_id -Unique).Count
$validParticipantCount = $validParticipants.Count
$excludedParticipants = $masterRows |
    Group-Object participant_id |
    ForEach-Object { $_.Group[0] } |
    Where-Object {
        $_.attention_check_passed -ne "True" -or $_.participant_fast_flag_under_180s -eq "True"
    } |
    Sort-Object participant_id

$distributionRows = Import-Csv $packetDistribution
$preparedParticipantSlots = $distributionRows.Count
$preparedPackages = ($distributionRows | Select-Object -ExpandProperty package -Unique).Count

$durationStats = $validParticipants | ForEach-Object { [double]$_.response_duration_seconds }
$meanDuration = [math]::Round((($durationStats | Measure-Object -Average).Average), 2)
$minDuration = [math]::Round((($durationStats | Measure-Object -Minimum).Minimum), 2)
$maxDuration = [math]::Round((($durationStats | Measure-Object -Maximum).Maximum), 2)

$studentOverviewRows = @(
    [pscustomobject]@{ metric = "prepared_participant_slots"; value = $preparedParticipantSlots; notes = "distribution sheet rows" }
    [pscustomobject]@{ metric = "prepared_packages"; value = $preparedPackages; notes = "unique packages in distribution sheet" }
    [pscustomobject]@{ metric = "submitted_participants"; value = $submittedParticipantCount; notes = "unique participant_id with submitted_at" }
    [pscustomobject]@{ metric = "valid_participants"; value = $validParticipantCount; notes = "attention_check_passed=True and participant_fast_flag_under_180s!=True" }
    [pscustomobject]@{ metric = "excluded_participants"; value = $excludedParticipants.Count; notes = (($excludedParticipants | ForEach-Object { $_.participant_id }) -join ", ") }
    [pscustomobject]@{ metric = "mean_response_duration_seconds"; value = $meanDuration; notes = "min=$minDuration; max=$maxDuration" }
    [pscustomobject]@{ metric = "raw_participants_in_master"; value = $rawParticipantCount; notes = "unique participant_id in student_analysis_master_30.csv" }
)

$studentOverviewCsv = Join-Path $outputDir "student_sample_overview.csv"
$studentOverviewRows | Export-Csv -NoTypeInformation -Encoding UTF8 $studentOverviewCsv

$studentProfileRows = @()
$studentProfileRows += Convert-GroupToRows -Rows $validParticipants -Field "study_stage" -Category "study_stage" -Denominator $validParticipantCount
$studentProfileRows += Convert-GroupToRows -Rows $validParticipants -Field "programming_background" -Category "programming_background" -Denominator $validParticipantCount
$studentProfileRows += Convert-GroupToRows -Rows $validParticipants -Field "python_familiarity" -Category "python_familiarity" -Denominator $validParticipantCount
$studentProfileRows += Convert-GroupToRows -Rows $validParticipants -Field "framework_familiarity" -Category "framework_familiarity" -Denominator $validParticipantCount
$studentProfileRows += Convert-GroupToRows -Rows $validParticipants -Field "dl_course_taken" -Category "dl_course_taken" -Denominator $validParticipantCount

$topicCountsMap = @{}
foreach ($participant in $validParticipants) {
    foreach ($topic in ([string]$participant.familiar_topics -split ";")) {
        $clean = $topic.Trim()
        if (-not $clean) {
            continue
        }
        if (-not $topicCountsMap.ContainsKey($clean)) {
            $topicCountsMap[$clean] = 0
        }
        $topicCountsMap[$clean]++
    }
}

foreach ($key in ($topicCountsMap.Keys | Sort-Object { -1 * $topicCountsMap[$_] }, { $_ })) {
    $studentProfileRows += [pscustomobject]@{
        category = "familiar_topics_multi_select"
        item = $key
        count = $topicCountsMap[$key]
        percentage = [math]::Round(($topicCountsMap[$key] / $validParticipantCount) * 100, 2)
    }
}

$studentProfileCsv = Join-Path $outputDir "student_profile_statistics.csv"
$studentProfileRows | Export-Csv -NoTypeInformation -Encoding UTF8 $studentProfileCsv

$generationManifestDoc = Get-Content $generationManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$generationSummaryRow = Import-Csv $generationSummary | Select-Object -First 1

$casePairIds = @(
    "PAIR-CURATED-MIT-01",
    "PAIR-CURATED-OPT-02",
    "PAIR-CURATED-KER-04"
)

$caseRows = foreach ($casePairId in $casePairIds) {
    $pair = $selectedPairs | Where-Object { $_.pair_id -eq $casePairId } | Select-Object -First 1
    if ($null -eq $pair) {
        continue
    }

    [pscustomobject]@{
        pair_id = [string]$pair.pair_id
        topic = [string]$pair.topic
        difficulty = [string]$pair.difficulty
        exercise_type = [string]$pair.reference_exercise_type_original
        expert_title = [string]$pair.reference_payload.title
        expert_source = Join-UniqueText -Values @(
            [string]$pair.reference_payload.source_url,
            [string]$pair.reference_source,
            [string]$pair.reference_payload.course_context
        )
        expert_instruction = [string]$pair.reference_payload.instruction_text
        ai_title = [string]$pair.ai_payload.title
        ai_model_name = [string]$pair.model_name
        ai_provider = [string]$pair.provider
        ai_generation_id = [string]$pair.generation_id
        ai_instruction = [string]$pair.ai_payload.instruction_text
    }
}

$caseCsv = Join-Path $outputDir "case_appendix_materials.csv"
$caseRows | Export-Csv -NoTypeInformation -Encoding UTF8 $caseCsv

$summary = [pscustomobject]@{
    generated_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    model_provider = [string]$generationManifestDoc.provider
    model_name = [string]$generationManifestDoc.model
    generation_run_id = [string]$generationManifestDoc.run_id
    generation_api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    prepared_participant_slots = $preparedParticipantSlots
    submitted_participants = $submittedParticipantCount
    valid_participants = $validParticipantCount
    excluded_participants = (($excludedParticipants | ForEach-Object { $_.participant_id }) -join ", ")
    valid_pair_count = $selectedPairIds.Count
    expert_source_csv = $expertSourceCsv
    expert_topic_distribution_csv = $topicSummaryCsv
    student_sample_overview_csv = $studentOverviewCsv
    student_profile_statistics_csv = $studentProfileCsv
    case_appendix_materials_csv = $caseCsv
}

$summaryJson = Join-Path $outputDir "revision_materials_summary.json"
$summary | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $summaryJson

Write-Host "Generated:"
Write-Host " - $expertSourceCsv"
Write-Host " - $topicSummaryCsv"
Write-Host " - $studentOverviewCsv"
Write-Host " - $studentProfileCsv"
Write-Host " - $caseCsv"
Write-Host " - $summaryJson"
