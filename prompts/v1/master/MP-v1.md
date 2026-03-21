You are generating ONE deep learning programming exercise for a research dataset that compares AI-generated exercises with expert-created exercises.

Your task is to produce a single exercise that is:
- pedagogically useful,
- structurally complete,
- comparable to a matched expert exercise,
- limited to one bounded task,
- suitable for both automatic evaluation and human rating.

Reference control variables:
- reference_exercise_id: {REFERENCE_EXERCISE_ID}
- topic: {TOPIC}
- difficulty: {DIFFICULTY}
- exercise_type: {EXERCISE_TYPE}
- programming_language: Python
- framework: {FRAMEWORK}
- target_learner_level: {TARGET_LEARNER_LEVEL}
- estimated_time_minutes: {ESTIMATED_TIME_MINUTES}
- learning_objectives: {LEARNING_OBJECTIVES}
- prerequisite_concepts: {PREREQUISITE_CONCEPTS}
- course_context: {COURSE_CONTEXT}

Generation constraints:
1. Match the reference exercise in topic, difficulty, exercise type, pedagogical scope, and expected effort.
2. Do NOT copy the reference title, wording, sentence structure, or distinctive phrasing.
3. Generate a single bounded exercise unit, not a project and not a multi-part assignment.
4. Keep the exercise focused on one central learning task only.
5. Use clear instructional language suitable for students in a deep learning course.
6. Explicitly include:
   - task goal,
   - required behavior or expected output,
   - constraints,
   - success criteria,
   - assumed background knowledge,
   - expected submission artifact.
7. Use necessary domain terminology, but avoid excessive jargon outside the target topic.
8. If code is applicable, provide syntactically valid starter code with clear variable names.
9. If tests are applicable, provide 2-4 concise test cases or checking instructions.
10. Do not require external files, hidden datasets, paid tools, or long-running experiments unless explicitly specified.
11. Keep the result self-contained and suitable for storage in a JSON-based exercise dataset.
12. Keep granularity comparable to a typical expert exercise in this dataset; do not expand the task into a mini-lesson or research project.

Output rules:
- Return JSON only.
- Do not add explanations before or after the JSON.
- Preserve the exact key names below.
- If an optional field is not applicable, return an empty string "" or empty array [].
- Do not invent metadata that cannot be justified by the task itself.
- Keep `topic`, `difficulty`, and `exercise_type` consistent with the provided control variables.
- Use `programming_language: "Python"` exactly.
- If `has_code` is true, `starter_code` must not be empty.
- If the task is analysis-oriented and tests are not naturally applicable, provide concrete checking instructions in `test_cases` or make the expected evidence explicit in `expected_output`.

Return this JSON structure exactly:

{
  "title": "",
  "topic": "",
  "difficulty": "",
  "exercise_type": "",
  "instruction_text": "",
  "programming_language": "Python",
  "framework": "",
  "has_code": true,
  "starter_code": "",
  "constraints": [],
  "expected_output": "",
  "test_cases": [],
  "learning_objectives": [],
  "prerequisite_concepts": [],
  "keywords": [],
  "estimated_time_minutes": 0,
  "target_learner_level": "",
  "course_context": "",
  "notes": ""
}

Additional field guidance:
- `title`: a concise original exercise title.
- `instruction_text`: the main task statement written for a student.
- `constraints`: explicit implementation or analysis constraints.
- `expected_output`: what the student must return, report, submit, or demonstrate.
- `test_cases`: 2-4 short validation items, sanity checks, or checking instructions when applicable.
- `learning_objectives`: concrete skills or concepts practiced in this exercise.
- `prerequisite_concepts`: assumed prior knowledge needed to attempt the task.
- `keywords`: short topic-relevant terms useful for indexing and analysis.
- `notes`: optional implementation note for dataset storage; use "" if not needed.

Final self-check before answering:
- The exercise is NOT project-scoped.
- The topic is coherent and singular.
- The wording is original.
- The structure is complete enough for automatic scoring.
- The task is comparable in granularity to the reference exercise.