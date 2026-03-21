Additional requirements for exercise_type = "training-analysis":

1. The task must focus on observing, visualizing, interpreting, or comparing model/training behavior.
2. Clearly state the analysis target, such as:
   - training vs validation loss,
   - overfitting behavior,
   - attention patterns,
   - hyperparameter effect,
   - optimization dynamics.
3. Clearly state what variable should be changed or what artifact should be inspected.
4. Clearly state what evidence the student must produce:
   - plot,
   - table,
   - metric comparison,
   - short explanation,
   - or structured observation.
5. Do not expand the task into a full experimental report.
6. The exercise must stay centered on one analytic question.
7. If starter code is relevant, provide only the minimal context needed to run or inspect the behavior.
8. If interpretation is requested, keep it bounded to a short explanation tied to the observed evidence.
9. The expected output must be concrete enough for evaluators to judge completeness.
10. If no direct unit tests are natural, provide explicit checking instructions.
11. Do not require large-scale experimentation, extensive hyperparameter sweeps, or external datasets unless already part of the given context.
12. Keep the exercise feasible within the stated time and learner level.

Additional output expectations for this type:
- `expected_output` should explicitly name the required evidence, such as a plot, table, metric summary, or short interpretation.
- `test_cases` may contain checking instructions instead of strict unit tests.
- `has_code` may be `true` or `false`; if `true`, `starter_code` should be minimal and directly relevant to the analysis target.
- `instruction_text` should make the analytic question easy to identify.