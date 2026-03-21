Additional requirements for exercise_type = "model building":

1. The task must require building a bounded model for a clearly specified learning problem.
2. Explicitly state:
   - the model goal,
   - the required architecture components,
   - the training setup if relevant,
   - the evaluation target.
3. Keep the task constrained:
   - no open-ended architecture search,
   - no full research workflow,
   - no requirement to compare many unrelated models.
4. If data is needed, either:
   - provide a small synthetic setting in the prompt, or
   - refer to an already-available dataset/context in a self-contained way.
5. The instruction must tell the student what artifact to submit:
   - model definition,
   - completed training code,
   - evaluation result,
   - or a short explanation of design choices.
6. If starter code is provided, it should define only the skeleton needed for the exercise.
7. If evaluation is required, state the expected metric or behavior clearly.
8. Include concise checking instructions or test cases whenever possible.
9. The task should remain feasible within the stated learner level and estimated time.
10. Do not turn the exercise into an architecture-comparison project.
11. Keep the implementation target narrow enough to fit in one script section or one notebook section.
12. If code is included, prefer minimal but runnable scaffolding over lengthy boilerplate.

Additional output expectations for this type:
- `has_code` may be `true` or `false`, but set it deliberately.
- If `has_code` is `true`, `starter_code` should provide only the relevant scaffold.
- `expected_output` should clearly state what the student must submit or demonstrate.
- `test_cases` should include checking instructions, target behavior, or concise evaluation checks when natural unit tests are not appropriate.