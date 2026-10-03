const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'expo/src/shared/program-structure.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleExports = {};
vm.runInNewContext(compiled, { exports: moduleExports });

const python = `import ast, json, pathlib
tree = ast.parse(pathlib.Path('streamlit/helpers/learning_programs.py').read_text())
names = {'_STAGE_STRUCTURE_RULES', '_ENGINE_STRUCTURE_OVERRIDES'}
values = {target.id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name) and target.id in names}
print(json.dumps(values))`;
const rules = JSON.parse(execFileSync('python3', ['-c', python], { cwd: root, encoding: 'utf8' }));
for (const [stage, base] of Object.entries(rules._STAGE_STRUCTURE_RULES)) {
  for (const [subject, engine] of [['Spanish', 'language'], ['English', 'language'], ['Study skills', 'study_skills'], ['Mathematics', 'general']]) {
    const expected = { ...base, ...(rules._ENGINE_STRUCTURE_OVERRIDES[engine]?.[stage] || {}) };
    const actual = moduleExports.programStructureRule(subject, stage);
    for (const [key, value] of Object.entries(expected)) {
      const camel = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
      assert.equal(actual[camel], value, `${subject}/${stage}/${key}`);
    }
    assert.equal(moduleExports.clampProgramStructure(subject, stage).units, expected.units_default);
    assert.equal(moduleExports.clampProgramStructure(subject, stage, 1, 1).units, expected.units_min);
    assert.equal(moduleExports.clampProgramStructure(subject, stage, 99, 99).lessonsPerUnit, expected.lessons_max);
  }
}
console.log('Program structure matches Python stage rules and overrides.');
