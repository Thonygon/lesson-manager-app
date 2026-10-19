import source from './source-exam-guidance.json';
import { examLengthRule } from '../lib/exam-generation-rules';

// Source: streamlit/helpers/quick_exam_builder.py:_build_exam_prompts.
export type ExamPromptInput = { subject: string; topic: string; learnerStage: string; levelOrBand: string; examTitle: string; examLength: string; exerciseTypes: string[]; planLanguage: string; studentMaterialLanguage: string; instructions?: string; studentProfile?: Record<string, unknown>; studentProfileBlock?: string; programContextBlock?: string };
const TYPES: Record<string, string[]> = { core: ['multiple_choice', 'true_false', 'matching', 'fill_in_blank', 'short_answer'], language: ['reading_comprehension', 'vocabulary', 'sentence_transformation', 'error_correction', 'writing_prompt'], math: ['problem_solving', 'equation_solving', 'show_your_work', 'table_interpretation', 'word_problems'], science: ['data_analysis', 'classification', 'process_explanation', 'hypothesis_and_conclusion', 'diagram_questions'], music: ['theory_questions', 'symbol_identification', 'rhythm_counting', 'terminology', 'composer_period_matching'] };
const typeGroup = Object.fromEntries(Object.entries(TYPES).flatMap(([group, values]) => values.map((value) => [value, group])));
const starts: Record<string, string> = { language: 'Start with accessible recognition/comprehension before moving into controlled production and extended output.', math: 'Start with accessible fluency or recognition before moving into procedural reasoning and multi-step problem solving.', science: 'Start with accessible knowledge checks before moving into explanation, evidence use, and interpretation.', music: 'Start with accessible recognition tasks before moving into deeper theory, terminology, and interpretation.', general: 'Start with accessible tasks before moving into more cognitively demanding sections.', other: 'Sequence sections from lower to higher cognitive demand so the paper feels intentionally designed.' };
function subjectGroup(subject: string) { const key = subject.trim().toLowerCase().replaceAll(' ', '_'); return ['english', 'spanish', 'turkish'].includes(key) ? 'language' : key === 'mathematics' || key === 'math' ? 'math' : ['science', 'music'].includes(key) ? key : key === 'other' ? 'other' : 'general'; }
function passageGuidance(selected: string[], group: string) {
  const shared = selected.filter((type) => type === 'reading_comprehension' || type === 'true_false');
  const lines = [
    '- Any section that uses a passage or source text must be tightly aligned to that text.',
    '- Questions must be answerable from textual evidence, not from random outside knowledge.',
    '- Higher-level inference is allowed only when the inference is strongly grounded in the text.',
    '- Distractors in text-based multiple choice must be plausible but still resolvable from the text.',
    '- The answer key must reflect what the text supports directly or reasonably implies.',
  ];
  if (selected.includes('reading_comprehension') && selected.includes('true_false')) lines.push('- Because both reading_comprehension and true_false are selected, prefer ONE coherent shared passage unless there is a strong pedagogical reason not to.', '- If a shared passage is used, both sections must use the same facts, ideas, and evidence base.', '- Do not generate unrelated passages or disconnected question sets for those two sections.');
  else if (shared.length) lines.push(`- The selected text-based section(s) ${shared.join(', ')} should use a purposeful passage that clearly supports the task.`, '- Do not create a passage that is decorative or loosely related to the questions.');
  if (group === 'language') lines.push('- For language subjects, keep comprehension, vocabulary, and inference anchored in the actual wording, meaning, tone, and details of the passage.');
  else if (group === 'science' || group === 'math') lines.push('- For science or math, any text-based section should support reasoning with content evidence, data, or scenario details rather than generic reading trivia.');
  return lines.join('\n');
}

export function buildExamUserPrompt(input: ExamPromptInput) {
  const group = subjectGroup(input.subject);
  const spec = examLengthRule(input.examLength);
  const selected = input.exerciseTypes;
  const typeDetails = selected.map((type) => { const rule = source.type_rules[`${type}|${group}` as keyof typeof source.type_rules] || ''; return rule ? `- ${type}: ${rule}` : `- ${type}`; }).join('\n');
  const blueprint = selected.map((type, index) => `- Section ${index + 1}: ${type} | group=${typeGroup[type] || 'core'} | label=${source.labels[type as keyof typeof source.labels] || type.replaceAll('_', ' ')}`).join('\n');
  const sequence = `- ${starts[group] || starts.general}\n- Vary the response demand across sections so the paper does not feel repetitive.\n- Make each section earn its place in the assessment by measuring a distinct but relevant skill.`;
  const subject = input.subject.trim().toLowerCase().replaceAll(' ', '_');
  const profile = source.profiles[`${subject}|${input.learnerStage}|${input.levelOrBand}` as keyof typeof source.profiles] || '';
  const payload = {
    subject: input.subject,
    subject_group: group,
    topic: input.topic,
    exam_title: input.examTitle,
    learner_stage: input.learnerStage,
    level_or_band: input.levelOrBand,
    exam_length: input.examLength,
    exercise_types: input.exerciseTypes,
    instructions: input.instructions || '',
    plan_language: input.planLanguage,
    student_material_language: input.studentMaterialLanguage,
    student_profile: input.studentProfile || {},
  };
  return `
Create a complete exam paper as JSON.

Input:
${JSON.stringify(payload, null, 2)}

Exam structure:
- ${selected.length} sections
- ${spec.questionsMin}-${spec.questionsMax} questions per section
- Exercise types to include (in order):
${typeDetails}

Subject-group guidance:
${source.group_guidance[group as keyof typeof source.group_guidance]}

Product-model alignment:
${source.alignment[group as keyof typeof source.alignment]}

Passage and evidence alignment:
${passageGuidance(selected, group)}

Selected exercise blueprint:
${blueprint}

Section-specific rules:
${typeDetails}

Quality guardrails:
${source.quality_guardrails}

Design principles:
- Use clear, age-appropriate language for the target learner_stage and level.
- Make the exam progressively harder from section to section.
- Sequence the paper like an expert assessor, not a random worksheet generator.
- Ensure every selected exercise type is used in a way that fits its group and the subject's product model.
- Make every section instruction match the actual response mode exactly.
- Do not tell students to write on a line if the section uses options, matching letters, or another built-in response format.
- Examples:
  - multiple_choice: tell students to choose or circle the correct option/letter
  - matching: tell students to match Column A with Column B and write the correct letter
  - true_false: tell students to decide whether each statement is true or false
  - fill_in_blank: tell students to complete each blank with the correct word, number, or phrase
- Design for efficiency: each section should gather meaningful evidence of learning with minimal fluff.
- Balance validity, reliability, clarity, and engagement.
- Prefer high-quality task design over decorative variety.
- Each section must have a clear title (e.g. "Part 1: Multiple Choice").
- Keep content factually accurate and pedagogically sound.
- Each section includes both questions AND answers.
- If the subject is custom or interdisciplinary, adapt intelligently to the topic rather than forcing a narrow template.
- In short_answer sections, every question must be self-contained; never refer to an unseen text or "the passage above". Assess application, explanation, comparison, reasoning, or a subject-specific skill. If source_text is supplied, show it and ask for synthesis or application beyond basic reading recall. Use reading_comprehension for passage-detail questions.

Profile quality guidance:
${profile}

${input.studentProfileBlock || ''}

${input.programContextBlock || ''}

Section sequencing guidance:
${sequence}

Required JSON structure:
{
  "title": "string",
  "instructions": "General exam instructions",
  "sections": [
        {
          "type": "exercise_type",
          "title": "Part N: Section Title",
          "instructions": "Section-specific instructions",
          "source_text": "optional reading passage or source text",
          "text_kind": "passage | article | essay | email | letter | message | dialogue",
          "text_blocks": [],
          "table_data": {
            "title": "optional table title",
            "caption": "optional table caption",
            "columns": ["Column 1", "Column 2"],
            "rows": [
              ["row 1 value 1", "row 1 value 2"],
              ["row 2 value 1", "row 2 value 2"]
            ]
          },
          "questions": [
          ],
          "answers": [
          ]
        }
  ]
}

Provide ALL sections and ALL answers.
`;
}
