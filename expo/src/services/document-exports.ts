import { Platform } from 'react-native';

import { requireSupabase } from '@/lib/supabase';
import type { StudentLearningWorkspace } from '@/services/teacher-students';
import sourceDocumentLabels from './source-document-labels.json';

type ReportSection = { heading: string; lines: string[] };
type DocumentLocale = 'en' | 'es' | 'tr';
const COPY = {
  en: { teachingResource: 'Teaching resource', studentCopy: 'Student copy', teacherCopy: 'Teacher copy', answerKey: 'Answer key', studentEvidence: 'Student learning evidence', overview: 'Overview', progress: 'Progress by subject', programs: 'Learning programs', recent: 'Recent work', noData: 'No data yet.', assignments: 'Assignments', attempts: 'Attempts', reviews: 'Reviews waiting', complete: 'complete', average: 'average', notScored: 'not scored', program: 'Learning program', assignment: 'Assignment', general: 'General', generated: 'Prepared with Classio' },
  es: { teachingResource: 'Recurso docente', studentCopy: 'Copia del estudiante', teacherCopy: 'Copia del docente', answerKey: 'Clave de respuestas', studentEvidence: 'Evidencia de aprendizaje', overview: 'Resumen', progress: 'Progreso por asignatura', programs: 'Programas de aprendizaje', recent: 'Trabajo reciente', noData: 'Aún no hay datos.', assignments: 'Tareas', attempts: 'Intentos', reviews: 'Revisiones pendientes', complete: 'completado', average: 'promedio', notScored: 'sin calificar', program: 'Programa de aprendizaje', assignment: 'Tarea', general: 'General', generated: 'Preparado con Classio' },
  tr: { teachingResource: 'Öğretim kaynağı', studentCopy: 'Öğrenci kopyası', teacherCopy: 'Öğretmen kopyası', answerKey: 'Cevap anahtarı', studentEvidence: 'Öğrenci öğrenme kanıtı', overview: 'Genel bakış', progress: 'Derse göre ilerleme', programs: 'Öğrenme programları', recent: 'Son çalışmalar', noData: 'Henüz veri yok.', assignments: 'Ödevler', attempts: 'Denemeler', reviews: 'Bekleyen incelemeler', complete: 'tamamlandı', average: 'ortalama', notScored: 'puanlanmadı', program: 'Öğrenme programı', assignment: 'Ödev', general: 'Genel', generated: 'Classio ile hazırlandı' },
} as const;

type DocumentBranding = { brandName: string; department: string; headerEnabled: boolean; footerEnabled: boolean; headerStyle: 'standard' | 'school'; font: string; fontSize: 'compact' | 'standard' | 'large' };
const DEFAULT_BRANDING: DocumentBranding = { brandName: '', department: '', headerEnabled: false, footerEnabled: false, headerStyle: 'standard', font: 'DejaVu Sans', fontSize: 'standard' };

async function loadBranding(): Promise<DocumentBranding> {
  try {
    const client = requireSupabase();
    const auth = await client.auth.getUser();
    if (!auth.data.user) return DEFAULT_BRANDING;
    const { data, error } = await client.from('branding_settings').select('brand_name,department,header_enabled,footer_enabled,header_style,branding_font,branding_font_size').eq('user_id', auth.data.user.id).maybeSingle();
    if (error || !data) return DEFAULT_BRANDING;
    const fontMap: Record<string, string> = { dejavu: 'DejaVu Sans', opensans: 'Open Sans', arial: 'Arial', calibri: 'Calibri', times: 'Times New Roman', comic: 'Comic Sans MS', handwriting: 'DejaVu Sans' };
    return { brandName: String(data.brand_name || ''), department: String(data.department || ''), headerEnabled: data.header_enabled === true, footerEnabled: data.footer_enabled === true, headerStyle: data.header_style === 'school' ? 'school' : 'standard', font: fontMap[String(data.branding_font || 'dejavu')] || 'DejaVu Sans', fontSize: ['compact', 'large'].includes(String(data.branding_font_size)) ? data.branding_font_size as 'compact' | 'large' : 'standard' };
  } catch { return DEFAULT_BRANDING; }
}

function slug(value: string) {
  return value.normalize('NFKD').replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').toLowerCase() || 'classio-document';
}

function browserReady() {
  return Platform.OS === 'web' && typeof document !== 'undefined';
}

let pdfFontData: Promise<[string, string]> | null = null;
async function loadPdfFontData(): Promise<[string, string]> {
  pdfFontData ??= Promise.all(['DejaVuSans.ttf', 'DejaVuSans-Bold.ttf'].map(async (name) => {
    const response = await fetch(`/fonts/${name}`);
    if (!response.ok) throw new Error(`PDF font could not be loaded: ${name}`);
    const bytes = new Uint8Array(await response.arrayBuffer());
    let binary = '';
    for (let offset = 0; offset < bytes.length; offset += 8192) binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
    return btoa(binary);
  })) as Promise<[string, string]>;
  try { return await pdfFontData; } catch (error) { pdfFontData = null; throw error; }
}

async function loadClassioLogo(): Promise<Uint8Array | null> {
  try { const response = await fetch('/logo_classio_light.png'); return response.ok ? new Uint8Array(await response.arrayBuffer()) : null; } catch { return null; }
}

function saveBlob(blob: Blob, filename: string) {
  if (!browserReady()) throw new Error('Downloads are available in the web app.');
  const href = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = href;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(href), 500);
}

function labelize(value: string) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function printable(value: unknown, depth = 0): string[] {
  if (value === null || value === undefined || value === '' || depth > 5) return [];
  if (typeof value === 'string') {
    if (value.startsWith('data:') || value.length > 12000) return [];
    return [value];
  }
  if (typeof value === 'number' || typeof value === 'boolean') return [String(value)];
  if (Array.isArray(value)) return value.flatMap((item, index) => printable(item, depth + 1).map((line) => `${index + 1}. ${line}`));
  if (typeof value === 'object') return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) => {
    const normalized = key.toLowerCase();
    if (normalized.includes('base64') || normalized.includes('image') || normalized.includes('thumbnail')) return [];
    return printable(child, depth + 1).map((line) => `${labelize(key)}: ${line}`);
  });
  return [];
}

type ResourceVariant = 'full' | 'student' | 'teacher' | 'answers';
const CV_COPY = {
  en: { contact: 'Contact', summary: 'Professional summary', subjects: 'Subjects', teaching_stages: 'Teaching stages', teaching_languages: 'Teaching languages', education: 'Education', certifications: 'Certifications', experience: 'Experience', skills: 'Skills', availability: 'Availability and rate', letter: 'Cover letter' },
  es: { contact: 'Contacto', summary: 'Resumen profesional', subjects: 'Asignaturas', teaching_stages: 'Etapas educativas', teaching_languages: 'Idiomas de enseñanza', education: 'Formación', certifications: 'Certificaciones', experience: 'Experiencia', skills: 'Habilidades', availability: 'Disponibilidad y tarifa', letter: 'Carta de presentación' },
  tr: { contact: 'İletişim', summary: 'Mesleki özet', subjects: 'Dersler', teaching_stages: 'Öğretim düzeyleri', teaching_languages: 'Öğretim dilleri', education: 'Eğitim', certifications: 'Sertifikalar', experience: 'Deneyim', skills: 'Beceriler', availability: 'Uygunluk ve ücret', letter: 'Ön yazı' },
} as const;

function professionalSections(detail: Record<string, unknown>, locale: DocumentLocale): ReportSection[] | null {
  const copy = CV_COPY[locale];
  if (detail.full_name) {
    const result: ReportSection[] = [];
    const contact = ['email', 'phone', 'location', 'date_of_birth'].map((key) => String(detail[key] || '').trim()).filter(Boolean);
    if (detail.role) contact.unshift(labelize(String(detail.role)));
    if (contact.length) result.push({ heading: copy.contact, lines: contact });
    if (detail.professional_summary) result.push({ heading: copy.summary, lines: [String(detail.professional_summary)] });
    for (const key of ['subjects', 'teaching_stages', 'teaching_languages', 'education', 'certifications', 'experience', 'skills'] as const) {
      const lines = list(detail[key]).map(String).filter(Boolean);
      if (lines.length) result.push({ heading: copy[key], lines });
    }
    const availability = [detail.availability, detail.rate].map((value) => String(value || '').trim()).filter(Boolean);
    if (availability.length) result.push({ heading: copy.availability, lines: availability });
    return result;
  }
  if (typeof detail.cover_letter === 'string') {
    const lines = detail.cover_letter.split(/\n\s*\n/).map((paragraph) => paragraph.trim()).filter(Boolean);
    if (detail.target_employer) lines.unshift(String(detail.target_employer));
    return [{ heading: copy.letter, lines }];
  }
  return null;
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function planSections(detail: Record<string, unknown>, locale: DocumentLocale): ReportSection[] | null {
  const plan = Object.keys(record(detail.plan_json)).length ? record(detail.plan_json) : detail;
  if (!plan.objective || !plan.core_material) return null;
  const label = (key: string) => (sourceDocumentLabels[locale] as Record<string, string>)[key] || labelize(key);
  const asLines = (value: unknown) => Array.isArray(value) ? value.flatMap((item) => printable(item)) : printable(value);
  const group = (heading: string, entries: [string, unknown][]): ReportSection | null => {
    const lines = entries.flatMap(([key, value]) => {
      const content = asLines(value);
      return content.length ? [label(key === 'objective' ? 'lesson_objective' : key), ...content] : [];
    });
    return lines.length ? { heading, lines } : null;
  };
  const core = record(plan.core_material);
  const materialsOrder = ['target_vocabulary', 'language_frames', 'pre_task_questions', 'reading_passage', 'listening_script', 'gist_questions', 'detail_questions', 'worked_example', 'independent_practice', 'common_error_alert', 'concept_explanation', 'real_life_application', 'strategy_steps', 'performance_goal', 'materials_needed', 'timing_guide', 'expected_output', 'differentiation', 'assessment_check', 'student_checklist', 'key_concept', 'guided_problem_set', 'independent_problem_set', 'challenge_problem', 'answer_key', 'phenomenon_prompt', 'prediction_task', 'observation_task', 'evidence_questions', 'misconception_alert', 'technical_focus', 'practice_pattern', 'teacher_model', 'strategy_name', 'model_scenario', 'student_action_plan', 'post_task'];
  const materials = materialsOrder.map((key): [string, unknown] => [key, key === 'reading_passage' || key === 'listening_script' ? plan[key] : core[key]]);
  return [
    group(label('lesson_overview').toUpperCase(), [['objective', plan.objective], ['success_criteria', plan.success_criteria]]),
    group(label('lesson_flow').toUpperCase(), [['warm_up', plan.warm_up], ['main_activity', plan.main_activity], ['guided_practice', plan.guided_practice], ['freer_task', plan.freer_task], ['wrap_up', plan.wrap_up]]),
    group(label('teacher_notes').toUpperCase(), [['core_examples', plan.core_examples], ['practice_questions', plan.practice_questions], ['teacher_moves', plan.teacher_moves], ['extension_task', plan.extension_task], ['optional_homework', plan.homework]]),
    group(label('lesson_materials').toUpperCase(), materials),
  ].filter((section): section is ReportSection => Boolean(section));
}

function examAnswer(value: unknown): string {
  const row = record(value);
  if (Object.keys(row).length) {
    if (row.left !== undefined && row.right !== undefined) return `${String(row.left)} → ${String(row.right)}`;
    return String(row.answer ?? row.text ?? row.correct_answer ?? '');
  }
  return String(value ?? '');
}

function examSections(detail: Record<string, unknown>, variant: ResourceVariant, locale: DocumentLocale): ReportSection[] | null {
  const exam = Object.keys(record(detail.exam_data)).length ? record(detail.exam_data) : detail;
  const sections = list(exam.sections).map(record).filter((section) => Object.keys(section).length);
  if (!sections.length || (detail.exam_data === undefined && exam.duration_minutes === undefined && !sections.some((section) => Array.isArray(section.answers)))) return null;

  const key = detail.answer_key ?? exam.answer_key;
  const keyedSections = list(record(key).sections).map(record);
  const flatAnswers = Array.isArray(key) ? key : list(record(key).answers);
  const output: ReportSection[] = [];
  if (variant !== 'answers' && String(exam.instructions || '').trim()) {
    output.push({ heading: labelize('instructions'), lines: [String(exam.instructions).trim()] });
  }
  if (variant !== 'answers') {
    for (const [sectionIndex, section] of sections.entries()) {
      const lines: string[] = [];
      if (String(section.instructions || '').trim()) lines.push(String(section.instructions).trim());
      if (String(section.source_text || '').trim()) lines.push(String(section.source_text).trim());
      const table = record(section.table_data);
      if (String(table.title || '').trim()) lines.push(String(table.title).trim());
      if (String(table.caption || '').trim()) lines.push(String(table.caption).trim());
      const columns = list(table.columns).map(String).filter(Boolean);
      if (columns.length) lines.push(columns.join('  |  '));
      for (const row of list(table.rows)) { const cells = list(row).map(String); if (cells.length) lines.push(cells.join('  |  ')); }
      for (const [questionIndex, question] of list(section.questions).entries()) {
        const row = record(question);
        const prompt = typeof question === 'string' ? question : String(row.stem || row.text || row.question || row.sentence || row.prompt || row.original || '');
        if (prompt.trim()) lines.push(`${questionIndex + 1}. ${prompt.trim()}`);
        for (const [optionIndex, option] of list(row.options).entries()) {
          lines.push(`   ${String.fromCharCode(65 + optionIndex)}) ${String(option)}`);
        }
      }
      if (lines.length) output.push({ heading: String(section.title || labelize(String(section.type || `Section ${sectionIndex + 1}`))), lines });
    }
  }

  if (variant !== 'student') {
    let flatOffset = 0;
    for (const [sectionIndex, section] of sections.entries()) {
      const questions = list(section.questions);
      const keyed = list(keyedSections[sectionIndex]?.answers).length ? list(keyedSections[sectionIndex]?.answers) : list(section.answers);
      const answers = questions.map((question, questionIndex) => {
        const inline = record(question);
        const answer = examAnswer(keyed[questionIndex] ?? flatAnswers[flatOffset + questionIndex] ?? inline.answer ?? inline.correct_answer ?? inline.correct);
        if (variant !== 'teacher' && variant !== 'full') return answer;
        const notes = [inline.explanation, inline.teacher_feedback, inline.marking_guide].map((value) => String(value || '').trim()).filter(Boolean);
        return [answer, ...notes].join(' — ');
      });
      flatOffset += questions.length;
      if (answers.some((answer) => answer.trim())) {
        output.push({ heading: `${COPY[locale].answerKey} · ${String(keyedSections[sectionIndex]?.title || section.title || sectionIndex + 1)}`, lines: answers.map((answer, index) => `${index + 1}. ${answer}`) });
      }
    }
  }
  return output;
}

function worksheetSections(detail: Record<string, unknown>, variant: ResourceVariant, locale: DocumentLocale): ReportSection[] | null {
  const worksheet = Object.keys(record(detail.worksheet_json)).length ? record(detail.worksheet_json) : detail;
  if (detail.worksheet_json === undefined && !worksheet.worksheet_type && !(worksheet.sections && worksheet.answer_key)) return null;
  const copy = { en: { questions: 'Questions', passage: 'Reading passage', answers: 'Answer key', matching: 'Match the items', vocabulary: 'Vocabulary bank', teacherNotes: 'Teacher notes' }, es: { questions: 'Preguntas', passage: 'Texto de lectura', answers: 'Clave de respuestas', matching: 'Relaciona los elementos', vocabulary: 'Banco de vocabulario', teacherNotes: 'Notas docentes' }, tr: { questions: 'Sorular', passage: 'Okuma metni', answers: 'Cevap anahtarı', matching: 'Öğeleri eşleştir', vocabulary: 'Kelime havuzu', teacherNotes: 'Öğretmen notları' } }[locale];
  const output: ReportSection[] = [];
  if (variant !== 'answers') {
    if (String(worksheet.instructions || '').trim()) output.push({ heading: labelize('instructions'), lines: [String(worksheet.instructions).trim()] });
    const vocabulary = list(worksheet.vocabulary_bank).map(String).filter(Boolean);
    if (vocabulary.length) output.push({ heading: copy.vocabulary, lines: [vocabulary.join('  ·  ')] });
    const passage = String(worksheet.reading_passage || worksheet.source_text || '').trim();
    if (passage) output.push({ heading: copy.passage, lines: [passage] });
    const sections = list(worksheet.sections).map(record).filter((section) => Object.keys(section).length);
    if (sections.length) {
      for (const [sectionIndex, section] of sections.entries()) {
        const lines: string[] = [];
        if (section.instructions) lines.push(String(section.instructions));
        for (const [questionIndex, question] of list(section.questions).entries()) {
          const row = record(question);
          const prompt = typeof question === 'string' ? question : String(row.prompt || row.stem || row.question || row.text || row.sentence || '');
          if (prompt.trim()) { lines.push(`${questionIndex + 1}. ${prompt.trim()}`); if (['short_answer', 'reading_comprehension', 'error_correction'].includes(String(worksheet.worksheet_type || section.type))) lines.push('____________________________________________'); }
          for (const [optionIndex, option] of list(row.options).entries()) lines.push(`   ${String.fromCharCode(65 + optionIndex)}) ${String(option)}`);
        }
        if (lines.length) output.push({ heading: String(section.title || `${copy.questions} ${sectionIndex + 1}`), lines });
      }
    } else if (worksheet.worksheet_type === 'matching') {
      const pairs = list(worksheet.matching_pairs).map(record);
      const left = pairs.length ? pairs.map((pair) => pair.left ?? pair.term) : list(worksheet.left_items);
      const right = pairs.length ? pairs.map((pair) => pair.right ?? pair.definition) : list(worksheet.right_items);
      const choices = right.length > 1 ? [...right.slice(1), right[0]] : right;
      const lines = left.map((item, index) => `${index + 1}. ${String(item || '')}   [   ]`);
      lines.push(...choices.map((item, index) => `${String.fromCharCode(97 + index)}) ${String(item || '')}`));
      if (lines.length) output.push({ heading: copy.matching, lines });
    } else {
      const items = list(worksheet.multiple_choice_items).length ? list(worksheet.multiple_choice_items) : list(worksheet.questions).length ? list(worksheet.questions) : list(worksheet.true_false_statements);
      const lines: string[] = [];
      for (const [index, item] of items.entries()) {
        const row = record(item);
        const prompt = typeof item === 'string' ? item : String(row.stem || row.question || row.prompt || row.text || row.sentence || '');
        if (prompt.trim()) { lines.push(`${index + 1}. ${prompt.trim()}`); if (['short_answer', 'reading_comprehension', 'error_correction'].includes(String(worksheet.worksheet_type))) lines.push('____________________________________________'); }
        for (const [optionIndex, option] of list(row.options).entries()) lines.push(`   ${String.fromCharCode(65 + optionIndex)}) ${String(option)}`);
      }
      if (lines.length) output.push({ heading: copy.questions, lines });
    }
  }
  if (variant !== 'student') {
    const key = detail.answer_key ?? worksheet.answer_key;
    const keyLines = typeof key === 'string' ? key.split(/\r?\n/).map((line) => line.trim()).filter(Boolean) : list(key).map(examAnswer).filter(Boolean);
    if (!keyLines.length && worksheet.worksheet_type === 'multiple_choice') {
      keyLines.push(...list(worksheet.multiple_choice_items).map((item, index) => `${index + 1}. ${examAnswer(record(item).answer ?? record(item).correct_answer)}`).filter((line) => !line.endsWith('. ')));
    }
    if (keyLines.length) output.push({ heading: copy.answers, lines: keyLines });
    const teacherNotes = list(worksheet.teacher_notes).map(String).filter(Boolean);
    if (teacherNotes.length && variant !== 'answers') output.push({ heading: copy.teacherNotes, lines: teacherNotes });
  }
  return output;
}

function withoutTeacherKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(withoutTeacherKeys);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(Object.entries(value as Record<string, unknown>).flatMap(([key, child]) => {
    const normalized = key.toLocaleLowerCase();
    if (/answer|solution|rationale|explanation|feedback|teacher_note|marking_guide|mark_scheme|rubric|(^|_)correct($|_)/.test(normalized)) return [];
    return [[key, withoutTeacherKeys(child)]];
  }));
}

function answersOnly(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(answersOnly).filter((item) => item !== undefined);
  if (!value || typeof value !== 'object') return undefined;
  const entries = Object.entries(value as Record<string, unknown>).flatMap(([key, child]) => {
    const normalized = key.toLocaleLowerCase();
    if (normalized.includes('answer') || normalized.includes('solution') || normalized.includes('rationale') || normalized === 'title') return [[key, child] as [string, unknown]];
    const nested = answersOnly(child);
    if (Array.isArray(nested) ? nested.length : nested && typeof nested === 'object' && Object.keys(nested as object).length) return [[key, nested] as [string, unknown]];
    return [];
  });
  return entries.length ? Object.fromEntries(entries) : undefined;
}

export function resourceSections(detail: Record<string, unknown>, variant: ResourceVariant = 'full', locale: DocumentLocale = 'en'): ReportSection[] {
  const professional = professionalSections(detail, locale);
  if (professional) return professional;
  const structuredPlan = planSections(detail, locale);
  if (structuredPlan) return structuredPlan;
  const structuredExam = examSections(detail, variant, locale);
  if (structuredExam) return structuredExam;
  const structuredWorksheet = worksheetSections(detail, variant, locale);
  if (structuredWorksheet) return structuredWorksheet;
  const omitted = new Set(['id', 'user_id', 'created_at', 'updated_at', 'is_public', 'status']);
  const payloadKey = ['worksheet_json', 'exam_data', 'plan_json', 'program_data', 'worksheet', 'exam'].find((key) => detail[key] && typeof detail[key] === 'object');
  const payload = payloadKey ? detail[payloadKey] as Record<string, unknown> : detail;
  const metadata = Object.fromEntries(Object.entries(detail).filter(([key, value]) => key !== payloadKey && !omitted.has(key) && ['string', 'number', 'boolean'].includes(typeof value)));
  const combined = { ...metadata, ...payload };
  const source = variant === 'student' ? withoutTeacherKeys(combined) : variant === 'answers' ? answersOnly(combined) : combined;
  return Object.entries((source || {}) as Record<string, unknown>).flatMap(([key, value]) => {
    if (omitted.has(key)) return [];
    const lines = printable(value);
    return lines.length ? [{ heading: labelize(key), lines }] : [];
  });
}

function studentSections(workspace: StudentLearningWorkspace, locale: DocumentLocale): ReportSection[] {
  const copy = COPY[locale];
  const subjectStats = workspace.assignments.reduce<Record<string, { total: number; complete: number; scores: number[] }>>((acc, row) => {
    const subject = String(row.subject_label || row.subject_key || copy.general);
    const stats = acc[subject] || { total: 0, complete: 0, scores: [] };
    stats.total += 1;
    if (['graded', 'completed'].includes(String(row.status))) stats.complete += 1;
    if (row.score_pct !== null && row.score_pct !== undefined && Number.isFinite(Number(row.score_pct))) stats.scores.push(Number(row.score_pct));
    acc[subject] = stats;
    return acc;
  }, {});
  return [
    { heading: copy.overview, lines: [`${copy.assignments}: ${workspace.assignments.length}`, `${copy.attempts}: ${workspace.attempts.length}`, `${copy.programs}: ${workspace.programs.length}`, `${copy.reviews}: ${workspace.reviews.filter((row) => String(row.status) === 'requested').length}`] },
    { heading: copy.progress, lines: Object.entries(subjectStats).map(([subject, stats]) => `${subject} — ${stats.complete}/${stats.total} ${copy.complete} · ${stats.scores.length ? `${Math.round(stats.scores.reduce((sum, score) => sum + score, 0) / stats.scores.length)}% ${copy.average}` : copy.notScored}`) },
    { heading: copy.programs, lines: workspace.programs.map((assignment) => {
      const program = (assignment.program || {}) as Record<string, unknown>;
      const progress = workspace.progress.filter((row) => String(row.assignment_id) === String(assignment.id));
      return `${String(program.title || copy.program)} — ${progress.filter((row) => Boolean(row.is_done)).length}/${progress.length} ${copy.complete}`;
    }) },
    { heading: copy.recent, lines: workspace.assignments.slice(0, 15).map((row) => `${String(row.title || copy.assignment)} · ${String(row.subject_label || row.subject_key || copy.general)} · ${String(row.status || 'assigned')}${row.score_pct === null || row.score_pct === undefined ? '' : ` · ${row.score_pct}%`}`) },
  ].map((section) => ({ ...section, lines: section.lines.length ? section.lines : [copy.noData] }));
}

function schoolFields(locale: DocumentLocale): [string, string, string] {
  if (locale === 'es') return ['Nombre: __________________', 'Clase: ________', 'Fecha: ________'];
  if (locale === 'tr') return ['Ad: __________________', 'Sınıf: ________', 'Tarih: ________'];
  return ['Name: __________________', 'Class: ________', 'Date: ________'];
}

async function savePdf(title: string, subtitle: string, sections: ReportSection[], filename: string, locale: DocumentLocale, worksheet = false, bulletLines = true) {
  if (!browserReady()) throw new Error('PDF downloads are available in the web app.');
  // The browser ESM build avoids jsPDF's Node-only optional html2canvas loader in Expo SSR.
  const { jsPDF } = await import('jspdf/dist/jspdf.es.min.js');
  const pdf = new jsPDF({ unit: 'pt', format: 'a4' });
  const [regularFont, boldFont] = await loadPdfFontData();
  pdf.addFileToVFS('DejaVuSans.ttf', regularFont);
  pdf.addFileToVFS('DejaVuSans-Bold.ttf', boldFont);
  pdf.addFont('DejaVuSans.ttf', 'DejaVu', 'normal');
  pdf.addFont('DejaVuSans-Bold.ttf', 'DejaVu', 'bold');
  const branding = await loadBranding();
  const logo = bulletLines ? null : await loadClassioLogo();
  const width = pdf.internal.pageSize.getWidth();
  const height = pdf.internal.pageSize.getHeight();
  const margin = 52;
  const bodySize = branding.fontSize === 'compact' ? 9 : branding.fontSize === 'large' ? 11 : 10;
  let y = 46;
  const ensureSpace = (needed: number) => { if (y + needed > height - margin) { pdf.addPage(); y = margin; } };
  pdf.setFillColor(29, 78, 216); pdf.rect(0, 0, width, 10, 'F');
  if (branding.headerEnabled) {
    if (branding.headerStyle === 'school') { pdf.setFillColor(239, 246, 255); pdf.roundedRect(margin, y - 15, width - margin * 2, 54, 8, 8, 'F'); }
    pdf.setTextColor(29, 78, 216); pdf.setFont('DejaVu', 'bold'); pdf.setFontSize(branding.headerStyle === 'school' ? 14 : 10); pdf.text(branding.brandName.toUpperCase(), branding.headerStyle === 'school' ? width / 2 : margin, y, { align: branding.headerStyle === 'school' ? 'center' : 'left' });
    if (branding.department) { y += 14; pdf.setFont('DejaVu', 'normal'); pdf.setFontSize(8); pdf.setTextColor(71, 85, 105); pdf.text(branding.department, branding.headerStyle === 'school' ? width / 2 : margin, y, { align: branding.headerStyle === 'school' ? 'center' : 'left' }); }
    y += branding.headerStyle === 'school' ? 42 : 24;
  }
  pdf.setTextColor(15, 23, 42); pdf.setFont('DejaVu', 'bold'); pdf.setFontSize(23); const titleLines = pdf.splitTextToSize(title, width - margin * 2); pdf.text(titleLines, margin, y); y += titleLines.length * 27 + 8;
  if (worksheet && branding.headerEnabled && branding.headerStyle === 'school') {
    pdf.setFont('DejaVu', 'bold'); pdf.setFontSize(8); pdf.setTextColor(51, 65, 85);
    schoolFields(locale).forEach((field, index) => pdf.text(field, margin + index * ((width - margin * 2) / 3), y + 8));
    y += 28; pdf.setDrawColor(203, 213, 225); pdf.line(margin, y, width - margin, y); y += 16;
  }
  pdf.setFillColor(248, 250, 252); pdf.setDrawColor(203, 213, 225); pdf.roundedRect(margin, y, width - margin * 2, 34, 6, 6, 'FD');
  pdf.setTextColor(71, 85, 105); pdf.setFont('DejaVu', 'normal'); pdf.setFontSize(9); pdf.text(subtitle, margin + 12, y + 14); pdf.text(new Date().toLocaleDateString(), width - margin - 12, y + 14, { align: 'right' }); y += 56;
  for (const section of sections) {
    ensureSpace(54); pdf.setFillColor(239, 246, 255); pdf.roundedRect(margin, y - 14, width - margin * 2, 28, 5, 5, 'F'); pdf.setTextColor(30, 64, 175); pdf.setFont('DejaVu', 'bold'); pdf.setFontSize(12); pdf.text(section.heading, margin + 10, y + 4); y += 28;
    pdf.setFont('DejaVu', 'normal'); pdf.setFontSize(bodySize);
    for (const line of section.lines) {
      const wrapped = pdf.splitTextToSize(line, width - margin * 2 - 20);
      ensureSpace(wrapped.length * (bodySize + 5) + 12); if (bulletLines) { pdf.setFillColor(37, 99, 235); pdf.circle(margin + 4, y - 3, 1.8, 'F'); } pdf.setTextColor(51, 65, 85); pdf.text(wrapped, margin + (bulletLines ? 14 : 0), y); y += wrapped.length * (bodySize + 5) + (line.startsWith('____') ? 15 : 9);
    }
    y += 10;
  }
  const pages = pdf.getNumberOfPages();
  for (let page = 1; page <= pages; page += 1) { pdf.setPage(page); pdf.setDrawColor(226, 232, 240); pdf.line(margin, height - 34, width - margin, height - 34); pdf.setFont('DejaVu', 'normal'); pdf.setFontSize(8); pdf.setTextColor(100, 116, 139); pdf.text(bulletLines ? (branding.footerEnabled ? `${branding.brandName} · ${COPY[locale].generated}` : COPY[locale].generated) : 'Visit classio.streamlit.app', margin, height - 20); if (logo) pdf.addImage(logo, 'PNG', width - margin - 80, height - 30, 50, 20); pdf.text(`${page} / ${pages}`, width - margin, height - 20, { align: 'right' }); }
  pdf.save(`${slug(filename)}.pdf`);
}

async function saveDocx(title: string, subtitle: string, sections: ReportSection[], filename: string, locale: DocumentLocale, worksheet = false, bulletLines = true) {
  if (!browserReady()) throw new Error('Word downloads are available in the web app.');
  const { AlignmentType, BorderStyle, Document, Footer, Header, HeadingLevel, ImageRun, Packer, PageNumber, Paragraph, ShadingType, Table, TableCell, TableRow, TextRun, WidthType } = await import('docx');
  const branding = await loadBranding();
  const logo = bulletLines ? null : await loadClassioLogo();
  const baseSize = branding.fontSize === 'compact' ? 19 : branding.fontSize === 'large' ? 23 : 21;
  const children = [
    new Paragraph({ text: title, heading: HeadingLevel.TITLE, spacing: { after: 180 } }),
    ...(worksheet && branding.headerEnabled && branding.headerStyle === 'school' ? [new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, rows: [new TableRow({ children: schoolFields(locale).map((field) => new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: field, font: branding.font, size: baseSize, bold: true })] })] })) })] })] : []),
    new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, rows: [new TableRow({ children: [new TableCell({ shading: { fill: 'F8FAFC', type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 140, right: 140 }, children: [new Paragraph({ children: [new TextRun({ text: subtitle, color: '475569', bold: true }), new TextRun({ text: `  ·  ${new Date().toLocaleDateString()}`, color: '64748B' })] })] })] })] }),
    ...sections.flatMap((section) => [
      new Paragraph({ text: section.heading, heading: HeadingLevel.HEADING_1, spacing: { before: 280, after: 100 }, shading: { fill: 'EFF6FF', type: ShadingType.CLEAR }, border: { bottom: { color: 'BFDBFE', size: 5, style: BorderStyle.SINGLE } } }),
      ...section.lines.map((line) => new Paragraph({ children: [new TextRun({ text: line, size: baseSize, font: branding.font, color: '334155' })], bullet: bulletLines ? { level: 0 } : undefined, spacing: { after: line.startsWith('____') ? 180 : 90, line: 300 } })),
    ]),
  ];
  const header = new Header({ children: [new Paragraph({ alignment: branding.headerStyle === 'school' ? AlignmentType.CENTER : AlignmentType.LEFT, border: { bottom: { color: '2563EB', size: 16, style: BorderStyle.SINGLE } }, children: [new TextRun({ text: branding.brandName.toUpperCase(), color: '1D4ED8', bold: true, size: 22, font: branding.font }), ...(branding.department ? [new TextRun({ text: `  ·  ${branding.department}`, color: '64748B', size: 18, font: branding.font })] : [])] })] });
  const footer = new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, border: { top: { color: 'E2E8F0', size: 4, style: BorderStyle.SINGLE } }, children: [new TextRun({ text: bulletLines ? `${branding.footerEnabled ? `${branding.brandName} · ` : ''}${COPY[locale].generated}   ` : 'Visit classio.streamlit.app  ', color: '64748B', size: 16, font: branding.font }), ...(logo ? [new ImageRun({ data: logo, transformation: { width: 65, height: 26 }, type: 'png' })] : []), ...(bulletLines ? [new TextRun({ children: [PageNumber.CURRENT], color: '64748B', size: 16 })] : [])] })] });
  const blob = await Packer.toBlob(new Document({ styles: { default: { document: { run: { font: branding.font, size: baseSize, color: '334155' }, paragraph: { spacing: { line: 300 } } }, title: { run: { font: branding.font, size: 42, bold: true, color: '0F172A' } }, heading1: { run: { font: branding.font, size: 26, bold: true, color: '1E40AF' } } } }, sections: [{ headers: branding.headerEnabled ? { default: header } : undefined, footers: { default: footer }, properties: { page: { margin: { top: 900, right: 850, bottom: 850, left: 850 } } }, children }] }));
  saveBlob(blob, `${slug(filename)}.docx`);
}

export function downloadResourcePdf(title: string, detail: Record<string, unknown>, locale: DocumentLocale = 'en', variant: ResourceVariant = 'full') {
  const suffix = variant === 'full' ? '' : `-${variant}`;
  const subtitle = variant === 'student' ? COPY[locale].studentCopy : variant === 'teacher' ? COPY[locale].teacherCopy : variant === 'answers' ? COPY[locale].answerKey : COPY[locale].teachingResource;
  return savePdf(title, subtitle, resourceSections(detail, variant, locale), `${title}${suffix}`, locale, Boolean(detail.worksheet_json || detail.worksheet_type), false);
}

export function downloadResourceDocx(title: string, detail: Record<string, unknown>, locale: DocumentLocale = 'en', variant: ResourceVariant = 'full') {
  const suffix = variant === 'full' ? '' : `-${variant}`;
  const subtitle = variant === 'student' ? COPY[locale].studentCopy : variant === 'teacher' ? COPY[locale].teacherCopy : variant === 'answers' ? COPY[locale].answerKey : COPY[locale].teachingResource;
  return saveDocx(title, subtitle, resourceSections(detail, variant, locale), `${title}${suffix}`, locale, Boolean(detail.worksheet_json || detail.worksheet_type), false);
}

export function downloadStudentReportPdf(studentName: string, workspace: StudentLearningWorkspace, locale: DocumentLocale = 'en') {
  return savePdf(`${studentName} · ${COPY[locale].progress}`, COPY[locale].studentEvidence, studentSections(workspace, locale), `${studentName}-progress-report`, locale);
}

export function downloadStudentReportDocx(studentName: string, workspace: StudentLearningWorkspace, locale: DocumentLocale = 'en') {
  return saveDocx(`${studentName} · ${COPY[locale].progress}`, COPY[locale].studentEvidence, studentSections(workspace, locale), `${studentName}-progress-report`, locale);
}

export function downloadStudentHistoryPdf(studentName: string, lessons: Record<string, unknown>[], payments: Record<string, unknown>[], locale: DocumentLocale = 'en') {
  const sections: ReportSection[] = [
    { heading: locale === 'es' ? 'Clases' : locale === 'tr' ? 'Dersler' : 'Lessons', lines: lessons.map((row) => `${String(row.lesson_date || '')} · ${String(row.subject_custom || row.subject || 'General')} · ${String(row.modality || '')} · ${String(row.number_of_lesson || 0)}${row.note ? ` · ${String(row.note)}` : ''}`) },
    { heading: locale === 'es' ? 'Pagos y paquetes' : locale === 'tr' ? 'Ödemeler ve paketler' : 'Payments & packages', lines: payments.map((row) => `${String(row.payment_date || '')} · ${String(row.subject_custom || row.subject || 'General')} · ${String(row.number_of_lesson || 0)} · ${String(row.currency || '')} ${Number(row.paid_amount || 0).toLocaleString()}`) },
  ].map((section) => ({ ...section, lines: section.lines.length ? section.lines : [COPY[locale].noData] }));
  return savePdf(studentName, COPY[locale].studentEvidence, sections, `${studentName}-student-report`, locale);
}
