const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/lib/youtube.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const moduleRef = { exports: {} };
new Function('module', 'exports', 'require', compiled)(moduleRef, moduleRef.exports, require);
const { publicVideoId, youtubeVideoId } = moduleRef.exports;

const id = 'dQw4w9WgXcQ';
assert.equal(youtubeVideoId(`https://youtu.be/${id}`), id);
assert.equal(youtubeVideoId(`https://www.youtube.com/watch?v=${id}&t=10`), id);
assert.equal(youtubeVideoId(`https://www.youtube.com/shorts/${id}`), id);
assert.equal(publicVideoId(id, ''), id, 'saved video IDs work without a legacy URL');
assert.equal(publicVideoId('', `https://www.youtube.com/watch?v=${id}`), id);
assert.equal(publicVideoId('', `https://evil.example/watch?v=${id}`), '', 'external hosts cannot be embedded');
assert.equal(publicVideoId('not-a-video-id', 'javascript:alert(1)'), '', 'invalid stored IDs and schemes are rejected');
console.log('Public video URL fixtures passed');
