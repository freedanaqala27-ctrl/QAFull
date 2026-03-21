Additional requirements for exercise_type = "model revision":

1. Start from an existing baseline model, baseline training loop, or given implementation context.
2. Ask the student to modify exactly one targeted design factor, such as:
   - regularization,
   - dropout placement,
   - normalization choice,
   - loss component,
   - one architectural block.
3. Preserve the rest of the setup unless explicitly stated otherwise.
4. Require the student to compare the revised version with the baseline.
5. Clearly state:
   - what must be changed,
   - what must remain unchanged,
   - what evidence should be reported.
6. Expected output should include:
   - revised code or revised model component,
   - and a concise comparison outcome or explanation.
7. Do not turn the exercise into a full ablation study or research report.
8. If quantitative comparison is requested, specify the metric or observation target.
9. Keep the task narrow enough to finish within one notebook section or one script segment.
10. Avoid changes that silently alter multiple experimental factors at once.
11. The exercise should focus on one interpretable revision decision.
12. If code is provided, the baseline context must be sufficient to understand what is being revised.

Additional output expectations for this type:
- `instruction_text` must clearly identify the baseline and the required revision.
- `constraints` should explicitly state what must remain unchanged.
- `expected_output` should require both the revised artifact and a short comparison result or explanation.
- `test_cases` may be functional checks, comparison checks, or structured evaluation instructions.