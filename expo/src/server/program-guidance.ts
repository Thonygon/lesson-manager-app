// Constants are snapshotted from streamlit/helpers/learning_programs.py.
import source from './program-guidance.json';

type ObjectValue = Record<string, unknown>;
type Progression = { subject: string; subject_family: string; global_priorities: string[]; focus_strands: string[]; sequence_expectations: string[]; subject_specific_notes: string[] };
const object = (value: unknown): ObjectValue => value && typeof value === 'object' && !Array.isArray(value) ? value as ObjectValue : {};
const strings = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
const key = (value: string) => value.trim().toLowerCase().replaceAll(' ', '_');
const constants = source as Record<string, unknown>;
const guidance = object(constants._SUBJECT_GUIDANCE);
const profiles = object(constants._SUBJECT_PROGRESSION_PROFILES);

export function inferProgramSubjectFamily(subject: string, customSubject = ''): string {
  const normalized = key(subject);
  const engines: Record<string, string> = { english: 'language', spanish: 'language', mathematics: 'math', science: 'science', music: 'music', study_skills: 'study_skills' };
  if (normalized !== 'other' && engines[normalized]) return engines[normalized];
  const probe = `${subject} ${customSubject}`.trim().toLowerCase();
  let family = 'general'; let best = 0;
  for (const [candidate, rawKeywords] of Object.entries(object(constants._SUBJECT_FAMILY_KEYWORDS))) {
    const score = strings(rawKeywords).reduce((sum, keyword) => sum + (probe.includes(keyword) ? Math.max(1, keyword.split(' ').length) : 0), 0);
    if (score > best) { best = score; family = candidate; }
  }
  return family;
}

function fallbackFocus(subject: string, family: string, stage: string, level: string): string[] {
  if (family === 'language') {
    const sourceFocus = object(constants._LANGUAGE_FOCUS_BY_LEVEL);
    const focus = [...strings(sourceFocus[level.toUpperCase()] || sourceFocus.A2)];
    if (stage === 'early_primary' && ['A1', 'A2'].includes(level)) { focus[0] = 'phonological awareness'; focus[3] = 'early reading support'; }
    else if (stage === 'adult_stage' && ['A1', 'A2'].includes(level)) { focus[0] = 'survival and everyday vocabulary'; focus[2] = 'practical interaction'; }
    return focus;
  }
  const byFamily = object(constants._FAMILY_FOCUS_BY_BAND);
  const familyFocus = object(byFamily[family] || byFamily.general);
  const focus = [...strings(familyFocus[level.toLowerCase()] || familyFocus.intermediate_band)];
  if (family === 'math' && stage === 'early_primary' && level === 'beginner_band') focus[0] = 'counting and quantity';
  else if (family === 'math' && stage === 'adult_stage' && level === 'beginner_band') focus[0] = 'practical numeracy';
  else if (family === 'science' && stage === 'early_primary') focus[0] = 'curiosity and observation';
  else if (family === 'study_skills' && stage === 'adult_stage') focus[focus.length - 1] = 'self-regulation';
  else if (family === 'general' && stage === 'adult_stage') focus[0] = 'practical understanding';
  return focus;
}

function progressionLine(family: string, level: string): string {
  const band = level.toLowerCase();
  if (family === 'language') {
    if (level === 'A1') return 'Start with highly supported comprehension and communication, then move toward short coherent texts, predictable interaction, and visible sentence building.';
    if (level === 'A2') return 'Move from secure everyday communication toward short connected texts, clearer opinion or reaction, and more independent paragraph-level output.';
    if (['B1', 'B2'].includes(level)) return 'Build from supported explanation toward interpretation, comparison, justification, and more sustained reading, listening, speaking, and writing.';
    return 'Keep the demand intellectually strong through interpretation, synthesis, nuance, and precision while staying appropriate to the learner stage.';
  }
  const lines: Record<string, [string, string, string]> = {
    math: ['Repair prerequisites first, then bridge learners into the core curriculum through worked examples, structured rehearsal, and steadily increasing independence.', 'Move from secure understanding toward flexible method choice, explanation, and connected multi-step application.', 'Stretch learners through richer reasoning, justification, and transfer, while keeping the build-up teachable and conceptually coherent.'],
    science: ['Begin with observable phenomena and simple explanation, then build scientific vocabulary, concept connections, and evidence-based responses.', 'Blend concept learning, investigation, evidence use, and explanation so students move from noticing to explaining and applying.', 'Increase demand through modeling, data interpretation, evaluation of evidence, and more precise scientific reasoning.'],
    music: ['Build confidence through short repeated cycles that connect hearing, doing, and notation before expecting sustained independent performance.', 'Sequence theory, aural work, practice, and performance so the work feels musical, connected, and steadily more independent.', 'Deepen interpretation, stylistic awareness, critique, and independent performance or composition without losing musical coherence.'],
    study_skills: ['Start with visible routines, teacher-guided strategy use, and repeated rehearsal before expecting independent study decisions.', 'Move from structured support toward guided independence in planning, revision, memory, and time management.', 'Expect learners to compare, choose, adapt, and evaluate strategies for different tasks, deadlines, and performance goals.'],
    general: ['Secure foundations first, then build toward manageable independent application through repetition, examples, and clear success criteria.', 'Move from understanding toward purposeful application, communication, and retrieval in a coherent sequence.', 'Stretch learners through deeper analysis, critique, and transfer while keeping the sequence practical and teachable.'],
  };
  return (lines[family] || lines.general)[band === 'beginner_band' ? 0 : band === 'intermediate_band' ? 1 : 2];
}

function reviewLine(subject: string, family: string, stage: string): string {
  const lines: Record<string, string> = {
    language: 'Recycle high-value vocabulary, structures, and communicative routines across the sequence so fluency and accuracy grow together.',
    math: 'Keep cumulative review active so gaps do not block new learning, and make reasoning visible through explanation and discussion.',
    science: 'Revisit core ideas, vocabulary, and evidence routines across the sequence so scientific understanding grows cumulatively rather than as isolated facts.',
    music: 'Use regular rehearsal, feedback, and reflection points so theory, listening, and performance keep reinforcing one another.',
    study_skills: 'Anchor each strategy in real tasks and revisit it often enough that it becomes usable beyond a single lesson or unit.',
  };
  if (lines[family]) return lines[family];
  const named = subject.trim().replaceAll('_', ' ');
  if (named && !['other', 'general'].includes(named)) return `Keep the disciplinary habits of ${named} visible rather than collapsing the work into generic literacy tasks.`;
  if (stage === 'early_primary') return 'Use repetition, modeling, and concrete examples so learners feel successful while building the right habits.';
  return 'Blend review with new learning so the sequence stays coherent, cumulative, and purposeful.';
}

function fallbackNotes(subject: string, family: string, stage: string): string[] {
  if (subject === 'spanish') return ['Prioritize pronunciation support, oral confidence, and meaningful communicative tasks in Spanish.', 'Use age-appropriate cultural and communicative contexts relevant to Spanish learning.'];
  if (family === 'language' && ['early_primary', 'upper_primary'].includes(stage)) return ['Keep challenge age-appropriate by avoiding adult-style topics and preserving child-friendly contexts and supports.'];
  if (family === 'general' && !['other', 'general', ''].includes(subject)) return [`Keep the disciplinary logic of ${subject.replaceAll('_', ' ')} visible in the tasks, examples, and outputs.`];
  return [];
}

export function programProgressionProfile(subject: string, stage: string, level: string, customSubject = ''): Progression {
  const normalized = key(subject);
  const family = inferProgramSubjectFamily(normalized, customSubject);
  const profile = object(profiles[normalized] || profiles[family]);
  const stageProfile = object(object(profile.by_stage)[stage]);
  let matched = object(stageProfile[level]);
  if (normalized === 'spanish' && !Object.keys(matched).length) {
    matched = object(object(object(profiles.english).by_stage)[stage]);
    matched = object(matched[level]);
    if (Object.keys(matched).length) return { subject: normalized, subject_family: family, global_priorities: ['Treat Spanish as a full communicative curriculum with CEFR-style progression.', 'Balance oral communication, comprehension, literacy, grammar, and vocabulary in context.', 'Use high-frequency Spanish structures and vocabulary in spiraled, meaningful reuse.'], focus_strands: strings(matched.focus_strands), sequence_expectations: strings(matched.sequence_expectations), subject_specific_notes: ['Use age-appropriate cultural and communicative contexts relevant to Spanish learning.', 'Prioritize pronunciation support, oral confidence, and meaningful communicative tasks.'] };
  }
  if (!Object.keys(matched).length) {
    const stageStart = object(constants._STAGE_FALLBACK_SEQUENCE_START);
    matched = { focus_strands: fallbackFocus(normalized, family, stage, level), sequence_expectations: [String(stageStart[stage] || stageStart.upper_primary), progressionLine(family, level), reviewLine(normalized, family, stage)], subject_specific_notes: fallbackNotes(normalized, family, stage) };
  }
  if (normalized === 'spanish' && !Object.keys(object(object(profiles.spanish).by_stage)).length) return { subject: normalized, subject_family: family, global_priorities: ['Treat Spanish as a full communicative curriculum with CEFR-style progression.', 'Balance oral communication, comprehension, literacy, grammar, and vocabulary in context.', 'Use high-frequency Spanish structures and vocabulary in spiraled, meaningful reuse.'], focus_strands: strings(matched.focus_strands), sequence_expectations: strings(matched.sequence_expectations), subject_specific_notes: ['Use age-appropriate cultural and communicative contexts relevant to Spanish learning.', 'Prioritize pronunciation support, oral confidence, and meaningful communicative tasks.'] };
  return { subject: normalized, subject_family: family, global_priorities: strings(profile.global_priorities), focus_strands: strings(matched.focus_strands), sequence_expectations: strings(matched.sequence_expectations), subject_specific_notes: strings(matched.subject_specific_notes) };
}

export function programGuidance(subject: string, stage: string, level: string, customSubject = '') {
  const family = inferProgramSubjectFamily(subject, customSubject);
  const details = object(guidance[family] || guidance.general);
  return { subject_family: family, best_practice_frameworks: strings(details.frameworks), best_practice_principles: strings(details.principles), subject_progression_profile: programProgressionProfile(subject, stage, level, customSubject), delivery_mode_guidance: object(constants._DELIVERY_GUIDANCE), recommended_non_classio_activities: strings(object(constants._NON_CLASSIO_ACTIVITY_BANK)[family] || object(constants._NON_CLASSIO_ACTIVITY_BANK).general) };
}

export function programTrackGuidance(track: string, target: string): string[] {
  if (track !== 'exam_prep') return ['Build a broad, level-appropriate language program rather than a narrow exam syllabus.', 'Balance skill development, communicative confidence, grammar, vocabulary, reading, and writing in a realistic progression.'];
  const targets: Record<string, string[]> = {
    sat_rw: ['Build an exam-prep program specifically for the Digital SAT Reading and Writing section.', 'Do not drift into generic ESL or essay-writing units that are not relevant to the Digital SAT Reading and Writing format.', 'Prioritize short-passage reading, revision and editing, vocabulary in context, rhetorical synthesis, and standard English conventions.'],
    ielts_academic: ['Build an exam-prep program specifically for IELTS Academic.', 'Sequence the program around band-appropriate reading, writing, language control, coherence, and academic task performance.', 'Use realistic academic exam-style skill strands rather than generic conversation-only progression.'],
    ielts_general: ['Build an exam-prep program specifically for IELTS General Training.', 'Sequence the program around practical reading, writing-task control, coherence, and band-oriented language accuracy.', 'Use realistic general-training exam-style skill strands rather than a generic A1-C2 pathway.'],
    toefl_ibt: ['Build an exam-prep program specifically for TOEFL iBT.', 'Prioritize academic reading, evidence-based writing, integrated language use, source-grounded reasoning, and academic vocabulary.', 'Avoid overly casual topic progression that would not support TOEFL-style academic performance.'],
    dele: ['Build an exam-prep program specifically for DELE.', 'Sequence the program around CEFR-aligned Spanish comprehension, production, interaction, register control, and authentic communicative tasks.', 'Avoid translated-from-English logic and keep the Spanish progression authentic and exam-relevant.'],
  };
  return targets[target] || ['Build an exam-prep program with a realistic, official-style skill progression.'];
}
