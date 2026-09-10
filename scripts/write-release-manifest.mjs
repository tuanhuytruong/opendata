import { createHash } from 'node:crypto';
import { readFile, readdir, writeFile } from 'node:fs/promises';
import { join, relative } from 'node:path';
import { execFileSync } from 'node:child_process';

const root = new URL('..', import.meta.url).pathname;
const dist = join(root, 'dist');
const sha256 = async path => createHash('sha256').update(await readFile(path)).digest('hex');
const sourceSha = process.env.OPENDATA_BUILD_SHA ?? execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();

async function files(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async entry => entry.isDirectory() ? files(join(directory, entry.name)) : [join(directory, entry.name)]));
  return nested.flat();
}

const artifactFiles = (await files(dist)).filter(path => !path.endsWith('release-manifest.json')).sort();
const assets = Object.fromEntries(await Promise.all(artifactFiles.map(async path => [relative(dist, path), await sha256(path)])));
const locks = Object.fromEntries(await Promise.all(['package-lock.json', 'requirements.lock'].map(async path => [path, await sha256(join(root, path))])));
const manifest = { version: 1, source_sha: sourceSha, built_at: new Date().toISOString(), assets, lockfiles: locks };
await writeFile(join(dist, 'release-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
