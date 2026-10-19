# Exam generation rules

These rules come from `streamlit/helpers/quick_exam_builder.py` (`_LENGTH_SPEC` and `_build_exam_prompts`). Expo uses the same values through `src/lib/exam-generation-rules.ts`.

| Length | Maximum exercise types / sections | Questions per section |
| --- | ---: | ---: |
| Short | 3 | 4–5 |
| Medium | 4 | 5–7 |
| Long | 5 | 6–10 |

- Each selected exercise type creates one section. Teachers may select fewer than the maximum, but at least one type is required.
- The order shown in the selector is the intended section order. Adding a type puts it last; the up and down controls change that order.
- Exam length changes **both** the maximum number of sections and the number of questions in each section. It does not require exactly 3, 4, or 5 sections.
- If a teacher changes to a shorter length with too many selected types, the form shows an error and disables generation until the selection fits. The API also rejects an over-limit or duplicate selection instead of silently omitting types.
- Program-topic exercise suggestions are defaults, not mandatory choices. Teachers can replace or reorder them while the subject, topic, learner stage, and level remain anchored to the program.
- The same ordered selector and limits apply in the teacher generator and Explorer.

The AI prompt requests sections in the selected order and the corresponding question range. As with any generated assessment, teachers should review item quality and difficulty before assigning it.
