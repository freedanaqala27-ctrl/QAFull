Additional requirements for exercise_type = "code completion":

1. The exercise must center on completing a missing function, method, or bounded code block.
2. Provide starter code with a clearly marked TODO region.
3. Clearly define:
   - input format or tensor shapes,
   - expected return value or output behavior,
   - any constraints on implementation.
4. Keep the implementation local and bounded:
   - do not expand into a full training pipeline,
   - do not ask for dataset download,
   - do not require a complete end-to-end project.
5. If the task involves tensors, state the expected shapes or dimensions.
6. If relevant, specify numerical assumptions such as padding, stride, mask handling, broadcasting, or activation behavior.
7. Include 2-4 test cases, sanity checks, or explicit validation conditions.
8. The task should be solvable in one function or one small module.
9. The starter code must be syntactically valid Python.
10. Avoid hidden dependencies and avoid requiring helper functions that are not shown or described.
11. The TODO region must be specific enough that an evaluator can tell exactly what the student is expected to complete.
12. If a framework is used, keep imports and helper definitions minimal and self-contained.
13. Do not leave critical variable definitions implicit.
14. Prefer starter code that can be parsed statically even if it is intentionally incomplete.

Additional output expectations for this type:
- `has_code` should normally be `true`.
- `starter_code` should contain a local TODO marker such as `# TODO: ...`.
- `expected_output` should state what the completed function/block must return or do.
- `test_cases` should include concrete functional checks, shape checks, or sanity conditions.