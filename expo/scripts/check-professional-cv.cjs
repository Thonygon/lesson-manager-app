const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/professional-cv.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const loaded = { exports: {} };
new Function('module', 'exports', 'require', compiled)(loaded, loaded.exports, (name) => {
  if (name === '@/lib/supabase') return { requireSupabase() { throw new Error('Save is not used in this fixture.'); } };
  if (name === './cv-countries.json') return require('../src/services/cv-countries.json');
  return require(name);
});

const input = {
  fullName: 'Ada Teacher', email: 'ada@example.test', phone: '', location: 'Spain', role: 'teacher',
  subjects: 'Spanish, English', teachingStages: 'Adult, Upper secondary', teachingLanguages: 'Spanish, English',
  summary: '', education: 'BA Education\nMA Linguistics', certifications: 'TESOL, DELE',
  experience: 'Tutor 2020–2024\nTeacher 2024–present', skills: 'Curriculum, Assessment', availability: 'Weekdays', rate: '€30',
};
const cv = loaded.exports.buildTemplateCv(input, 'en');
assert.equal(cv.title, 'CV – Ada Teacher');
assert.equal(cv.source_type, 'template');
assert.deepEqual(cv.subjects, ['Spanish', 'English']);
assert.deepEqual(cv.education, ['BA Education', 'MA Linguistics']);
assert.deepEqual(cv.certifications, ['TESOL', 'DELE']);
assert.ok(cv.professional_summary.includes('Adult'));
assert.ok(loaded.exports.buildTemplateCv(input, 'tr').professional_summary.includes('öğrencilere'));
assert.throws(() => loaded.exports.buildTemplateCv({ ...input, teachingLanguages: '' }, 'en'));
assert.throws(() => loaded.exports.buildTemplateCv({ ...input, location: 'Atlantis' }, 'en'), /valid country/);
assert.equal(loaded.exports.validCvPhone('+34(612)345678'), true);
assert.equal(loaded.exports.validCvPhone('+34 612345678'), false);
assert.equal(loaded.exports.validCvPhone('12345'), false);
assert.throws(() => loaded.exports.buildTemplateCv({ ...input, phone: '12345' }, 'en'), /six digits/);
assert.ok(loaded.exports.CV_COUNTRIES.length >= 249);
assert.deepEqual(loaded.exports.profileCvDefaults({ display_name: 'Ada Teacher', email: 'ada@example.test', phone_number: '+34 612-345678', country: 'Spain', primary_role: 'tutor', primary_subjects: ['spanish'], teaching_stages: ['adult_stage'], teaching_languages: ['es', 'en'] }), { fullName: 'Ada Teacher', email: 'ada@example.test', phone: '+34612345678', location: 'Spain', role: 'tutor', subjects: 'spanish', teachingStages: 'adult_stage', teachingLanguages: 'es, en' });
process.stdout.write('Professional CV template fixture passed.\n');
