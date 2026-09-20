import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const root = path.resolve(process.argv[2] || '.');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'experience.json'), 'utf8'));
assert.match(manifest.id, /^[a-z][a-z0-9-]{0,63}$/);
assert.equal(manifest.contract_version, '1.0', 'Unsupported frontend contract');
assert.equal(manifest.entry, 'dist/index.html');
assert.ok(typeof manifest.version === 'string' && manifest.version.length);
assert.ok(Array.isArray(manifest.capabilities) && manifest.capabilities.length);
assert.ok(manifest.capabilities.every(c => ['labs', 'practice', 'transfer'].includes(c)));
const html = fs.readFileSync(path.join(root, manifest.entry), 'utf8');
const assets = [...html.matchAll(/(?:src|href)="([^"]+)"/g)].map(m => m[1]).filter(url => /\.(js|css)$/.test(url));
assert.ok(assets.some(url => url.endsWith('.js')), 'Build must contain an executable entry');
for (const url of assets) {
  assert.ok(url.startsWith(`/experience/${manifest.id}/`), `Asset base must be /experience/${manifest.id}/: ${url}`);
  const asset = path.resolve(root, 'dist', url.slice(`/experience/${manifest.id}/`.length));
  assert.ok(asset.startsWith(path.join(root, 'dist') + path.sep));
  assert.ok(fs.existsSync(asset), `Missing built asset: ${url}`);
}
console.log(`Compatible static build: ${manifest.id} ${manifest.version} (contract 1.0). Run the journey checks in skill/references/verification.md before installation.`);
