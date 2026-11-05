const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const servicePath = path.join(__dirname, '../src/services');
const source = fs.readFileSync(path.join(servicePath, 'document-exports.ts'), 'utf8');
const patched = source.replace('pdf.save(`${slug(filename)}.pdf`);', 'globalThis.__classioPdfBytes = pdf.output("arraybuffer");');
if (patched === source) throw new Error('PDF save hook was not found.');
const compiled = ts.transpileModule(patched, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, resolveJsonModule: true } }).outputText;
const loaded = { exports: {} };
const moduleRequire = (name) => {
  if (name === 'react-native') return { Platform: { OS: 'web' } };
  if (name === '@/lib/supabase') return { requireSupabase() { throw new Error('Use default branding'); } };
  if (name === '@/services/branding') return { getBrandingSettings() { throw new Error('Use default branding'); } };
  if (name === '@/services/document-export-events') return { recordedDocumentExport: async (_format, _kind, _variant, prepare) => prepare() };
  if (name === '@/lib/subjects') return { canonicalSubjectKey: (value) => String(value || '').toLowerCase() };
  if (name === '@/lib/learner-stages') return { canonicalLearnerStageKey: (value) => String(value || '').toLowerCase() };
  if (name === '@/lib/lesson-purpose') return { lessonPurposeKey: (value) => String(value || '').toLowerCase() };
  if (name.startsWith('./')) {
    const filename = path.join(servicePath, name);
    if (name.endsWith('.json')) return require(filename);
    const local = fs.readFileSync(`${filename}.ts`, 'utf8');
    const code = ts.transpileModule(local, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
    const nested = { exports: {} };
    new Function('module', 'exports', code)(nested, nested.exports);
    return nested.exports;
  }
  return require(name);
};
new Function('module', 'exports', 'require', compiled)(loaded, loaded.exports, moduleRequire);
global.document = {};
global.fetch = async (url) => {
  const name = String(url).split('/').pop();
  if (name === 'DejaVuSans.ttf' || name === 'DejaVuSans-Bold.ttf') {
    const bytes = fs.readFileSync(path.join(__dirname, '../public/fonts', name));
    return { ok: true, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) };
  }
  if (name === 'logo_classio_light.png') {
    const bytes = fs.readFileSync(path.join(__dirname, '../public', name));
    return { ok: true, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) };
  }
  return { ok: false };
};
const outputDir = process.argv[2] || '/tmp/classio-resource-pdf-fixtures';
fs.mkdirSync(outputDir, { recursive: true });
const examples = [
  ['exam-matching', 'Matching exam', { title: 'Matching exam', sections: [{ type: 'matching', title: 'Match the terms', questions: [{ left: { key: 'Cat' }, right: { value: 'Animal' } }, { left: { key: 'Dog' }, right: { value: 'Pet' } }] }] }, 'student'],
  ['worksheet-matching', 'Matching worksheet', { title: 'Matching worksheet', worksheet_type: 'matching', instructions: 'Match the terms.', matching_pairs: [{ left: { Cat: 'Gato' }, right: { value: 'Animal' } }, { left: { Dog: 'Perro' }, right: { value: 'Pet' } }] }, 'student'],
];
const visual = { status: 'ready', image_data_url: `data:image/png;base64,${fs.readFileSync(path.join(__dirname, '../public/logo_classio_light.png')).toString('base64')}` };
examples.push(['worksheet-visual', 'Visual worksheet', { worksheet_type: 'reading_comprehension', instructions: 'Study the picture.', visual_supports: [visual], questions: ['What do you see?'] }, 'student']);
examples.push(['exam-visual', 'Visual exam', { sections: [{ type: 'diagram_questions', title: 'Diagram', instructions: 'Study the image before answering.', source_text: 'The classroom diagram.', visual_support: visual, questions: ['Identify the image.'] }] }, 'student']);
examples.push(['word-search-watermark', 'Visual word search', { worksheet_type: 'word_search_vocab', instructions: 'Find CLASS.', vocabulary_bank: ['CLASS'], visual_supports: [visual] }, 'student']);
examples.push(['exam-word-search', 'Exam word search', { sections: [{ type: 'word_search', title: 'Find the words', instructions: 'Circle the words.', vocabulary_bank: ['CLASS', 'LEARN'], visual_support: visual }] }, 'student']);
examples.push(['long-topic-exam', 'El pretérito imperfecto', { exam_data: { sections: [{ type: 'short_answer', title: 'Parte 1', questions: ['Explica el uso del tiempo verbal.'] }] }, subject: 'Spanish', topic: 'Cuando era niño/a: El Pretérito Imperfecto regular e irregular para describir rutinas y hábitos del pasado', learner_stage: 'adult_stage', level_or_band: 'A2' }, 'student']);
examples.push(['email-reading', 'Reading an email', { worksheet_json: { worksheet_type: 'reading_comprehension', reading_passage: 'From: Ana\nTo: Ben\nSubject: Our trip\n\nHello Ben,\n\nWe will travel next week. We will visit the museum and explore the city together. Please bring your notebook and camera.\n\nBest wishes,\nAna', text_kind: 'email', questions: ['When will they travel?'] } }, 'student']);
(async () => {
  for (const [name, title, detail, variant] of examples) {
    global.__classioPdfBytes = null;
    await loaded.exports.downloadResourcePdf(title, detail, 'en', variant);
    if (!global.__classioPdfBytes) throw new Error(`${name} did not produce a PDF`);
    fs.writeFileSync(path.join(outputDir, `${name}.pdf`), Buffer.from(global.__classioPdfBytes));
  }
  global.__classioPdfBytes = null;
  await loaded.exports.downloadStudentHistoryPdf('Sample Student', [{ lesson_date: '2026-11-04', number_of_lesson: 1, modality: 'Online', subject: 'English', note: 'Future plans' }], [], 'en');
  fs.writeFileSync(path.join(outputDir, 'student-history.pdf'), Buffer.from(global.__classioPdfBytes));
  global.__classioPdfBytes = null;
  await loaded.exports.downloadStudentReportPdf('Sample Student', { assignments: [], attempts: [], programs: [], reviews: [], progress: [] }, 'en');
  fs.writeFileSync(path.join(outputDir, 'student-progress.pdf'), Buffer.from(global.__classioPdfBytes));
  global.__classioPdfBytes = null;
  await loaded.exports.downloadStudentHistoryPdf('Sample Student', Array.from({ length: 60 }, (_, index) => ({ lesson_date: `2026-10-${String(index % 28 + 1).padStart(2, '0')}`, number_of_lesson: 1, modality: 'Online', subject: 'English', note: `Lesson ${index + 1}: Future plans and speaking practice` })), [], 'en');
  fs.writeFileSync(path.join(outputDir, 'student-history-long.pdf'), Buffer.from(global.__classioPdfBytes));
  process.stdout.write(`${outputDir}\n`);
})().catch((error) => { console.error(error); process.exitCode = 1; });
