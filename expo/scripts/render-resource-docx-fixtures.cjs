const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const servicePath = path.join(__dirname, '../src/services');
const source = fs.readFileSync(path.join(servicePath, 'document-exports.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, resolveJsonModule: true } }).outputText;
const loaded = { exports: {} };
const moduleRequire = (name) => {
  if (name === 'react-native') return { Platform: { OS: 'web' } };
  if (name === '@/lib/supabase') return { requireSupabase() { throw new Error('Use default branding'); } };
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

const outputDir = process.argv[2] || '/tmp/classio-document-fixtures';
fs.mkdirSync(outputDir, { recursive: true });
global.document = { createElement: () => ({ click() {}, remove() {} }), body: { appendChild() {} } };
global.window = { setTimeout() {} };
global.fetch = async () => ({ ok: false });
let captured;
global.URL.createObjectURL = (blob) => { captured = blob; return 'blob:fixture'; };
global.URL.revokeObjectURL = () => {};

const samples = [
  ['plan', 'Lesson plan', { title: 'Greetings', subject: 'Spanish', topic: 'Greetings', learner_stage: 'adult_stage', level_or_band: 'A2', lesson_purpose: 'introduce_concept', objective: 'Greet a peer.', success_criteria: ['Use three greetings.', 'Respond politely.'], warm_up: ['Recall a phrase.'], main_activity: ['Role play.'], guided_practice: ['Model a dialogue.'], practice_questions: ['What would you say?'], core_material: { target_vocabulary: ['hola', 'adiós', 'gracias'] } }, 'full'],
  ['worksheet', 'Reading worksheet', { title: 'Reading worksheet', worksheet_type: 'reading_comprehension', instructions: 'Read and answer.', text_kind: 'dialogue', reading_passage: 'Ana: Hello.\nBen: Welcome.', text_blocks: [{ type: 'turn', speaker: 'Ana', text: 'Hello.' }, { type: 'turn', speaker: 'Ben', text: 'Welcome.' }], questions: ['Who speaks first?', 'How does Ben respond?'], answer_key: '1. Ana\n2. He welcomes Ana.' }, 'student'],
  ['exam', 'Science exam', { title: 'Science exam', instructions: 'Answer each question.', sections: [{ type: 'true_false', title: 'Part 1: True or False', instructions: 'Mark T or F.', questions: ['Water is a liquid.', 'Ice is frozen water.', 'Steam is a gas.', 'The Sun is cold.', 'Plants need light.'], answers: ['True', 'True', 'True', 'False', 'True'] }] }, 'student'],
  ['exam-writing', 'Writing exam', { title: 'Writing exam', duration_minutes: 45, sections: [{ type: 'short_answer', title: 'Short answer', questions: ['Explain the result.'], answers: ['Reasoned response'] }, { type: 'writing_prompt', title: 'Writing', questions: ['Write a paragraph about the result.'], answers: ['Coherent paragraph'] }] }, 'student'],
  ['exam-matching', 'Matching exam', { title: 'Matching exam', sections: [{ type: 'matching', title: 'Match the terms', questions: [{ left: { key: 'Cat' }, right: { value: 'Animal' } }, { left: { key: 'Dog' }, right: { value: 'Pet' } }] }] }, 'student'],
  ['worksheet-matching', 'Matching worksheet', { title: 'Matching worksheet', worksheet_type: 'matching', instructions: 'Match the terms.', matching_pairs: [{ left: { Cat: 'Gato' }, right: { value: 'Animal' } }, { left: { Dog: 'Perro' }, right: { value: 'Pet' } }] }, 'student'],
  ['word-search', 'Word search', { title: 'Word search', worksheet_type: 'word_search_vocab', instructions: 'Find the words.', vocabulary_bank: ['CLASS', 'LEARN', 'SCHOOL'] }, 'student'],
];
const visual = { status: 'ready', image_data_url: `data:image/png;base64,${fs.readFileSync(path.join(__dirname, '../public/logo_classio_light.png')).toString('base64')}` };
samples.push(['worksheet-visual', 'Visual worksheet', { worksheet_type: 'reading_comprehension', instructions: 'Study the picture.', visual_supports: [visual], questions: ['What do you see?'] }, 'student']);
samples.push(['exam-visual', 'Visual exam', { sections: [{ type: 'diagram_questions', title: 'Diagram', visual_support: visual, questions: ['Identify the image.'] }] }, 'student']);

(async () => {
  for (const [name, title, detail, variant] of samples) {
    captured = null;
    await loaded.exports.downloadResourceDocx(title, detail, 'en', variant);
    if (!captured) throw new Error(`${name} did not produce a document`);
    fs.writeFileSync(path.join(outputDir, `${name}.docx`), Buffer.from(await captured.arrayBuffer()));
  }
  process.stdout.write(`${outputDir}\n`);
})().catch((error) => { console.error(error); process.exitCode = 1; });
