const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const sourcePath = path.join(root, 'streamlit/helpers/learning_programs.py');
const snapshot = JSON.parse(fs.readFileSync(path.join(root, 'expo/src/server/program-guidance.json'), 'utf8'));
const python = `import ast,json,pathlib
tree=ast.parse(pathlib.Path(${JSON.stringify(sourcePath)}).read_text())
names=set(${JSON.stringify(Object.keys(snapshot))})
values={target.id:ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) for target in node.targets if isinstance(target,ast.Name) and target.id in names}
print(json.dumps(values,ensure_ascii=False))`;
assert.deepEqual(snapshot, JSON.parse(execFileSync('python3', ['-c', python], { encoding: 'utf8' })));

const moduleExports = {};
const guidancePath = path.join(root, 'expo/src/server/program-guidance.ts');
const compiled = ts.transpileModule(fs.readFileSync(guidancePath, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, resolveJsonModule: true } }).outputText;
vm.runInNewContext(compiled, { exports: moduleExports, require: (specifier) => { assert.equal(specifier, './program-guidance.json'); return snapshot; } });

const stages = ['early_primary', 'upper_primary', 'lower_secondary', 'upper_secondary', 'adult_stage'];
const cases = [
  ...['english', 'spanish'].flatMap((subject) => stages.flatMap((stage) => ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'].map((level) => [subject, stage, level, '']))),
  ...['mathematics', 'science', 'music', 'study_skills'].flatMap((subject) => stages.flatMap((stage) => ['beginner_band', 'intermediate_band', 'advanced_band'].map((level) => [subject, stage, level, '']))),
  ['other', 'adult_stage', 'intermediate_band', 'Algebra'],
  ['other', 'lower_secondary', 'beginner_band', 'Biology'],
];
const profilePython = `import ast,json,pathlib,re
tree=ast.parse(pathlib.Path(${JSON.stringify(sourcePath)}).read_text())
names=set(${JSON.stringify(Object.keys(snapshot))})
functions={'_subject_engine','infer_subject_family','_fallback_focus_strands','_fallback_progression_line','_fallback_review_line','_fallback_subject_specific_notes','_fallback_progression_level','_subject_progression_profile'}
body=[node for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id in names for target in node.targets) or isinstance(node,ast.FunctionDef) and node.name in functions]
class LP:
  def normalize_subject(self,value): return str(value or '').strip().lower().replace(' ','_')
  def get_subject_engine(self,value): return {'english':'language','spanish':'language','mathematics':'math','science':'science','music':'music','study_skills':'study_skills'}.get(value,'general')
ns={'_lp':lambda:LP(),'_clean_text':lambda value:re.sub(r'\\s+',' ',str(value or '')).strip()}
exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),${JSON.stringify(sourcePath)},'exec'),ns)
cases=${JSON.stringify(cases)}
print(json.dumps([ns['_subject_progression_profile'](*case) for case in cases],ensure_ascii=False))`;
const expected = JSON.parse(execFileSync('python3', ['-c', profilePython], { encoding: 'utf8' }));
cases.forEach(([subject, stage, level, custom], index) => {
  const actual = JSON.parse(JSON.stringify(moduleExports.programProgressionProfile(subject, stage, level, custom)));
  assert.deepEqual(actual, expected[index], `${subject}/${stage}/${level}`);
});
assert.equal(moduleExports.inferProgramSubjectFamily('other', 'Algebra'), 'math');
assert.match(moduleExports.programTrackGuidance('exam_prep', 'dele').join(' '), /DELE/);
console.log('Program guidance constants and progression profiles match Python.');
