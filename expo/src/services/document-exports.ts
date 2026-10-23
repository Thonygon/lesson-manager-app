import { Platform } from 'react-native';

import { getBrandingSettings } from '@/services/branding';
import { recordedDocumentExport, type DocumentKind } from '@/services/document-export-events';
import { canonicalSubjectKey } from '@/lib/subjects';
import { canonicalLearnerStageKey } from '@/lib/learner-stages';
import { lessonPurposeKey } from '@/lib/lesson-purpose';
import type { StudentLearningWorkspace } from '@/services/teacher-students';
import sourceDocumentLabels from './source-document-labels.json';
import { findWordSearchPlacements, makeWordSearchGrid, makeWordSearchPuzzle, type WordSearchPlacement } from './word-search-grid';

type PlanBlock = { label: string; lines: string[]; list: boolean };
type ReportSection = { heading: string; lines: string[]; subheadings?: string[]; planBlocks?: PlanBlock[]; planOverview?: boolean; pageBreak?: boolean; pdfPageBreak?: boolean; vocabularyTable?: boolean; bulleted?: boolean; grid?: string[][]; table?: string[][]; visuals?: string[]; watermark?: string; answerCells?: [number, number][] };
type DocumentLocale = 'en' | 'es' | 'tr';
const COPY = {
  en: { teachingResource: 'Teaching resource', studentCopy: 'Student copy', teacherCopy: 'Teacher copy', answerKey: 'Answer key', studentEvidence: 'Student learning evidence', overview: 'Overview', progress: 'Progress by subject', programs: 'Learning programs', recent: 'Recent work', noData: 'No data yet.', assignments: 'Assignments', attempts: 'Attempts', reviews: 'Reviews waiting', complete: 'complete', average: 'average', notScored: 'not scored', program: 'Learning program', assignment: 'Assignment', general: 'General', generated: 'Prepared with Classio' },
  es: { teachingResource: 'Recurso docente', studentCopy: 'Copia del estudiante', teacherCopy: 'Copia del docente', answerKey: 'Clave de respuestas', studentEvidence: 'Evidencia de aprendizaje', overview: 'Resumen', progress: 'Progreso por asignatura', programs: 'Programas de aprendizaje', recent: 'Trabajo reciente', noData: 'Aún no hay datos.', assignments: 'Tareas', attempts: 'Intentos', reviews: 'Revisiones pendientes', complete: 'completado', average: 'promedio', notScored: 'sin calificar', program: 'Programa de aprendizaje', assignment: 'Tarea', general: 'General', generated: 'Preparado con Classio' },
  tr: { teachingResource: 'Öğretim kaynağı', studentCopy: 'Öğrenci kopyası', teacherCopy: 'Öğretmen kopyası', answerKey: 'Cevap anahtarı', studentEvidence: 'Öğrenci öğrenme kanıtı', overview: 'Genel bakış', progress: 'Derse göre ilerleme', programs: 'Öğrenme programları', recent: 'Son çalışmalar', noData: 'Henüz veri yok.', assignments: 'Ödevler', attempts: 'Denemeler', reviews: 'Bekleyen incelemeler', complete: 'tamamlandı', average: 'ortalama', notScored: 'puanlanmadı', program: 'Öğrenme programı', assignment: 'Ödev', general: 'Genel', generated: 'Classio ile hazırlandı' },
} as const;

type DocumentBranding = { brandName: string; department: string; headerEnabled: boolean; footerEnabled: boolean; headerStyle: 'standard' | 'school'; headerLogoUrl: string; footerImageUrl: string; font: string; fontSize: 'compact' | 'standard' | 'large' | 'exam_style' };
function resourceMetaLine(detail: Record<string, unknown>, kind: 'plan' | 'worksheet' | 'exam' | null, locale: DocumentLocale): string {
  if (!kind) return '';
  const labels = { en: ['Subject', 'Topic', 'Stage', 'Level', 'Purpose'], es: ['Asignatura', 'Tema', 'Etapa', 'Nivel', 'Objetivo'], tr: ['Ders', 'Konu', 'Kademe', 'Seviye', 'Amaç'] }[locale];
  const fields = [detail.subject, detail.topic, detail.learner_stage, detail.level_or_band ?? detail.level, kind === 'plan' ? detail.lesson_purpose : undefined];
  const subjects: Record<DocumentLocale, Record<string, string>> = {
    en: { english: 'English', spanish: 'Spanish', mathematics: 'Mathematics', science: 'Science', music: 'Music', study_skills: 'Study skills', turkish: 'Turkish' },
    es: { english: 'Inglés', spanish: 'Español', mathematics: 'Matemáticas', science: 'Ciencias', music: 'Música', study_skills: 'Técnicas de estudio', turkish: 'Turco' },
    tr: { english: 'İngilizce', spanish: 'İspanyolca', mathematics: 'Matematik', science: 'Fen bilimleri', music: 'Müzik', study_skills: 'Çalışma becerileri', turkish: 'Türkçe' },
  };
  const stages: Record<DocumentLocale, Record<string, string>> = {
    en: { early_primary: 'Early primary', upper_primary: 'Upper primary', lower_secondary: 'Lower secondary', upper_secondary: 'Upper secondary', adult_stage: 'Adult' },
    es: { early_primary: 'Primaria inicial', upper_primary: 'Primaria superior', lower_secondary: 'Secundaria inicial', upper_secondary: 'Secundaria superior', adult_stage: 'Adultos' },
    tr: { early_primary: 'İlkokul alt sınıflar', upper_primary: 'İlkokul üst sınıflar', lower_secondary: 'Ortaokul alt sınıflar', upper_secondary: 'Ortaokul üst sınıflar', adult_stage: 'Yetişkin' },
  };
  const purposes: Record<DocumentLocale, Record<string, string>> = {
    en: { introduce_concept: 'Introduce a concept', practice_skill: 'Practice a skill', review_topic: 'Review a topic', diagnose_difficulty: 'Diagnose a difficulty', discussion_exploration: 'Discussion / exploration' },
    es: { introduce_concept: 'Introducir un concepto', practice_skill: 'Practicar una habilidad', review_topic: 'Repasar un tema', diagnose_difficulty: 'Diagnosticar una dificultad', discussion_exploration: 'Discusión / exploración' },
    tr: { introduce_concept: 'Kavram tanıtma', practice_skill: 'Beceri uygulama', review_topic: 'Konuyu gözden geçirme', diagnose_difficulty: 'Zorluğu belirleme', discussion_exploration: 'Tartışma / keşif' },
  };
  const display = (value: unknown, index: number) => {
    const raw = String(value).trim();
    if (index === 0) return subjects[locale][canonicalSubjectKey(raw)] || raw;
    if (index === 2) return stages[locale][canonicalLearnerStageKey(raw)] || raw.replaceAll('_', ' ');
    if (index === 4) return purposes[locale][lessonPurposeKey(raw)] || raw.replaceAll('_', ' ');
    return raw;
  };
  const parts = fields.map((value, index) => value ? `${labels[index]}: ${display(value, index)}` : '').filter(Boolean);
  if (kind === 'worksheet') {
    const rawType = String(record(detail.worksheet_json).worksheet_type ?? detail.worksheet_type ?? '').trim();
    const types: Record<DocumentLocale, Record<string, string>> = {
      en: { reading_comprehension: 'Reading comprehension', short_answer: 'Short answers', fill_in_the_blanks: 'Fill in the blanks', fill_in_blank: 'Fill in the blanks', multiple_choice: 'Multiple choice', true_false: 'True / false', matching: 'Matching', word_search_vocab: 'Word search', error_correction: 'Error correction' },
      es: { reading_comprehension: 'Comprensión lectora', short_answer: 'Respuestas cortas', fill_in_the_blanks: 'Completar espacios', fill_in_blank: 'Completar espacios', multiple_choice: 'Selección múltiple', true_false: 'Verdadero / falso', matching: 'Relacionar', word_search_vocab: 'Sopa de letras', error_correction: 'Corrección de errores' },
      tr: { reading_comprehension: 'Okuduğunu anlama', short_answer: 'Kısa cevaplar', fill_in_the_blanks: 'Boşluk doldurma', fill_in_blank: 'Boşluk doldurma', multiple_choice: 'Çoktan seçmeli', true_false: 'Doğru / yanlış', matching: 'Eşleştirme', word_search_vocab: 'Kelime avı', error_correction: 'Hata düzeltme' },
    };
    if (rawType) parts.splice(2, 0, `${{ en: 'Worksheet type', es: 'Tipo de ficha', tr: 'Çalışma kâğıdı türü' }[locale]}: ${types[locale][rawType] || rawType.replaceAll('_', ' ')}`);
  }
  if (kind === 'plan') {
    const language = record(detail.plan_json).student_material_language ?? detail.student_material_language;
    if (language) parts.push(`${{ en: 'Student material language', es: 'Idioma del material del estudiante', tr: 'Öğrenci materyali dili' }[locale]}: ${String(language).toUpperCase()}`);
  }
  return parts.join('  |  ');
}
const DEFAULT_BRANDING: DocumentBranding = { brandName: '', department: '', headerEnabled: false, footerEnabled: false, headerStyle: 'standard', headerLogoUrl: '', footerImageUrl: '', font: 'DejaVu Sans', fontSize: 'standard' };

async function loadBranding(): Promise<DocumentBranding> {
  try {
    const data = await getBrandingSettings();
    const fontMap: Record<string, string> = { dejavu: 'DejaVu Sans', open_sans: 'Open Sans', yavuz: 'Yavuz Bagis Dik Temel', arial: 'Arial', calibri: 'Calibri', times: 'Times New Roman', comic_sans: 'Comic Sans MS' };
    return { ...data, font: fontMap[data.font] || 'DejaVu Sans' };
  } catch { return DEFAULT_BRANDING; }
}

function slug(value: string) {
  return value.normalize('NFKD').replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '').toLowerCase() || 'classio-document';
}

function browserReady() {
  return Platform.OS === 'web' && typeof document !== 'undefined';
}

const pdfFontData = new Map<string, Promise<[string, string]>>();
async function loadPdfFontData(font: string): Promise<[string, string]> {
  const names = font === 'Open Sans' ? ['OpenSans-Regular.ttf', 'OpenSans-Bold.ttf'] : font === 'Yavuz Bagis Dik Temel' ? ['YavuzBagis.ttf', 'YavuzBagis.ttf'] : ['DejaVuSans.ttf', 'DejaVuSans-Bold.ttf'];
  if (!pdfFontData.has(font)) pdfFontData.set(font, Promise.all(names.map(async (name) => {
    const response = await fetch(`/fonts/${name}`);
    if (!response.ok) throw new Error(`PDF font could not be loaded: ${name}`);
    const bytes = new Uint8Array(await response.arrayBuffer());
    let binary = '';
    for (let offset = 0; offset < bytes.length; offset += 8192) binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
    return btoa(binary);
  })) as Promise<[string, string]>);
  try { return await pdfFontData.get(font)!; } catch (error) { pdfFontData.delete(font); throw error; }
}

async function loadClassioLogo(): Promise<Uint8Array | null> {
  try { const response = await fetch('/logo_classio_light.png'); return response.ok ? new Uint8Array(await response.arrayBuffer()) : null; } catch { return null; }
}

async function loadBrandingImage(url: string): Promise<{ bytes: Uint8Array; type: 'PNG' | 'JPEG' } | null> {
  if (!url) return null;
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes.length > 2 * 1024 * 1024) return null;
    if (bytes[0] === 137 && bytes[1] === 80) return { bytes, type: 'PNG' };
    if (bytes[0] === 255 && bytes[1] === 216) return { bytes, type: 'JPEG' };
  } catch { /* A missing image must not block a document download. */ }
  return null;
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
    const contact = ['email', 'phone', 'location', 'date_of_birth', 'sex'].map((key) => { const value = String(detail[key] || '').trim(); if (key !== 'sex') return value; const sex = { en: { male: 'Male', female: 'Female', other: 'Other' }, es: { male: 'Hombre', female: 'Mujer', other: 'Otro' }, tr: { male: 'Erkek', female: 'Kadın', other: 'Diğer' } }[locale]; return (sex as Record<string, string>)[value.toLowerCase()] || value; }).filter(Boolean);
    if (detail.role) result.push({ heading: '', lines: [String(detail.role)] });
    if (contact.length) result.push({ heading: '', lines: [contact.join('  |  ')] });
    if (detail.professional_summary) result.push({ heading: copy.summary, lines: [String(detail.professional_summary)] });
    for (const key of ['subjects', 'teaching_stages', 'teaching_languages', 'education', 'certifications', 'experience', 'skills'] as const) {
      const lines = list(detail[key]).map(String).filter(Boolean);
      if (lines.length) result.push({ heading: copy[key], lines, bulleted: true });
    }
    const availability = [detail.availability ? `${{ en: 'Availability', es: 'Disponibilidad', tr: 'Uygunluk' }[locale]}: ${String(detail.availability).trim()}` : '', detail.rate ? `${{ en: 'Rate', es: 'Tarifa', tr: 'Ücret' }[locale]}: ${String(detail.rate).trim()}` : ''].filter(Boolean);
    if (availability.length) result.push({ heading: copy.availability, lines: availability });
    return result;
  }
  if (typeof detail.cover_letter === 'string') {
    const lines = detail.cover_letter.split(/\n\s*\n/).map((paragraph) => paragraph.trim()).filter(Boolean);
    return [{ heading: '', lines }];
  }
  return null;
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function mappingSide(input: unknown, prefer: 'key' | 'value'): string {
  let value = input;
  if (typeof value === 'string' && value.trim().startsWith('{')) {
    try { value = JSON.parse(value); } catch { /* Keep plain text. */ }
  }
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const entries = Object.entries(value as Record<string, unknown>);
    if (prefer in (value as Record<string, unknown>)) return String((value as Record<string, unknown>)[prefer] ?? '').trim();
    if (entries.length === 1) return String(prefer === 'key' ? entries[0][0] : entries[0][1] ?? '').trim();
    return String((value as Record<string, unknown>).text ?? (value as Record<string, unknown>).answer ?? '').trim();
  }
  return String(value ?? '').trim();
}

function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function readyVisual(value: unknown): string | null {
  const support = record(value);
  const url = String(support.image_data_url || '').trim();
  return support.status === 'ready' && /^data:image\/(?:png|jpe?g);base64,[A-Za-z0-9+/=]+$/i.test(url) ? url : null;
}

function visualBytes(url: string): Uint8Array {
  const binary = atob(url.slice(url.indexOf(',') + 1));
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function visualDimensions(bytes: Uint8Array): { width: number; height: number } | null {
  if (bytes.length >= 24 && bytes[0] === 137 && bytes[1] === 80 && bytes[2] === 78 && bytes[3] === 71) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    return { width: view.getUint32(16), height: view.getUint32(20) };
  }
  if (bytes[0] === 255 && bytes[1] === 216) {
    let offset = 2;
    while (offset + 9 < bytes.length) {
      if (bytes[offset] !== 255) break;
      const marker = bytes[offset + 1];
      const length = (bytes[offset + 2] << 8) + bytes[offset + 3];
      if (length < 2) break;
      if ([192, 193, 194, 195, 198, 199, 201, 202].includes(marker)) return { height: (bytes[offset + 5] << 8) + bytes[offset + 6], width: (bytes[offset + 7] << 8) + bytes[offset + 8] };
      offset += 2 + length;
    }
  }
  return null;
}

function fittedImageSize(bytes: Uint8Array, maxWidth: number, maxHeight: number) {
  const dimensions = visualDimensions(bytes);
  if (!dimensions?.width || !dimensions.height) return { width: maxWidth, height: maxHeight };
  const scale = Math.min(maxWidth / dimensions.width, maxHeight / dimensions.height);
  return { width: dimensions.width * scale, height: dimensions.height * scale };
}

async function fadedWatermark(url: string): Promise<string | null> {
  if (!browserReady()) return null;
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    const context = canvas.getContext('2d');
    if (!context) return null;
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.globalAlpha = 0.10;
    context.drawImage(image, 0, 0);
    return canvas.toDataURL('image/png');
  } catch { return null; }
}

function structuredTextLines(value: unknown, title: unknown, blocks: unknown): string[] {
  const lines: string[] = [];
  if (String(title || '').trim()) lines.push(String(title).trim());
  const structured = list(blocks).map(record).filter((block) => String(block.text || '').trim());
  if (structured.length) {
    for (const block of structured) {
      const content = String(block.text).replace(/\r\n?/g, '\n').trim();
      const kind = String(block.type || '').toLowerCase();
      if (kind === 'turn' && block.speaker) lines.push(`${String(block.speaker).trim()}: ${content}`);
      else if (['from', 'to', 'subject'].includes(kind)) lines.push(`${kind[0].toUpperCase()}${kind.slice(1)}: ${content}`);
      else lines.push(...content.split(/\n\s*\n|\n/).map((part) => part.trim()).filter(Boolean));
    }
    return lines;
  }
  lines.push(...String(value || '').replace(/\r\n?/g, '\n').split(/\n\s*\n|\n/).map((part) => part.trim()).filter(Boolean));
  return lines;
}

function planSections(detail: Record<string, unknown>, locale: DocumentLocale): ReportSection[] | null {
  const plan = Object.keys(record(detail.plan_json)).length ? record(detail.plan_json) : detail;
  if (!plan.objective && !plan.core_material && !plan.warm_up) return null;
  const label = (key: string) => (sourceDocumentLabels[locale] as Record<string, string>)[key] || labelize(key);
  const group = (heading: string, entries: [string, unknown][], pageBreak = false): ReportSection | null => {
    const planBlocks = entries.flatMap(([key, value]): PlanBlock[] => {
      const lines = (Array.isArray(value) ? value : [value]).flatMap((item) => printable(item)).map((line) => line.trim()).filter(Boolean);
      return lines.length ? [{ label: label(key === 'objective' ? 'lesson_objective' : key), lines: key === 'target_vocabulary' ? [lines.join(', ')] : lines, list: Array.isArray(value) && key !== 'target_vocabulary' }] : [];
    });
    return planBlocks.length ? { heading, lines: [], planBlocks, pageBreak } : null;
  };
  const core = record(plan.core_material);
  const materialsOrder = ['target_vocabulary', 'language_frames', 'pre_task_questions', 'reading_passage', 'listening_script', 'gist_questions', 'detail_questions', 'worked_example', 'independent_practice', 'common_error_alert', 'concept_explanation', 'real_life_application', 'strategy_steps', 'performance_goal', 'materials_needed', 'timing_guide', 'expected_output', 'differentiation', 'assessment_check', 'student_checklist', 'key_concept', 'guided_problem_set', 'independent_problem_set', 'challenge_problem', 'answer_key', 'phenomenon_prompt', 'prediction_task', 'observation_task', 'evidence_questions', 'misconception_alert', 'technical_focus', 'practice_pattern', 'teacher_model', 'strategy_name', 'model_scenario', 'student_action_plan', 'post_task'];
  const materials = materialsOrder.map((key): [string, unknown] => [key, key === 'reading_passage' || key === 'listening_script' ? plan[key] : core[key]]);
  return [
    { ...(group(label('lesson_overview').toUpperCase(), [['objective', plan.objective], ['success_criteria', plan.success_criteria]]) || { heading: label('lesson_overview').toUpperCase(), lines: [], planBlocks: [] }), planOverview: true },
    group(label('lesson_flow').toUpperCase(), [['warm_up', plan.warm_up], ['main_activity', plan.main_activity], ['guided_practice', plan.guided_practice], ['freer_task', plan.freer_task], ['wrap_up', plan.wrap_up]]),
    group(label('teacher_notes').toUpperCase(), [['core_examples', plan.core_examples], ['practice_questions', plan.practice_questions], ['teacher_moves', plan.teacher_moves], ['extension_task', plan.extension_task], ['optional_homework', plan.homework]]),
    group(label('lesson_materials').toUpperCase(), materials, true),
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

// Models sometimes include their own item number despite the prompt. Number only once at render time.
function withoutQuestionNumber(value: string): string {
  return value.trim().replace(/^(?:\d{1,3}[.)]\s+)+/, '').trim();
}

function examSections(detail: Record<string, unknown>, variant: ResourceVariant, locale: DocumentLocale): ReportSection[] | null {
  const exam = Object.keys(record(detail.exam_data)).length ? record(detail.exam_data) : detail;
  const sections = list(exam.sections).map(record).filter((section) => Object.keys(section).length);
  if (!sections.length || detail.worksheet_json || detail.worksheet_type || detail.plan_json) return null;

  const key = detail.answer_key ?? exam.answer_key;
  const keyedSections = list(record(key).sections).map(record);
  const flatAnswers = Array.isArray(key) ? key : list(record(key).answers);
  const output: ReportSection[] = [];
  if (variant !== 'answers' && String(exam.instructions || '').trim()) {
    output.push({ heading: { en: 'Instructions', es: 'Instrucciones', tr: 'Yönergeler' }[locale], lines: [String(exam.instructions).trim()] });
  }
  if (variant !== 'answers') {
    for (const [sectionIndex, section] of sections.entries()) {
      const lines: string[] = [];
      const sectionType = String(section.type || '');
      const wordSearch = sectionType === 'word_search_vocab' || sectionType === 'word_search';
      if (String(section.instructions || '').trim()) lines.push(String(section.instructions).trim());
      if (String(section.source_text || '').trim()) lines.push(...structuredTextLines(section.source_text, section.text_title, section.text_blocks));
      const table = record(section.table_data);
      if (String(table.title || '').trim()) lines.push(String(table.title).trim());
      if (String(table.caption || '').trim()) lines.push(String(table.caption).trim());
      const columns = list(table.columns).map(String).filter(Boolean);
      const dataRows = list(table.rows).map((row) => list(row).map(String)).filter((row) => row.length);
      const words = wordSearch ? list(section.vocabulary_bank || section.words || section.questions).map((item) => {
          const row = record(item);
          return String(Object.keys(row).length ? row.word || row.term || row.left || row.text || row.stem || '' : item).trim();
        }).filter(Boolean) : [];
      if (words.length) lines.push(words.join('  ·  '));
      for (const [questionIndex, question] of (wordSearch ? [] : list(section.questions)).entries()) {
        const row = record(question);
        const prompt = typeof question === 'string' ? question : String(row.stem || row.text || row.question || row.sentence || row.prompt || row.original || '');
        if (prompt.trim()) lines.push(`${questionIndex + 1}. ${sectionType === 'fill_in_blank' ? withoutQuestionNumber(prompt).replaceAll('___', '______________') : withoutQuestionNumber(prompt)}`);
        for (const [optionIndex, option] of list(row.options).entries()) {
          lines.push(`   ${String.fromCharCode(65 + optionIndex)}) ${String(option)}`);
        }
        const responseTypes = ['short_answer', 'reading_comprehension', 'writing_prompt', 'problem_solving', 'equation_solving', 'word_problems', 'data_analysis', 'classification', 'process_explanation', 'hypothesis_and_conclusion', 'diagram_questions', 'theory_questions', 'symbol_identification', 'rhythm_counting', 'terminology', 'composer_period_matching', 'show_your_work', 'vocabulary', 'sentence_transformation', 'error_correction', 'table_interpretation'];
        if (prompt.trim() && responseTypes.includes(sectionType)) lines.push(...Array(sectionType === 'writing_prompt' || sectionType === 'show_your_work' ? 5 : 2).fill('_'.repeat(50)));
      }
      const questions = list(section.questions);
      const tableRows = sectionType === 'matching' ? questions.map((question, index) => {
        const pair = record(question);
        return [`${index + 1}. ${mappingSide(pair.left, 'key')}`, '[   ]', `${String.fromCharCode(97 + index)}) ${mappingSide(record(questions[(index + 1) % questions.length]).right, 'value')}`];
      }) : sectionType === 'true_false' ? questions.map((question, index) => {
        const row = record(question);
        const prompt = typeof question === 'string' ? question : String(row.stem || row.text || row.question || row.sentence || row.prompt || '');
        return [`${index + 1}. ${withoutQuestionNumber(prompt)}`, locale === 'es' ? '[ ] V  [ ] F' : locale === 'tr' ? '[ ] D  [ ] Y' : '[ ] T  [ ] F'];
      }) : undefined;
      const visual = readyVisual(section.visual_support);
      const rawGrid = wordSearch ? list(section.wordsearch_grid || section.grid) : [];
      const grid = wordSearch ? (rawGrid.length ? rawGrid : makeWordSearchGrid(words)).map((row) => list(row).map(String)).filter((row) => row.length) : [];
      if (lines.length || tableRows?.length || dataRows.length || visual || grid.length) output.push({ heading: String(section.title || labelize(String(section.type || `Section ${sectionIndex + 1}`))), lines: tableRows?.length ? lines.filter((line) => !/^\d+\.\s/.test(line)) : lines, table: tableRows || (columns.length || dataRows.length ? [...(columns.length ? [columns] : []), ...dataRows] : undefined), grid: grid.length ? grid : undefined, visuals: visual && !wordSearch ? [visual] : undefined, watermark: visual && wordSearch ? visual : undefined });
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
        output.push({ heading: `${COPY[locale].answerKey} · ${String(keyedSections[sectionIndex]?.title || section.title || sectionIndex + 1)}`, lines: answers.map((answer, index) => `${index + 1}. ${answer}`), pdfPageBreak: variant !== 'answers' && sectionIndex === 0 });
      }
    }
  }
  return output;
}

function worksheetSections(detail: Record<string, unknown>, variant: ResourceVariant, locale: DocumentLocale): ReportSection[] | null {
  const worksheet = Object.keys(record(detail.worksheet_json)).length ? record(detail.worksheet_json) : detail;
  if (detail.worksheet_json === undefined && !worksheet.worksheet_type && !(worksheet.sections && worksheet.answer_key)) return null;
  const copy = { en: { instructions: 'Instructions', questions: 'Questions', passage: 'Reading passage', source: 'Source text', answers: 'Answer key', matching: 'Match the items', vocabulary: 'Vocabulary bank', teacherNotes: 'Teacher notes' }, es: { instructions: 'Instrucciones', questions: 'Preguntas', passage: 'Texto de lectura', source: 'Texto de apoyo', answers: 'Clave de respuestas', matching: 'Relaciona los elementos', vocabulary: 'Banco de vocabulario', teacherNotes: 'Notas docentes' }, tr: { instructions: 'Yönergeler', questions: 'Sorular', passage: 'Okuma metni', source: 'Kaynak metin', answers: 'Cevap anahtarı', matching: 'Öğeleri eşleştir', vocabulary: 'Kelime havuzu', teacherNotes: 'Öğretmen notları' } }[locale];
  const output: ReportSection[] = [];
  const wordSearch = worksheet.worksheet_type === 'word_search_vocab' ? (() => {
    const words = list(worksheet.vocabulary_bank);
    const stored = list(worksheet.wordsearch_grid || worksheet.grid).map((row) => list(row).map(String)).filter((row) => row.length);
    const puzzle = stored.length ? { grid: stored, placements: findWordSearchPlacements(stored, words) } : makeWordSearchPuzzle(words);
    const answerCells: [number, number][] = puzzle.placements.flatMap((placement: WordSearchPlacement) => {
      const dr = Math.sign(placement.end[0] - placement.start[0]);
      const dc = Math.sign(placement.end[1] - placement.start[1]);
      return Array.from({ length: [...placement.word].length }, (_, index) => [placement.start[0] + dr * index, placement.start[1] + dc * index] as [number, number]);
    });
    return { grid: puzzle.grid, answerCells };
  })() : null;
  if (variant !== 'answers') {
    if (String(worksheet.instructions || '').trim()) output.push({ heading: copy.instructions, lines: [String(worksheet.instructions).trim()] });
    if (worksheet.worksheet_type !== 'word_search_vocab') {
      const visuals = list(worksheet.visual_supports).map(readyVisual).filter((url): url is string => Boolean(url));
      if (visuals.length) output.push({ heading: '', lines: [], visuals });
    }
    const vocabulary = list(worksheet.vocabulary_bank).map(String).filter(Boolean);
    if (vocabulary.length) {
      const columns = vocabulary.some((word) => /\s[-–—:]\s?/.test(word)) ? 2 : 5;
      const rows = Array.from({ length: Math.ceil(vocabulary.length / columns) }, (_, row) => vocabulary.slice(row * columns, (row + 1) * columns));
      output.push({ heading: copy.vocabulary, lines: [], table: rows.map((row) => [...row, ...Array(columns - row.length).fill('')]), vocabularyTable: true });
    }
    const passage = String(worksheet.reading_passage || worksheet.source_text || '').trim();
    if (passage) output.push({ heading: worksheet.worksheet_type === 'reading_comprehension' ? copy.passage : copy.source, lines: structuredTextLines(passage, worksheet.text_title, worksheet.text_blocks) });
    const sections = list(worksheet.sections).map(record).filter((section) => Object.keys(section).length);
    if (sections.length) {
      for (const [sectionIndex, section] of sections.entries()) {
        const lines: string[] = [];
        if (section.instructions) lines.push(String(section.instructions));
        for (const [questionIndex, question] of list(section.questions).entries()) {
          const row = record(question);
          const prompt = typeof question === 'string' ? question : String(row.prompt || row.stem || row.question || row.text || row.sentence || '');
          if (prompt.trim()) { lines.push(`${questionIndex + 1}. ${withoutQuestionNumber(prompt)}`); if (['short_answer', 'reading_comprehension'].includes(String(worksheet.worksheet_type || section.type))) lines.push('____________________________________________', '____________________________________________'); else if (String(worksheet.worksheet_type || section.type) === 'error_correction') lines.push(`${{ en: 'Correction', es: 'Corrección', tr: 'Düzeltme' }[locale]}: _____________________`); }
          for (const [optionIndex, option] of list(row.options).entries()) lines.push(`   ${String.fromCharCode(65 + optionIndex)}) ${String(option)}`);
        }
        if (lines.length) output.push({ heading: String(section.title || `${copy.questions} ${sectionIndex + 1}`), lines });
      }
    } else if (worksheet.worksheet_type === 'matching') {
      const pairs = list(worksheet.matching_pairs).map(record);
      const left = (pairs.length ? pairs.map((pair) => pair.left ?? pair.term) : list(worksheet.left_items)).map((item) => mappingSide(item, 'key'));
      const right = (pairs.length ? pairs.map((pair) => pair.right ?? pair.definition) : list(worksheet.right_items)).map((item) => mappingSide(item, 'value'));
      const choices = right.length > 1 ? [...right.slice(1), right[0]] : right;
      const lines = left.map((item, index) => `${index + 1}. ${String(item || '')}   [   ]`);
      lines.push(...choices.map((item, index) => `${String.fromCharCode(97 + index)}) ${String(item || '')}`));
      const table = left.map((item, index) => [`${index + 1}. ${String(item || '')}`, '[   ]', `${String.fromCharCode(97 + index)}) ${String(choices[index] || '')}`]);
      if (lines.length) output.push({ heading: copy.matching, lines: [], table });
    } else if (worksheet.worksheet_type === 'word_search_vocab') {
      const grid = wordSearch?.grid || [];
      const watermark = list(worksheet.visual_supports).map(readyVisual).find(Boolean) || undefined;
      if (grid.length) output.push({ heading: locale === 'es' ? 'Sopa de letras' : locale === 'tr' ? 'Kelime avı' : 'Word search', lines: grid.map((row) => row.join('  ')), grid, watermark });
    } else {
      const items = list(worksheet.multiple_choice_items).length ? list(worksheet.multiple_choice_items) : list(worksheet.questions).length ? list(worksheet.questions) : list(worksheet.true_false_statements);
      const lines: string[] = [];
      for (const [index, item] of items.entries()) {
        const row = record(item);
        const prompt = typeof item === 'string' ? item : String(row.stem || row.question || row.prompt || row.text || row.sentence || '');
        const trueFalse = locale === 'es' ? '   [ ] Verdadero   [ ] Falso' : locale === 'tr' ? '   [ ] Doğru   [ ] Yanlış' : '   [ ] True   [ ] False';
        if (prompt.trim()) { lines.push(`${index + 1}. ${withoutQuestionNumber(prompt)}${worksheet.worksheet_type === 'true_false' ? trueFalse : ''}`); if (['short_answer', 'reading_comprehension'].includes(String(worksheet.worksheet_type))) lines.push('____________________________________________', '____________________________________________'); if (worksheet.worksheet_type === 'error_correction') lines.push(`${{ en: 'Correction', es: 'Corrección', tr: 'Düzeltme' }[locale]}: _____________________`); }
        for (const [optionIndex, option] of list(row.options).entries()) lines.push(`   ${String.fromCharCode(65 + optionIndex)}) ${String(option)}`);
      }
      const table = worksheet.worksheet_type === 'true_false' ? items.map((item, index) => {
        const row = record(item);
        const prompt = typeof item === 'string' ? item : String(row.stem || row.question || row.prompt || row.text || row.sentence || '');
        return [`${index + 1}. ${withoutQuestionNumber(prompt)}`, locale === 'es' ? '[ ] V  [ ] F' : locale === 'tr' ? '[ ] D  [ ] Y' : '[ ] T  [ ] F'];
      }) : undefined;
      if (lines.length) output.push({ heading: copy.questions, lines: table ? [] : lines, table });
    }
  }
  if (variant !== 'student') {
    const key = detail.answer_key ?? worksheet.answer_key;
    const keyLines = typeof key === 'string' ? key.split(/\r?\n|\s*;\s*/).map((line) => line.trim()).filter(Boolean) : Array.isArray(key) ? key.map(examAnswer).filter(Boolean) : Object.entries(record(key)).map(([number, answer]) => `${number}. ${examAnswer(answer)}`).filter((line) => !line.endsWith('. '));
    if (!keyLines.length && worksheet.worksheet_type === 'matching') {
      const pairs = list(worksheet.matching_pairs).map(record);
      const answers = (pairs.length ? pairs.map((pair) => pair.right ?? pair.definition) : list(worksheet.right_items)).map((item) => mappingSide(item, 'value'));
      const choices = answers.length > 1 ? [...answers.slice(1), answers[0]] : answers;
      keyLines.push(...answers.map((_answer, index) => `${index + 1} → ${String.fromCharCode(97 + (choices.length > 1 ? (index + choices.length - 1) % choices.length : index))}`));
    }
    if (!keyLines.length && worksheet.worksheet_type === 'multiple_choice') {
      keyLines.push(...list(worksheet.multiple_choice_items).map((item, index) => `${index + 1}. ${examAnswer(record(item).answer ?? record(item).correct_answer)}`).filter((line) => !line.endsWith('. ')));
    }
    if (wordSearch?.grid.length) output.push({ heading: copy.answers, lines: [], grid: wordSearch.grid, answerCells: wordSearch.answerCells, pdfPageBreak: true });
    else if (keyLines.length) output.push({ heading: copy.answers, lines: keyLines, pdfPageBreak: true });
    const teacherNotes = list(worksheet.teacher_notes).map(String).filter(Boolean);
    if (teacherNotes.length && variant !== 'answers') output.push({ heading: copy.teacherNotes, lines: teacherNotes, pdfPageBreak: !keyLines.length && !wordSearch?.grid.length });
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
  const program = detail.program_data && typeof detail.program_data === 'object' ? detail.program_data as Record<string, unknown> : Array.isArray(detail.units) ? detail : null;
  if (program && Array.isArray(program.units)) {
    const terms = { en: { overview: 'Program overview', unit: 'Unit', topic: 'Topic', labels: { program_overview: 'Overview', teacher_rationale: 'Teaching rationale', scope_and_sequence_rationale: 'Scope and sequence', core_progression_priorities: 'Progression priorities', entry_profile: 'Entry profile', exit_profile: 'Exit profile', prerequisite_summary: 'Prerequisites', student_summary: 'For students', assessment_strategy: 'Assessment strategy', resource_strategy: 'Resource strategy', delivery_design_notes: 'Delivery design', non_classio_support_strategy: 'Other learning support', best_practice_frameworks: 'Teaching frameworks', unit_objectives: 'Unit objectives', recommended_lesson_purposes: 'Recommended lesson purposes', recommended_worksheet_types: 'Recommended worksheets', recommended_exam_exercise_types: 'Recommended exam exercises', recommended_non_classio_activities: 'Other activities', delivery_notes: 'Delivery notes', estimated_lessons: 'Estimated lessons', subtopic: 'Subtopic', lesson_focus: 'Lesson focus', lesson_purpose: 'Lesson purpose', learning_objectives: 'Learning objectives', success_criteria: 'Success criteria', student_can_do: 'Student can do', suggested_worksheet_types: 'Suggested worksheets', suggested_exam_exercise_types: 'Suggested exam exercises', suggested_non_classio_activities: 'Other suggested activities', homework_idea: 'Homework idea', teacher_notes: 'Teacher notes' } }, es: { overview: 'Resumen del programa', unit: 'Unidad', topic: 'Tema', labels: { program_overview: 'Descripción general', teacher_rationale: 'Fundamento docente', scope_and_sequence_rationale: 'Alcance y secuencia', core_progression_priorities: 'Prioridades de progresión', entry_profile: 'Perfil de entrada', exit_profile: 'Perfil de salida', prerequisite_summary: 'Conocimientos previos', student_summary: 'Para estudiantes', assessment_strategy: 'Estrategia de evaluación', resource_strategy: 'Estrategia de recursos', delivery_design_notes: 'Diseño didáctico', non_classio_support_strategy: 'Apoyo externo', best_practice_frameworks: 'Marcos pedagógicos', unit_objectives: 'Objetivos de la unidad', recommended_lesson_purposes: 'Propósitos recomendados', recommended_worksheet_types: 'Fichas recomendadas', recommended_exam_exercise_types: 'Ejercicios de examen recomendados', recommended_non_classio_activities: 'Otras actividades', delivery_notes: 'Notas de implementación', estimated_lessons: 'Clases estimadas', subtopic: 'Subtema', lesson_focus: 'Enfoque de la clase', lesson_purpose: 'Propósito de la clase', learning_objectives: 'Objetivos de aprendizaje', success_criteria: 'Criterios de logro', student_can_do: 'El estudiante puede', suggested_worksheet_types: 'Fichas sugeridas', suggested_exam_exercise_types: 'Ejercicios de examen sugeridos', suggested_non_classio_activities: 'Otras actividades sugeridas', homework_idea: 'Idea para casa', teacher_notes: 'Notas docentes' } }, tr: { overview: 'Program özeti', unit: 'Ünite', topic: 'Konu', labels: { program_overview: 'Genel bakış', teacher_rationale: 'Öğretim gerekçesi', scope_and_sequence_rationale: 'Kapsam ve sıra', core_progression_priorities: 'İlerleme öncelikleri', entry_profile: 'Başlangıç profili', exit_profile: 'Bitiş profili', prerequisite_summary: 'Ön koşullar', student_summary: 'Öğrenciler için', assessment_strategy: 'Değerlendirme stratejisi', resource_strategy: 'Kaynak stratejisi', delivery_design_notes: 'Öğretim tasarımı', non_classio_support_strategy: 'Dış öğrenme desteği', best_practice_frameworks: 'Öğretim çerçeveleri', unit_objectives: 'Ünite hedefleri', recommended_lesson_purposes: 'Önerilen ders amaçları', recommended_worksheet_types: 'Önerilen çalışma kâğıtları', recommended_exam_exercise_types: 'Önerilen sınav alıştırmaları', recommended_non_classio_activities: 'Diğer etkinlikler', delivery_notes: 'Uygulama notları', estimated_lessons: 'Tahmini ders sayısı', subtopic: 'Alt konu', lesson_focus: 'Ders odağı', lesson_purpose: 'Ders amacı', learning_objectives: 'Öğrenme hedefleri', success_criteria: 'Başarı ölçütleri', student_can_do: 'Öğrenci yapabilir', suggested_worksheet_types: 'Önerilen çalışma kâğıtları', suggested_exam_exercise_types: 'Önerilen sınav alıştırmaları', suggested_non_classio_activities: 'Diğer önerilen etkinlikler', homework_idea: 'Ev ödevi fikri', teacher_notes: 'Öğretmen notları' } } }[locale];
    const fieldLines = (data: Record<string, unknown>, keys: string[]) => keys.flatMap((key) => { const value = data[key]; const lines = (Array.isArray(value) ? value : [value]).flatMap((item) => printable(item)); return lines.map((line) => `${(terms.labels as Record<string, string>)[key] || labelize(key)}: ${line}`); });
    const items: ReportSection[] = [{ heading: terms.overview, lines: fieldLines(program, ['program_overview', 'teacher_rationale', 'scope_and_sequence_rationale', 'core_progression_priorities', 'entry_profile', 'exit_profile', 'prerequisite_summary', 'student_summary', 'assessment_strategy', 'resource_strategy', 'delivery_design_notes', 'non_classio_support_strategy', 'best_practice_frameworks']) }];
    for (const [unitIndex, rawUnit] of program.units.entries()) {
      if (!rawUnit || typeof rawUnit !== 'object') continue;
      const unit = rawUnit as Record<string, unknown>;
      items.push({ heading: `${terms.unit} ${unitIndex + 1}: ${String(unit.title || '')}`, lines: [...(unit.overview ? [String(unit.overview)] : []), ...fieldLines(unit, ['unit_objectives', 'recommended_lesson_purposes', 'recommended_worksheet_types', 'recommended_exam_exercise_types', 'recommended_non_classio_activities', 'delivery_notes', 'estimated_lessons'])] });
      for (const [topicIndex, rawTopic] of list(unit.topics).entries()) {
        if (!rawTopic || typeof rawTopic !== 'object') continue;
        const topic = rawTopic as Record<string, unknown>;
        items.push({ heading: `${terms.topic} ${topicIndex + 1}: ${String(topic.title || '')}`, lines: fieldLines(topic, ['subtopic', 'lesson_focus', 'lesson_purpose', 'learning_objectives', 'success_criteria', 'student_can_do', 'suggested_worksheet_types', 'suggested_exam_exercise_types', 'suggested_non_classio_activities', 'delivery_notes', 'homework_idea', 'teacher_notes', 'student_summary', 'estimated_lessons']) });
      }
    }
    return items;
  }
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

async function savePdf(title: string, subtitle: string, sections: ReportSection[], filename: string, locale: DocumentLocale, worksheet = false, bulletLines = true, resourceKind: 'plan' | 'worksheet' | 'exam' | null = null, metaLine = '', profileDocument: 'cv' | 'letter' | null = null, profileImageUrl = '') {
  if (!browserReady()) throw new Error('PDF downloads are available in the web app.');
  // The browser ESM build avoids jsPDF's Node-only optional html2canvas loader in Expo SSR.
  const { jsPDF } = await import('jspdf/dist/jspdf.es.min.js');
  const pdf = new jsPDF({ unit: 'pt', format: 'a4' });
  const branding = await loadBranding();
  const [regularFont, boldFont] = await loadPdfFontData(branding.font);
  pdf.addFileToVFS('DejaVuSans.ttf', regularFont);
  pdf.addFileToVFS('DejaVuSans-Bold.ttf', boldFont);
  pdf.addFont('DejaVuSans.ttf', 'DocumentFont', 'normal');
  pdf.addFont('DejaVuSans-Bold.ttf', 'DocumentFont', 'bold');
  const headerImage = branding.headerEnabled ? await loadBrandingImage(branding.headerLogoUrl) : null;
  const footerImage = branding.footerEnabled ? await loadBrandingImage(branding.footerImageUrl) : null;
  const profileImage = profileDocument === 'cv' ? await loadBrandingImage(profileImageUrl) : null;
  const logo = await loadClassioLogo();
  const width = pdf.internal.pageSize.getWidth();
  const height = pdf.internal.pageSize.getHeight();
  const margin = resourceKind === 'plan' ? 57 : 51;
  const bodySize = profileDocument === 'cv' ? 10 : profileDocument === 'letter' ? 10.5 : (branding.fontSize === 'compact' ? 10 : branding.fontSize === 'large' ? 13 : branding.fontSize === 'exam_style' ? 11 : 12) - (resourceKind === 'plan' ? 0.5 : 0);
  let y = 43;
  const ensureSpace = (needed: number) => { if (y + needed > height - margin) { pdf.addPage(); y = margin; } };
  if (!resourceKind) { pdf.setFillColor(29, 78, 216); pdf.rect(0, 0, width, 10, 'F'); }
  if ((!resourceKind || resourceKind === 'plan') && !branding.headerEnabled && logo) { pdf.addImage(logo, 'PNG', margin, y, 76, 30.4); y += 46; }
  if (branding.headerEnabled) {
    if (branding.headerStyle === 'school') { pdf.setFillColor(239, 246, 255); pdf.roundedRect(margin, y - 15, width - margin * 2, 54, 8, 8, 'F'); }
    if (headerImage) { const dimensions = pdf.getImageProperties(headerImage.bytes); const drawHeight = Math.min(48, 88 * dimensions.height / dimensions.width); pdf.addImage(headerImage.bytes, headerImage.type, branding.headerStyle === 'school' ? (width - 88) / 2 : margin, y - 10, 88, drawHeight); y += drawHeight + 8; }
    pdf.setTextColor(29, 78, 216); pdf.setFont('DocumentFont', 'bold'); pdf.setFontSize(branding.headerStyle === 'school' ? 14 : 10); pdf.text(branding.brandName.toUpperCase(), branding.headerStyle === 'school' ? width / 2 : margin, y, { align: branding.headerStyle === 'school' ? 'center' : 'left' });
    if (branding.department) { y += 14; pdf.setFont('DocumentFont', 'normal'); pdf.setFontSize(8); pdf.setTextColor(71, 85, 105); pdf.text(branding.department, branding.headerStyle === 'school' ? width / 2 : margin, y, { align: branding.headerStyle === 'school' ? 'center' : 'left' }); }
    y += branding.headerStyle === 'school' ? 42 : 24;
  }
  pdf.setTextColor(resourceKind || profileDocument ? 29 : 15, resourceKind || profileDocument ? 78 : 23, resourceKind || profileDocument ? 216 : 42); pdf.setFont('DocumentFont', 'bold'); const titleSize = profileDocument === 'cv' ? 20 : profileDocument === 'letter' ? 14 : resourceKind === 'plan' ? (branding.fontSize === 'large' ? 17 : 13) : resourceKind ? (branding.fontSize === 'large' ? 18 : 14) : 23; pdf.setFontSize(titleSize); const portraitSize = profileImage ? fittedImageSize(profileImage.bytes, 78, 78) : null; const titleWidth = width - margin * 2 - (portraitSize ? 94 : 0); const titleLines = pdf.splitTextToSize(title, titleWidth); const titleY = y; pdf.text(titleLines, resourceKind === 'plan' || resourceKind === 'worksheet' || profileDocument ? margin + titleWidth / 2 : margin, y, { align: resourceKind === 'plan' || resourceKind === 'worksheet' || profileDocument ? 'center' : 'left' }); y += titleLines.length * (titleSize + 4) + 8; if (profileImage && portraitSize) { pdf.addImage(profileImage.bytes, profileImage.type, width - margin - portraitSize.width, titleY - 12, portraitSize.width, portraitSize.height); y = Math.max(y, titleY - 12 + portraitSize.height + 8); }
  if (metaLine && !(worksheet && branding.headerEnabled && branding.headerStyle === 'school')) {
    pdf.setFontSize(resourceKind === 'plan' ? bodySize - 1.5 : 9); pdf.setTextColor(51, 65, 85);
    let metaX = margin;
    for (const [index, part] of metaLine.split(/\s+\|\s+/).entries()) {
      const separator = index ? '  |  ' : '';
      const colon = part.indexOf(':');
      const label = colon >= 0 ? `${part.slice(0, colon + 1)} ` : '';
      const value = colon >= 0 ? part.slice(colon + 1).trim() : part;
      pdf.setFont('DocumentFont', 'normal');
      const separatorWidth = pdf.getTextWidth(separator);
      pdf.setFont('DocumentFont', 'bold');
      const labelWidth = pdf.getTextWidth(label);
      pdf.setFont('DocumentFont', 'normal');
      const valueWidth = pdf.getTextWidth(value);
      if (metaX > margin && metaX + separatorWidth + labelWidth + valueWidth > width - margin) { metaX = margin; y += 14; }
      if (separator && metaX > margin) { pdf.text(separator, metaX, y); metaX += separatorWidth; }
      pdf.setFont('DocumentFont', 'bold'); pdf.text(label, metaX, y); metaX += labelWidth;
      pdf.setFont('DocumentFont', 'normal');
      const wrapped = pdf.splitTextToSize(value, width - margin - metaX);
      pdf.text(wrapped, metaX, y);
      if (wrapped.length > 1) { y += (wrapped.length - 1) * 14; metaX = margin + pdf.getTextWidth(wrapped[wrapped.length - 1]); }
      else metaX += valueWidth;
    }
    y += 19;
  }
  if (worksheet && branding.headerEnabled && branding.headerStyle === 'school') {
    pdf.setFont('DocumentFont', 'bold'); pdf.setFontSize(8); pdf.setTextColor(51, 65, 85);
    schoolFields(locale).forEach((field, index) => pdf.text(field, margin + index * ((width - margin * 2) / 3), y + 8));
    y += 28; pdf.setDrawColor(203, 213, 225); pdf.line(margin, y, width - margin, y); y += 16;
  }
  if (!resourceKind && !profileDocument) { pdf.setFillColor(248, 250, 252); pdf.setDrawColor(203, 213, 225); pdf.roundedRect(margin, y, width - margin * 2, 34, 6, 6, 'FD'); pdf.setTextColor(71, 85, 105); pdf.setFont('DocumentFont', 'normal'); pdf.setFontSize(9); pdf.text(subtitle, margin + 12, y + 14); pdf.text(new Date().toLocaleDateString(), width - margin - 12, y + 14, { align: 'right' }); y += 56; }
  let cvRuleDrawn = false;
  for (const section of sections) {
    if (profileDocument === 'cv' && section.heading && !cvRuleDrawn) { pdf.setDrawColor(59, 130, 246); pdf.setLineWidth(1.5); pdf.line(margin, y, width - margin, y); y += 15; cvRuleDrawn = true; }
    if (section.pdfPageBreak && resourceKind && y > margin + 30) { pdf.addPage(); y = margin; }
    if (resourceKind === 'plan' && section.planBlocks) {
      if (section.pageBreak && y > margin + 30) { pdf.addPage(); y = margin; }
      ensureSpace(45);
      pdf.setTextColor(15, 23, 42); pdf.setFont('DocumentFont', 'bold'); pdf.setFontSize(branding.fontSize === 'large' ? 15.5 : 13.5);
      pdf.text(section.heading, margin, y); y += 25;
      if (section.planOverview) {
        const gap = 12;
        const cellWidth = (width - margin * 2 - gap) / 2;
        const content = section.planBlocks.slice(0, 2);
        const layouts = content.map((block) => {
          pdf.setFontSize(bodySize);
          const lines = block.lines.flatMap((line) => pdf.splitTextToSize(line, cellWidth - 20));
          return { block, lines };
        });
        const boxHeight = Math.max(70, ...layouts.map(({ lines }) => 37 + lines.length * (bodySize + 4) + 9));
        ensureSpace(boxHeight + 15);
        layouts.forEach(({ block, lines }, index) => {
          const x = margin + index * (cellWidth + gap);
          pdf.setDrawColor(37, 99, 235); pdf.setLineWidth(1.3); pdf.roundedRect(x, y, cellWidth, boxHeight, 5, 5, 'S');
          pdf.setFont('DocumentFont', 'bold'); pdf.setFontSize(bodySize); pdf.setTextColor(15, 23, 42); pdf.text(block.label, x + 10, y + 19);
          pdf.setFont('DocumentFont', 'normal'); pdf.setTextColor(51, 65, 85);
          lines.forEach((line: string, lineIndex: number) => pdf.text(`${block.list && lineIndex === 0 ? '• ' : ''}${line}`, x + 10, y + 39 + lineIndex * (bodySize + 4)));
        });
        y += boxHeight + 14;
      } else {
        for (const block of section.planBlocks) {
          const wrapped = block.lines.map((line) => pdf.splitTextToSize(line, width - margin * 2 - 20) as string[]);
          const needed = 22 + wrapped.reduce((sum, lines) => sum + lines.length * (bodySize + 4) + 5, 0);
          ensureSpace(needed);
          pdf.setFont('DocumentFont', 'bold'); pdf.setFontSize(bodySize); pdf.setTextColor(15, 23, 42); pdf.text(block.label, margin, y); y += 18;
          pdf.setFont('DocumentFont', 'normal'); pdf.setTextColor(51, 65, 85);
          wrapped.forEach((lines) => { lines.forEach((line, index) => { pdf.text(`${block.list && index === 0 ? '• ' : ''}${line}`, margin + 10, y); y += bodySize + 4; }); y += 5; });
          y += 5;
        }
      }
      continue;
    }
    if (section.heading) { ensureSpace(54); if (!resourceKind && !profileDocument) { pdf.setFillColor(239, 246, 255); pdf.roundedRect(margin, y - 14, width - margin * 2, 28, 5, 5, 'F'); } pdf.setTextColor(resourceKind === 'plan' ? 15 : 30, resourceKind === 'plan' ? 23 : 64, resourceKind === 'plan' ? 42 : 175); pdf.setFont('DocumentFont', 'bold'); pdf.setFontSize(profileDocument === 'cv' ? 11 : resourceKind ? (branding.fontSize === 'large' ? 16 : 14) : 12); pdf.text(profileDocument === 'cv' ? section.heading.toUpperCase() : section.heading, margin + (resourceKind || profileDocument ? 0 : 10), y + 4); y += profileDocument === 'cv' ? 19 : resourceKind ? 25 : 28; if (profileDocument === 'cv') { pdf.setDrawColor(191, 219, 254); pdf.setLineWidth(0.5); pdf.line(margin, y - 8, width - margin, y - 8); } }
    for (const visual of section.visuals || []) {
      try {
        const dimensions = pdf.getImageProperties(visual);
        const drawWidth = Math.min(width - margin * 2, 431);
        const drawHeight = drawWidth * dimensions.height / dimensions.width;
        const scale = Math.min(1, (height - margin * 2 - 40) / drawHeight);
        ensureSpace(drawHeight * scale + 12);
        pdf.addImage(visual, dimensions.fileType, margin, y, drawWidth * scale, drawHeight * scale);
        y += drawHeight * scale + 12;
      } catch { /* Invalid stored artwork should not prevent the document download. */ }
    }
    if (section.grid?.length) {
      pdf.setFont('DocumentFont', 'normal'); pdf.setFontSize(bodySize); pdf.setTextColor(51, 65, 85);
      if (resourceKind === 'exam') { for (const line of section.lines) { const wrapped = pdf.splitTextToSize(line, width - margin * 2); ensureSpace(wrapped.length * (bodySize + 3) + 8); pdf.text(wrapped, margin, y); y += wrapped.length * (bodySize + 3) + 5; } y += 6; }
      if (resourceKind === 'exam' && section.watermark) {
        try {
          const dimensions = pdf.getImageProperties(section.watermark);
          const drawWidth = Math.min(width - margin * 2, 431);
          const drawHeight = drawWidth * dimensions.height / dimensions.width;
          const scale = Math.min(1, (height - margin * 2 - 40) / drawHeight);
          ensureSpace(drawHeight * scale + 12);
          pdf.addImage(section.watermark, dimensions.fileType, margin, y, drawWidth * scale, drawHeight * scale);
          y += drawHeight * scale + 12;
        } catch { /* Keep the puzzle if its stored illustration is invalid. */ }
      }
      const cell = Math.min(25, (width - margin * 2) / section.grid[0].length);
      const x = (width - cell * section.grid[0].length) / 2;
      ensureSpace(cell * section.grid.length + 15);
      if (section.watermark && resourceKind !== 'exam') {
        try {
          const dimensions = pdf.getImageProperties(section.watermark);
          const boxWidth = cell * section.grid[0].length;
          const boxHeight = cell * section.grid.length;
          const scale = Math.min(boxWidth / dimensions.width, boxHeight / dimensions.height);
          const imageWidth = dimensions.width * scale;
          const imageHeight = dimensions.height * scale;
          pdf.saveGraphicsState();
          pdf.setGState(pdf.GState({ opacity: 0.10 }));
          pdf.addImage(section.watermark, dimensions.fileType, x + (boxWidth - imageWidth) / 2, y - 12 + (boxHeight - imageHeight) / 2, imageWidth, imageHeight);
          pdf.restoreGraphicsState();
        } catch { /* A bad stored image should not prevent the puzzle export. */ }
      }
      pdf.setFont('DocumentFont', 'bold'); pdf.setFontSize(10); pdf.setTextColor(15, 23, 42); pdf.setDrawColor(148, 163, 184);
      const answerCells = new Set(section.answerCells?.map(([row, column]) => `${row}:${column}`));
      for (const [rowIndex, row] of section.grid.entries()) {
        ensureSpace(cell + 4);
        row.forEach((letter, column) => { const solved = answerCells.has(`${rowIndex}:${column}`); pdf.setDrawColor(solved ? 59 : 148, solved ? 130 : 163, solved ? 246 : 184); if (solved) { pdf.setFillColor(219, 234, 254); pdf.rect(x + column * cell, y - 12, cell, cell, 'FD'); } else pdf.rect(x + column * cell, y - 12, cell, cell); pdf.setTextColor(solved ? 37 : 15, solved ? 99 : 23, solved ? 235 : 42); pdf.text(letter, x + column * cell + cell / 2, y + 4, { align: 'center' }); });
        y += cell;
      }
      y += 10;
      continue;
    }
    pdf.setFont('DocumentFont', 'normal'); pdf.setFontSize(bodySize);
    for (const line of section.lines) {
      if (/^_{10,}$/.test(line.trim()) && resourceKind) { ensureSpace(22); pdf.setDrawColor(100, 116, 139); pdf.setLineWidth(0.6); pdf.line(margin, y + 3, width - margin - 30, y + 3); y += 22; continue; }
      const subheading = resourceKind === 'plan' && section.subheadings?.includes(line);
      const wrapped = pdf.splitTextToSize(line, width - margin * 2 - 20);
      const useBullet = bulletLines || section.bulleted;
      ensureSpace(wrapped.length * (bodySize + 3) + 12); if (useBullet) { pdf.setFillColor(37, 99, 235); pdf.circle(margin + 4, y - 3, 1.8, 'F'); } pdf.setFont('DocumentFont', subheading ? 'bold' : 'normal'); pdf.setTextColor(51, 65, 85); pdf.text(wrapped, profileDocument === 'cv' && !section.heading ? width / 2 : margin + (useBullet ? 14 : 0), y, { align: profileDocument === 'cv' && !section.heading ? 'center' : 'left' }); y += wrapped.length * (bodySize + 3) + (line.startsWith('____') ? 15 : subheading ? 2 : resourceKind ? 4 : 9);
    }
    if (section.table?.length) {
      const columns = section.table[0].length;
      const available = width - margin * 2;
      const widths = section.vocabularyTable ? Array(columns).fill(available / columns) : !resourceKind && columns === 3 ? [available * 0.20, available * 0.60, available * 0.20] : columns === 3 ? [available * 0.43, available * 0.14, available * 0.43] : columns === 2 ? [available * 0.78, available * 0.22] : Array(columns).fill(available / columns);
      const tableSize = resourceKind ? bodySize : 9;
      pdf.setFont('DocumentFont', 'normal'); pdf.setFontSize(tableSize);
      for (const [rowIndex, row] of section.table.entries()) {
        const wrapped = row.map((cell, index) => pdf.splitTextToSize(cell, widths[index] - 8));
        const rowHeight = Math.max(...wrapped.map((cell) => cell.length)) * (tableSize + 3) + 8;
        ensureSpace(rowHeight);
        if (!resourceKind || section.vocabularyTable) { pdf.setFillColor(section.vocabularyTable ? (rowIndex % 2 ? 248 : 255) : rowIndex === 0 ? 29 : rowIndex % 2 ? 255 : 241, section.vocabularyTable ? (rowIndex % 2 ? 250 : 255) : rowIndex === 0 ? 78 : rowIndex % 2 ? 255 : 245, section.vocabularyTable ? (rowIndex % 2 ? 252 : 255) : rowIndex === 0 ? 216 : rowIndex % 2 ? 255 : 249); pdf.rect(margin, y - bodySize, available, rowHeight, 'F'); pdf.setTextColor(!resourceKind && rowIndex === 0 ? 255 : 30, !resourceKind && rowIndex === 0 ? 255 : 41, !resourceKind && rowIndex === 0 ? 255 : 59); pdf.setFont('DocumentFont', !resourceKind && rowIndex === 0 ? 'bold' : 'normal'); }
        let x = margin;
        wrapped.forEach((cell, index) => { pdf.text(cell, x + 3, y + 1); if (!resourceKind) { pdf.setDrawColor(203, 213, 225); pdf.setLineWidth(0.4); pdf.rect(x, y - tableSize, widths[index], rowHeight); } x += widths[index]; });
        y += rowHeight;
      }
    }
    y += 10;
  }
  const pages = pdf.getNumberOfPages();
  for (let page = 1; page <= pages; page += 1) { pdf.setPage(page); pdf.setDrawColor(29, 78, 216); pdf.setLineWidth(1.2); pdf.line(margin, height - 49, width - margin, height - 49); pdf.setFont('DocumentFont', 'normal'); pdf.setFontSize(8); pdf.setTextColor(100, 116, 139); pdf.text(`${page} / ${pages}`, margin, height - 25); pdf.text(branding.footerEnabled && branding.brandName ? branding.brandName : COPY[locale].generated, width / 2, height - 25, { align: 'center' }); if (footerImage) { const dimensions = pdf.getImageProperties(footerImage.bytes); const drawWidth = Math.min(110, 30 * dimensions.width / dimensions.height); pdf.addImage(footerImage.bytes, footerImage.type, width - margin - drawWidth, height - 43, drawWidth, 30); } else if (logo && !headerImage) pdf.addImage(logo, 'PNG', width - margin - 50, height - 36, 50, 20); }
  pdf.save(`${slug(filename)}.pdf`);
}

async function saveDocx(title: string, subtitle: string, sections: ReportSection[], filename: string, locale: DocumentLocale, worksheet = false, bulletLines = true, resourceKind: 'plan' | 'worksheet' | 'exam' | null = null, metaLine = '') {
  if (!browserReady()) throw new Error('Word downloads are available in the web app.');
  const { AlignmentType, BorderStyle, Document, Footer, HeadingLevel, ImageRun, Packer, PageNumber, Paragraph, ShadingType, Table, TableCell, TableRow, TextRun, WidthType } = await import('docx');
  const branding = await loadBranding();
  const headerImage = branding.headerEnabled ? await loadBrandingImage(branding.headerLogoUrl) : null;
  const footerImage = branding.footerEnabled ? await loadBrandingImage(branding.footerImageUrl) : null;
  const logo = await loadClassioLogo();
  const watermarks = await Promise.all(sections.map((section) => section.grid?.length && section.watermark ? fadedWatermark(section.watermark) : Promise.resolve(null)));
  const baseSize = branding.fontSize === 'compact' ? 20 : branding.fontSize === 'large' ? 26 : 24;
  const children = [
    ...(branding.headerEnabled && headerImage ? [new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ data: headerImage.bytes, type: headerImage.type === 'PNG' ? 'png' : 'jpg', transformation: fittedImageSize(headerImage.bytes, 85, 85) })], spacing: { after: 80 } })] : !resourceKind && logo ? [new Paragraph({ children: [new ImageRun({ data: logo, type: 'png', transformation: { width: 78, height: 31.2 } })], spacing: { after: 80 } })] : []),
    ...(branding.headerEnabled && branding.brandName ? [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: branding.brandName, font: branding.font, size: baseSize + 2, bold: true, color: '1D4ED8' })], spacing: { after: 60 } })] : []),
    ...(branding.headerEnabled && branding.department ? [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: branding.department, font: branding.font, size: baseSize, color: '475569' })], spacing: { after: 60 } })] : []),
    new Paragraph({ text: title, heading: HeadingLevel.TITLE, alignment: resourceKind === 'plan' || resourceKind === 'worksheet' ? AlignmentType.CENTER : AlignmentType.LEFT, spacing: { after: 120 } }),
    ...(metaLine ? [new Paragraph({ children: metaLine.split(/\s+\|\s+/).flatMap((part, index) => { const colon = part.indexOf(':'); return [
      ...(index ? [new TextRun({ text: '  |  ', size: baseSize - 2, font: branding.font, color: '334155' })] : []),
      ...(colon >= 0 ? [new TextRun({ text: `${part.slice(0, colon + 1)} `, size: baseSize - 2, font: branding.font, bold: true, color: '334155' })] : []),
      new TextRun({ text: colon >= 0 ? part.slice(colon + 1).trim() : part, size: baseSize - 2, font: branding.font, color: '334155' }),
    ]; }), spacing: { after: 90 } })] : []),
    ...(worksheet && branding.headerEnabled && branding.headerStyle === 'school' ? [new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, rows: [new TableRow({ children: schoolFields(locale).map((field) => new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: field, font: branding.font, size: baseSize, bold: true })] })] })) })] })] : []),
    ...(!resourceKind ? [new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, rows: [new TableRow({ children: [new TableCell({ shading: { fill: 'F8FAFC', type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 140, right: 140 }, children: [new Paragraph({ children: [new TextRun({ text: subtitle, color: '475569', bold: true }), new TextRun({ text: `  ·  ${new Date().toLocaleDateString()}`, color: '64748B' })] })] })] })] })] : []),
    ...sections.flatMap((section, sectionIndex) => section.planBlocks ? [
      new Paragraph({ text: section.heading, heading: HeadingLevel.HEADING_1, pageBreakBefore: section.pageBreak, spacing: { before: 160, after: 100 } }),
      ...(section.planOverview ? [new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, borders: { top: { color: '3B82F6', size: 10, style: BorderStyle.SINGLE }, bottom: { color: '3B82F6', size: 10, style: BorderStyle.SINGLE }, left: { color: '3B82F6', size: 10, style: BorderStyle.SINGLE }, right: { color: '3B82F6', size: 10, style: BorderStyle.SINGLE }, insideVertical: { color: 'CBD5E1', size: 5, style: BorderStyle.SINGLE } }, rows: [new TableRow({ children: section.planBlocks.slice(0, 2).map((block) => new TableCell({ width: { size: 50, type: WidthType.PERCENTAGE }, margins: { top: 150, bottom: 150, left: 150, right: 150 }, children: [new Paragraph({ children: [new TextRun({ text: block.label, bold: true, color: '0F172A', font: branding.font, size: baseSize })], spacing: { after: 70 } }), ...block.lines.map((line) => new Paragraph({ children: [new TextRun({ text: line, font: branding.font, size: baseSize })], bullet: block.list ? { level: 0 } : undefined }))] })) })] })] : section.planBlocks.flatMap((block) => [
        new Paragraph({ children: [new TextRun({ text: block.label, bold: true, color: '0F172A', font: branding.font, size: baseSize })], spacing: { before: 100, after: 60 }, keepNext: true }),
        ...block.lines.map((line) => new Paragraph({ children: [new TextRun({ text: line, font: branding.font, size: baseSize, color: '334155' })], bullet: block.list ? { level: 0 } : undefined, spacing: { after: 70 } })),
      ])),
    ] : [
      ...(section.heading ? [new Paragraph({ text: section.heading, heading: HeadingLevel.HEADING_1, spacing: { before: section.pdfPageBreak ? 300 : resourceKind ? 160 : 280, after: 100 }, ...(section.pdfPageBreak ? { border: { top: { color: '1D4ED8', size: 8, style: BorderStyle.SINGLE } } } : resourceKind ? {} : { shading: { fill: 'EFF6FF', type: ShadingType.CLEAR }, border: { bottom: { color: 'BFDBFE', size: 5, style: BorderStyle.SINGLE } } }) })] : []),
      ...(section.visuals || []).flatMap((visual) => {
        try {
          const bytes = visualBytes(visual);
          const dimensions = visualDimensions(bytes);
          if (!dimensions?.width || !dimensions.height) return [];
          const drawWidth = 430;
          const drawHeight = drawWidth * dimensions.height / dimensions.width;
          const scale = Math.min(1, 680 / drawHeight);
          return [new Paragraph({ children: [new ImageRun({ data: bytes, type: visual.startsWith('data:image/png') ? 'png' : 'jpg', transformation: { width: drawWidth * scale, height: drawHeight * scale } })], spacing: { after: 90 } })];
        } catch { return []; }
      }),
      ...(section.grid?.length ? [
        ...(resourceKind === 'exam' ? section.lines.map((line) => new Paragraph({ children: [new TextRun({ text: line, font: branding.font, size: baseSize, color: '334155' })], spacing: { after: 90 } })) : []),
        ...(watermarks[sectionIndex] ? [new Paragraph({ spacing: { before: 0, after: 0, line: 1 }, children: [new ImageRun({ data: visualBytes(watermarks[sectionIndex]!), type: 'png', transformation: { width: 430, height: section.grid.length * 27 }, floating: { horizontalPosition: { relative: 'column', align: 'center' }, verticalPosition: { relative: 'paragraph', offset: 108000 }, behindDocument: true, allowOverlap: true } })] })] : []),
        new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, rows: section.grid.map((row, rowIndex) => new TableRow({ children: row.map((letter, columnIndex) => { const solved = section.answerCells?.some(([r, c]) => r === rowIndex && c === columnIndex); return new TableCell({ ...(solved ? { shading: { fill: 'DBEAFE', type: ShadingType.CLEAR }, borders: { top: { color: '3B82F6', style: BorderStyle.SINGLE }, bottom: { color: '3B82F6', style: BorderStyle.SINGLE }, left: { color: '3B82F6', style: BorderStyle.SINGLE }, right: { color: '3B82F6', style: BorderStyle.SINGLE } } } : {}), children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: letter, font: branding.font, size: baseSize, bold: true, color: solved ? '2563EB' : '0F172A' })] })] }); }) })) })
      ] : [
        ...section.lines.map((line) => new Paragraph({ children: [new TextRun({ text: line, size: baseSize, font: branding.font, color: '334155', bold: resourceKind === 'plan' && section.subheadings?.includes(line) })], bullet: bulletLines || section.bulleted ? { level: 0 } : undefined, spacing: { after: line.startsWith('____') ? 180 : resourceKind ? 60 : 90, line: resourceKind ? 276 : 300 } })),
        ...(section.table?.length ? [new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, columnWidths: section.vocabularyTable ? Array(section.table[0].length).fill(Math.floor(9240 / section.table[0].length)) : !resourceKind && section.table[0].length === 3 ? [1800, 5500, 1800] : section.table[0].length === 3 ? [3973, 1294, 3973] : section.table[0].length === 2 ? [7200, 2040] : Array(section.table[0].length).fill(Math.floor(9240 / section.table[0].length)), borders: { top: { style: resourceKind ? BorderStyle.NONE : BorderStyle.SINGLE, color: 'CBD5E1' }, bottom: { style: resourceKind ? BorderStyle.NONE : BorderStyle.SINGLE, color: 'CBD5E1' }, left: { style: resourceKind ? BorderStyle.NONE : BorderStyle.SINGLE, color: 'CBD5E1' }, right: { style: resourceKind ? BorderStyle.NONE : BorderStyle.SINGLE, color: 'CBD5E1' }, insideHorizontal: { style: resourceKind ? BorderStyle.NONE : BorderStyle.SINGLE, color: 'CBD5E1' }, insideVertical: { style: resourceKind ? BorderStyle.NONE : BorderStyle.SINGLE, color: 'CBD5E1' } }, rows: section.table.map((row, rowIndex) => new TableRow({ children: row.map((cell, index) => new TableCell({ ...(!resourceKind || section.vocabularyTable ? { shading: { fill: !resourceKind && rowIndex === 0 ? '1D4ED8' : rowIndex % 2 ? 'FFFFFF' : 'F1F5F9', type: ShadingType.CLEAR } } : {}), width: { size: section.vocabularyTable ? Math.floor(9240 / section.table![0].length) : !resourceKind && section.table?.[0].length === 3 ? [1800, 5500, 1800][index] : section.table?.[0].length === 3 ? [3973, 1294, 3973][index] : section.table?.[0].length === 2 ? [7200, 2040][index] : Math.floor(9240 / section.table![0].length), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: cell, font: branding.font, size: resourceKind ? baseSize : 18, bold: (!resourceKind && rowIndex === 0) || section.vocabularyTable, color: !resourceKind && rowIndex === 0 ? 'FFFFFF' : '334155' })] })] })) })) })] : []),
      ]),
    ]),
  ];
  const footer = new Footer({ children: [new Paragraph({ alignment: AlignmentType.LEFT, border: { top: { color: '1D4ED8', size: 10, style: BorderStyle.SINGLE } }, children: [new TextRun({ children: [PageNumber.CURRENT], color: '64748B', size: 16, font: branding.font }), new TextRun({ text: `   ·   ${branding.footerEnabled && branding.brandName ? branding.brandName : COPY[locale].generated}   `, color: '64748B', size: 16, font: branding.font }), ...(footerImage ? [new ImageRun({ data: footerImage.bytes, transformation: fittedImageSize(footerImage.bytes, 95, 30), type: footerImage.type === 'PNG' ? 'png' : 'jpg' })] : logo && !headerImage ? [new ImageRun({ data: logo, transformation: { width: 50, height: 20 }, type: 'png' })] : [])] })] });
  const blob = await Packer.toBlob(new Document({ styles: { default: { document: { run: { font: branding.font, size: baseSize, color: '0F172A' }, paragraph: { spacing: { line: resourceKind ? 276 : 300 } } }, title: { run: { font: branding.font, size: resourceKind ? (branding.fontSize === 'large' ? 36 : 28) : 42, bold: true, color: resourceKind ? '1D4ED8' : '0F172A' } }, heading1: { run: { font: branding.font, size: resourceKind ? (branding.fontSize === 'large' ? 32 : 28) : 26, bold: true, color: '0F172A' } } } }, sections: [{ footers: { default: footer }, properties: { page: { margin: { top: 850, right: resourceKind === 'plan' ? 1134 : 1020, bottom: 850, left: resourceKind === 'plan' ? 1134 : 1020 } } }, children }] }));
  saveBlob(blob, `${slug(filename)}.docx`);
}

export function downloadResourcePdf(title: string, detail: Record<string, unknown>, locale: DocumentLocale = 'en', variant: ResourceVariant = 'full') {
  const suffix = variant === 'full' ? '' : `-${variant}`;
  const subtitle = variant === 'student' ? COPY[locale].studentCopy : variant === 'teacher' ? COPY[locale].teacherCopy : variant === 'answers' ? COPY[locale].answerKey : COPY[locale].teachingResource;
  const resourceKind = detail.plan_json || detail.objective && detail.core_material ? 'plan' : detail.worksheet_json || detail.worksheet_type ? 'worksheet' : detail.exam_data || detail.sections ? 'exam' : null;
  const worksheetLanguage = record(detail.worksheet_json).plan_language ?? detail.plan_language;
  const documentLocale: DocumentLocale = resourceKind === 'worksheet' && ['en', 'es', 'tr'].includes(String(worksheetLanguage)) ? String(worksheetLanguage) as DocumentLocale : locale;
  const profileDocument = detail.full_name ? 'cv' : typeof detail.cover_letter === 'string' ? 'letter' : null;
  const displayTitle = profileDocument === 'cv' ? String(detail.full_name) : resourceKind === 'exam' && variant !== 'student' && variant !== 'full' ? `${title} - ${COPY[documentLocale].answerKey}` : title;
  const documentKind: DocumentKind = resourceKind === 'plan' ? 'lesson_plan' : resourceKind || (profileDocument === 'letter' ? 'cover_letter' : profileDocument) || 'other';
  return recordedDocumentExport('pdf', documentKind, variant, () => savePdf(displayTitle, subtitle, resourceSections(detail, variant, documentLocale), `${title}${suffix}`, documentLocale, resourceKind === 'worksheet' || resourceKind === 'exam', false, resourceKind, resourceMetaLine(detail, resourceKind, documentLocale), profileDocument, String(detail.avatar_url || '')));
}

export function downloadResourceDocx(title: string, detail: Record<string, unknown>, locale: DocumentLocale = 'en', variant: ResourceVariant = 'full') {
  const suffix = variant === 'full' ? '' : `-${variant}`;
  const subtitle = variant === 'student' ? COPY[locale].studentCopy : variant === 'teacher' ? COPY[locale].teacherCopy : variant === 'answers' ? COPY[locale].answerKey : COPY[locale].teachingResource;
  const resourceKind = detail.plan_json || detail.objective && detail.core_material ? 'plan' : detail.worksheet_json || detail.worksheet_type ? 'worksheet' : detail.exam_data || detail.sections ? 'exam' : null;
  const worksheetLanguage = record(detail.worksheet_json).plan_language ?? detail.plan_language;
  const documentLocale: DocumentLocale = resourceKind === 'worksheet' && ['en', 'es', 'tr'].includes(String(worksheetLanguage)) ? String(worksheetLanguage) as DocumentLocale : locale;
  const displayTitle = resourceKind === 'exam' && variant !== 'student' && variant !== 'full' ? `${title} - ${COPY[documentLocale].answerKey}` : title;
  const documentKind: DocumentKind = resourceKind === 'plan' ? 'lesson_plan' : resourceKind || 'other';
  return recordedDocumentExport('docx', documentKind, variant, () => saveDocx(displayTitle, subtitle, resourceSections(detail, variant, documentLocale), `${title}${suffix}`, documentLocale, resourceKind === 'worksheet' || resourceKind === 'exam', false, resourceKind, resourceKind === 'plan' ? resourceMetaLine(detail, resourceKind, documentLocale) : ''));
}

export function downloadStudentReportPdf(studentName: string, workspace: StudentLearningWorkspace, locale: DocumentLocale = 'en') {
  return recordedDocumentExport('pdf', 'student_report', 'full', () => savePdf(`${studentName} · ${COPY[locale].progress}`, COPY[locale].studentEvidence, studentSections(workspace, locale), `${studentName}-progress-report`, locale));
}

export function downloadStudentReportDocx(studentName: string, workspace: StudentLearningWorkspace, locale: DocumentLocale = 'en') {
  return recordedDocumentExport('docx', 'student_report', 'full', () => saveDocx(`${studentName} · ${COPY[locale].progress}`, COPY[locale].studentEvidence, studentSections(workspace, locale), `${studentName}-progress-report`, locale));
}

type HistoryBalance = { subject: string; modality: string; purchased: number; delivered: number; remaining: number; startDate?: string; expiryDate?: string } | null;
function studentHistorySections(lessons: Record<string, unknown>[], payments: Record<string, unknown>[], locale: DocumentLocale, balance: HistoryBalance): ReportSection[] {
  const labels = {
    en: { lessons: 'Lessons', payments: 'Payments & packages', balance: 'Current package balance', date: 'Date', details: 'Details', amount: 'Amount', units: 'Units', paid: 'Paid', taken: 'Delivered', left: 'Remaining', start: 'Starts', expiry: 'Expires', subject: 'Subject', modality: 'Modality', note: 'Note' },
    es: { lessons: 'Clases', payments: 'Pagos y paquetes', balance: 'Saldo del paquete actual', date: 'Fecha', details: 'Detalles', amount: 'Importe', units: 'Unidades', paid: 'Pagadas', taken: 'Impartidas', left: 'Restantes', start: 'Inicio', expiry: 'Vencimiento', subject: 'Asignatura', modality: 'Modalidad', note: 'Nota' },
    tr: { lessons: 'Dersler', payments: 'Ödemeler ve paketler', balance: 'Güncel paket bakiyesi', date: 'Tarih', details: 'Ayrıntılar', amount: 'Tutar', units: 'Birim', paid: 'Ödenen', taken: 'Verilen', left: 'Kalan', start: 'Başlangıç', expiry: 'Bitiş', subject: 'Ders', modality: 'Ders biçimi', note: 'Not' },
  }[locale];
  const sections: ReportSection[] = [
    { heading: labels.lessons, lines: lessons.length ? [] : [COPY[locale].noData], table: lessons.length ? [[labels.date, labels.units, labels.modality, labels.subject, labels.note], ...lessons.map((row) => [String(row.lesson_date || '').slice(0, 10), String(row.number_of_lesson || 0), String(row.modality || ''), String(row.subject_custom || row.subject || COPY[locale].general), String(row.note || '')])] : undefined },
    { heading: labels.payments, lines: payments.length ? [] : [COPY[locale].noData], table: payments.length ? [[labels.date, labels.paid, labels.amount, labels.modality, labels.subject, labels.start, labels.expiry], ...payments.map((row) => [String(row.payment_date || '').slice(0, 10), String(row.number_of_lesson || 0), `${String(row.currency || '')} ${Number(row.paid_amount || 0).toLocaleString()}`, String(row.modality || ''), String(row.subject_custom || row.subject || COPY[locale].general), String(row.package_start_date || '').slice(0, 10), String(row.package_expiry_date || '').slice(0, 10)])] : undefined },
  ];
  const totals = new Map<string, number>();
  for (const payment of payments) { const currency = String(payment.currency || 'TRY'); totals.set(currency, (totals.get(currency) || 0) + Number(payment.paid_amount || 0)); }
  sections.push({ heading: locale === 'es' ? 'Totales' : locale === 'tr' ? 'Toplamlar' : 'Totals', lines: [`${labels.lessons}: ${lessons.reduce((sum, lesson) => sum + Number(lesson.number_of_lesson || 0), 0)} ${labels.units}`, ...[...totals].map(([currency, amount]) => `${currency} ${amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}`)] });
  if (balance) sections.push({ heading: labels.balance, lines: [[balance.subject, balance.modality, balance.startDate ? `${labels.start}: ${balance.startDate}` : '', balance.expiryDate ? `${labels.expiry}: ${balance.expiryDate}` : ''].filter(Boolean).join(' · ')], table: [[labels.paid, labels.taken, labels.left], [String(balance.purchased), String(balance.delivered), String(balance.remaining)]] });
  return sections;
}

export function downloadStudentHistoryPdf(studentName: string, lessons: Record<string, unknown>[], payments: Record<string, unknown>[], locale: DocumentLocale = 'en', balance: HistoryBalance = null) {
  return recordedDocumentExport('pdf', 'student_history', 'full', () => savePdf(`${{ en: 'Student report', es: 'Informe del estudiante', tr: 'Öğrenci raporu' }[locale]} · ${studentName}`, new Date().toISOString().slice(0, 10), studentHistorySections(lessons, payments, locale, balance), `${studentName}-student-report`, locale));
}

export function downloadStudentHistoryDocx(studentName: string, lessons: Record<string, unknown>[], payments: Record<string, unknown>[], locale: DocumentLocale = 'en', balance: HistoryBalance = null) {
  return recordedDocumentExport('docx', 'student_history', 'full', () => saveDocx(`${{ en: 'Student report', es: 'Informe del estudiante', tr: 'Öğrenci raporu' }[locale]} · ${studentName}`, new Date().toISOString().slice(0, 10), studentHistorySections(lessons, payments, locale, balance), `${studentName}-student-report`, locale));
}
