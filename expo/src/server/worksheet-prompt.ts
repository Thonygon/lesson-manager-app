import profileGuidance from './source-worksheet-profile-guidance.json';
import typeRules from './source-worksheet-type-rules.json';

// Source: streamlit/helpers/worksheet_builder.py:_build_worksheet_prompts.
export type WorksheetPromptInput = { subject: string; topic: string; learnerStage: string; levelOrBand: string; worksheetType: string; planLanguage: string; studentMaterialLanguage: string; studentProfile?: Record<string, unknown>; studentProfileBlock?: string; programContextBlock?: string };

function pagePlan(type: string, stage: string, level: string) {
  const onePage = ['lower_primary', 'primary_lower', 'early_primary', 'pre_primary'].includes(stage.trim().toLowerCase()) || (['upper_primary', 'primary_upper'].includes(stage.trim().toLowerCase()) && level.trim().toUpperCase() === 'A1');
  const targetPages = onePage ? 1 : 2;
  const ranges: Record<string, [string, string]> = { multiple_choice: ['5-6', '8-10'], true_false: ['5-6', '7-9'], matching: ['5-6', '7-8'], short_answer: ['4-5', '6-8'], reading_comprehension: ['4-5', '5-7'], error_correction: ['5-6', '6-8'] };
  return { targetPages, itemRange: (ranges[type] || ['5-6', '6-8'])[onePage ? 0 : 1] };
}

export function buildWorksheetUserPrompt(input: WorksheetPromptInput) {
  const payload = {
    subject: input.subject,
    topic: input.topic,
    learner_stage: input.learnerStage,
    level_or_band: input.levelOrBand,
    worksheet_type: input.worksheetType,
    plan_language: input.planLanguage,
    student_material_language: input.studentMaterialLanguage,
    student_profile: input.studentProfile || {},
  };
  const subject = input.subject.trim().toLowerCase().replaceAll(' ', '_');
  const page = pagePlan(input.worksheetType, input.learnerStage, input.levelOrBand);
  const profile = (profileGuidance as Record<string, string>)[`${subject}|${input.learnerStage}|${input.levelOrBand}`] || '';
  const studentProfileBlock = input.studentProfileBlock || '';
  const programContextBlock = input.programContextBlock || '';
  const rules = (typeRules as Record<string, string>)[input.worksheetType] || '';
  return `
Create one complete, topic-based teaching worksheet as JSON.

Input:
${JSON.stringify(payload, null, 2)}

Design principles:
- Use clear, age-appropriate language for the target learner_stage and level.
- Keep the worksheet pedagogically coherent and clearly aligned to the worksheet_type.
- Use publication-ready capitalization, punctuation, grammar, and clean academic formatting.
- Make the student instructions match the actual response mode exactly.
- Do not tell students to write on a line if the task uses options, matching letters, or a grid.
- Examples:
  - multiple_choice: tell students to choose or circle the correct option/letter
  - matching: tell students to match Column A with Column B and write the correct letter
  - true_false: tell students to decide whether each statement is true or false
  - word_search_vocab: tell students to find and circle the hidden words in the grid
- Include a vocabulary_bank only when it is genuinely useful.
- teacher_notes should include 2-3 practical tips for differentiation or extension.
- Keep content factually accurate and pedagogically sound.
- Do not invent unnecessary sections.
- Follow this Classio worksheet layout target:
  - target_pages: ${page.targetPages}
  - target_item_range: ${page.itemRange}
- Create enough content to fill the target number of pages well, but do not overfill.
- Avoid outputs that would leave the final page half empty.
- Prefer fewer, better-distributed items over too many short items.
- For short_answer and reading_comprehension, create questions that reasonably allow student writing space below each item.
- For short_answer, assess application, explanation, comparison, reasoning, editing, or a subject-specific skill. At B2, C1, and C2 in language subjects, a short source text can support style improvement, paraphrasing, argument analysis, or synthesis. If any question refers to a paragraph, phrase, passage, or text, include the COMPLETE student-facing text in source_text. Never refer to an unseen text. Keep reading_passage empty for short_answer. Questions must practice the target skill, not merely recall passage details; use reading_comprehension for passage-detail recall.
- When a worksheet needs a reading_passage or source_text, choose the text form deliberately:
  - passage, article, essay, email, letter, message, or dialogue.
  - Put that value in "text_kind".
  - Preserve clean line breaks in reading_passage/source_text so the student version looks publication-ready.
  - For emails/letters/messages, put headers, greeting, body paragraphs, closing, and signature on separate lines.
  - For dialogues, use one speaker turn per line, e.g. "Ana: ...".
  - For articles/essays/passages, keep the title separate from the first paragraph and separate paragraphs with line breaks.

Profile quality guidance:
${profile}

${studentProfileBlock}

${programContextBlock}

${rules}

Required JSON structure:
{
  "title": "string",
  "subject": "string",
  "topic": "string",
  "learner_stage": "string",
  "level_or_band": "string",
  "worksheet_type": "string",
  "plan_language": "string",
  "student_material_language": "string",
  "instructions": "string",
  "text_kind": "passage | article | essay | email | letter | message | dialogue",
  "text_blocks": [],
  "reading_passage": "string",
  "source_text": "string",
  "questions": ["string", ...],
  "true_false_statements": ["string", ...],
  "vocabulary_bank": ["string", ...],
  "matching_pairs": [
    {"left": "string", "right": "string"}
  ],
  "multiple_choice_items": [
    {"stem": "string", "options": ["string", "string", "string", "string"], "answer": "string"}
  ],
  "left_items": ["string", ...],
  "right_items": ["string", ...],
  "answer_key": "string or list of numbered answers",
  "teacher_notes": ["string", ...]
}

Global validation rules:
- Only reading_comprehension may use "reading_passage".
- true_false must use "true_false_statements" and normally uses "source_text". short_answer may also use "source_text" when questions analyze or transform a supplied text. Other exercise types should leave unrelated text fields empty.
- Only matching may use "matching_pairs", "left_items", or "right_items".
- Only multiple_choice may use "multiple_choice_items".
- matching must not be sentence completion.
- true_false must include a source text.
- fill_in_the_blanks must remain a sentence-completion task.
- word_search_vocab should mainly use vocabulary_bank.
- If a section is not needed for the worksheet_type, return an empty string "" or [].
`;
}
