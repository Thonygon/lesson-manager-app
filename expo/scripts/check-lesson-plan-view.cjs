const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/document-exports.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', 'require', compiled)(loaded, loaded.exports, (name) => {
  if (name === 'react-native') return { Platform: { OS: 'web' } };
  if (name === '@/services/branding') return { getBrandingSettings: () => ({}) };
  if (name === '@/lib/subjects') return { canonicalSubjectKey: (value) => value };
  if (name === '@/lib/learner-stages') return { canonicalLearnerStageKey: (value) => value };
  if (name === '@/lib/lesson-purpose') return { lessonPurposeKey: (value) => value };
  if (name === './source-document-labels.json') return require('../src/services/source-document-labels.json');
  if (name === './word-search-grid') return {};
  throw new Error(`Unexpected dependency: ${name}`);
});

const sections = loaded.exports.resourceSections({ plan_json: {
  objective: 'Greet a visitor politely.', success_criteria: ['Use a greeting and respond.'],
  warm_up: ['Recall a familiar greeting.'], main_activity: ['Role-play a greeting.'],
  teacher_moves: ['Model a short exchange.'], core_material: { target_vocabulary: ['hello', 'thank you'] },
} }, 'full', 'es');
assert.ok(sections.every((section) => section.planBlocks?.length), 'The export formatter must provide visible plan blocks.');
assert.ok(sections[0].planBlocks.some((block) => block.lines.includes('Greet a visitor politely.')));
assert.ok(sections.some((section) => section.planBlocks.some((block) => block.lines.includes('Role-play a greeting.'))));
const view = fs.readFileSync(path.join(__dirname, '../src/components/lesson-plan-view.tsx'), 'utf8');
const viewJs = ts.transpileModule(view, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const loadedView = { exports: {} };
new Function('module', 'exports', 'require', viewJs)(loadedView, loadedView.exports, (name) => {
  if (name === 'react/jsx-runtime') return require(name);
  if (name === 'react-native') return {
    StyleSheet: { create: (styles) => styles },
    Text: ({ children }) => React.createElement('span', null, children),
    View: ({ children }) => React.createElement('div', null, children),
  };
  if (name === 'expo-image') return { Image: () => null };
  if (name === '@/components/ui') return { Disclosure: ({ title, children }) => React.createElement('section', null, title, children) };
  if (name === '@/services/document-exports') return loaded.exports;
  if (name === '@/theme') return { colors: { primary: '#2563eb', ink: '#0f172a', inkSecondary: '#334155' } };
  throw new Error(`Unexpected view dependency: ${name}`);
});
const html = renderToStaticMarkup(React.createElement(loadedView.exports.LessonPlanView, { detail: { plan_json: {
  objective: 'Greet a visitor politely.', success_criteria: ['Use a greeting and respond.'],
  warm_up: ['Recall a familiar greeting.'], main_activity: ['Role-play a greeting.'],
  teacher_moves: ['Model a short exchange.'], core_material: { target_vocabulary: ['hello', 'thank you'] },
} }, locale: 'es' }));
for (const content of ['Greet a visitor politely.', 'Role-play a greeting.', 'Model a short exchange.', 'hello, thank you']) assert.ok(html.includes(content), `The plan view omitted ${content}`);
process.stdout.write('Lesson plan content fixture passed.\n');
