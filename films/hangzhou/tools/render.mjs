// Compatibility entry point. Capture/cache/encoding logic lives in videocut.
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const film = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const root = path.resolve(film, '../..');
let args = process.argv.slice(2);
const mode = args.includes('--stills') ? 'stills' : 'render';
args = args.filter(a => a !== '--stills');
const python = process.env.VIDEOCUT_PYTHON || path.join(root, '.venv/bin/python');
const result = spawnSync(python, ['-m', 'videocut.codefilm', mode, '--config', path.join(film, 'codefilm.json'), ...args], {stdio: 'inherit'});
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);
