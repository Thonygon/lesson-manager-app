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
examples.push(['exam-visual', 'Visual exam', { sections: [{ type: 'diagram_questions', title: 'Diagram', visual_support: visual, questions: ['Identify the image.'] }] }, 'student']);
examples.push(['word-search-watermark', 'Visual word search', { worksheet_type: 'word_search_vocab', instructions: 'Find CLASS.', vocabulary_bank: ['CLASS'], visual_supports: [visual] }, 'student']);
examples.push(['exam-word-search', 'Exam word search', { sections: [{ type: 'word_search', title: 'Find the words', instructions: 'Circle the words.', vocabulary_bank: ['CLASS', 'LEARN'], visual_support: visual }] }, 'student']);
(async () => {
  for (const [name, title, detail, variant] of examples) {
    global.__classioPdfBytes = null;
    await loaded.exports.downloadResourcePdf(title, detail, 'en', variant);
    if (!global.__classioPdfBytes) throw new Error(`${name} did not produce a PDF`);
    fs.writeFileSync(path.join(outputDir, `${name}.pdf`), Buffer.from(global.__classioPdfBytes));
  }
  process.stdout.write(`${outputDir}\n`);
})().catch((error) => { console.error(error); process.exitCode = 1; });
