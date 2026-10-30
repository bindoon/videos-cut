// Private offscreen browser: executes local film code, never user browser tabs.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';

const request = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const {root, width, height, fps, source_hash: sourceHash, output} = request;
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const checksum = file => hash(fs.readFileSync(file));
const children = new Set();
function save(file, data) {
  fs.writeFileSync(file + '.tmp', JSON.stringify(data, null, 2) + '\n');
  fs.renameSync(file + '.tmp', file);
}
function inputsUnchanged() {
  for (const s of request.sources) {
    if (checksum(path.join(root, s.path)) !== s.sha256) throw Error(`Input changed during capture: ${s.path}`);
  }
}
async function tool(argv, log) {
  return await new Promise((resolve, reject) => {
    const proc = spawn(request.python, ['-m', 'videocut.ffmpeg_tools', ...argv], {stdio: ['ignore', 'pipe', 'pipe'], detached: true});
    children.add(proc);
    let stdout = '', stderr = '';
    proc.stdout.on('data', b => stdout += b);
    proc.stderr.on('data', b => stderr += b);
    proc.on('error', reject);
    proc.on('close', code => {
      children.delete(proc);
      fs.writeFileSync(log + '.stdout', stdout);
      fs.writeFileSync(log + '.stderr', stderr);
      if (code !== 0) return reject(Error(`videocut ffmpeg ${argv[0]} failed (${code}): ${stderr.slice(-1800)}`));
      try {
        // Encoding and probe emit one document. No loose text is accepted here.
        const doc = JSON.parse(stdout);
        save(log, doc);
        resolve(doc);
      } catch (error) { reject(error); }
    });
  });
}
function checkVideo(doc, count) {
  const expected = {width, height, fps, nb_frames: count, codec: 'h264', pix_fmt: 'yuv420p', color_range: 'tv'};
  for (const [key, value] of Object.entries(expected)) {
    if (doc.video?.[key] !== value) throw Error(`Encoded video ${key}: expected ${value}, got ${doc.video?.[key]}`);
  }
}
const types = {'.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.woff2': 'font/woff2', '.css': 'text/css'};
const server = http.createServer(async (req, res) => {
  try {
    let name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    if (name === '/') name = '/' + request.entry;
    const file = await fs.promises.realpath(path.resolve(root, '.' + name));
    if (!file.startsWith(root + path.sep)) { res.writeHead(403); res.end(); return; }
    const body = await fs.promises.readFile(file);
    res.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream');
    res.end(body);
  } catch { res.writeHead(404); res.end('Not found'); }
});
let browser;
let stopping = false;
async function stop() {
  if (stopping) return;
  stopping = true;
  for (const proc of children) {
    try { process.kill(-proc.pid, 'SIGTERM'); } catch { /* Already exited. */ }
  }
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}
for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, async () => { await stop(); process.exit(130); });

try {
  const require = createRequire(path.join(root, 'package.json'));
  let chromium;
  try { ({chromium} = require('playwright-core')); }
  catch { throw Error('Install playwright-core in the film directory (npm ci) before rendering'); }
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const args = ['--enable-gpu', '--ignore-gpu-blocklist', '--font-render-hinting=none', '--force-color-profile=srgb'];
  if (request.angle !== 'default') args.push(`--use-angle=${request.angle}`);
  browser = await chromium.launch({headless: true, executablePath: request.browser || undefined, args});
  const errors = [];
  const sessions = new WeakMap();
  const origin = `http://127.0.0.1:${server.address().port}`;
  async function page() {
    const p = await browser.newPage({viewport: {width, height}, deviceScaleFactor: 1});
    p.setDefaultTimeout(request.timeout_ms);
    p.on('pageerror', e => errors.push(String(e)));
    // Render inputs must be local and declared. No web service can change pixels mid-run.
    await p.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.origin === origin || ['data:', 'blob:'].includes(url.protocol)) return route.continue();
      errors.push(`Rendering input must be local: ${url.origin}`);
      return route.abort();
    });
    await p.goto(origin + '/' + request.entry, {waitUntil: 'load', timeout: request.timeout_ms});
    await p.waitForFunction(() => window.READY === true && typeof window.render === 'function');
    await p.evaluate(() => document.fonts.ready);
    if (errors.length) throw Error(errors.join('\n'));
    return p;
  }
  async function capture(p, t) {
    let timer;
    try {
      await Promise.race([p.evaluate(t => window.render(t), t), new Promise((_, reject) => {
        timer = setTimeout(() => reject(Error('render(t) timed out')), request.timeout_ms);
      })]);
    } finally { clearTimeout(timer); }
    if (errors.length) throw Error(errors.join('\n'));
    if (!sessions.has(p)) sessions.set(p, await p.context().newCDPSession(p));
    const shot = await sessions.get(p).send('Page.captureScreenshot', {
      format: 'png', fromSurface: true, captureBeyondViewport: false, optimizeForSpeed: true,
    });
    return Buffer.from(shot.data, 'base64');
  }
  const p = await page();
  const renderer = await p.evaluate(() => {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (!gl) return 'Canvas / no WebGL';
    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    const name = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'WebGL';
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    return name;
  });
  if (/swiftshader|llvmpipe|software/i.test(renderer)) console.error(`Software rendering: ${renderer}`);
  const runtime = {browser: browser.version(), renderer, angle: request.angle};
  const cacheKey = hash(JSON.stringify({sourceHash, runtime}));
  const run = path.join(output, 'renders', cacheKey.slice(0, 20));
  fs.mkdirSync(run, {recursive: true});
  console.log('RENDER', cacheKey.slice(0, 20), `${width}x${height}@${fps}`, renderer);

  // Independently addressed times must not depend on a previously rendered frame.
  const ta = request.duration * .21, tb = request.duration * .73;
  const first = await capture(p, ta);
  await capture(p, tb);
  if (!first.equals(await capture(p, ta))) throw Error('render(t) depends on previous frame state');

  if (request.mode === 'stills') {
    const scenes = request.scenes.length ? request.scenes : [{start: 0, end: request.duration}];
    const stills = [];
    const directory = path.join(run, 'stills');
    fs.mkdirSync(directory, {recursive: true});
    for (const [i, scene] of scenes.entries()) {
      const t = Math.min(request.duration - 1 / fps, scene.start + (scene.end - scene.start) * .52);
      const file = path.join(directory, `scene-${String(i).padStart(3, '0')}.png`);
      const pixels = await capture(p, t);
      fs.writeFileSync(file, pixels);
      stills.push({file, t, sha256: hash(pixels)});
      console.log('STILL', t.toFixed(3), file);
    }
    inputsUnchanged();
    const report = {schema: 'codefilm-stills-v1', source_hash: sourceHash, cache_key: cacheKey,
      ...runtime, width, height, deterministic_same_frame: true, stills};
    save(path.join(run, 'still-verification.json'), report);
    save(path.join(output, 'latest-stills.pending.json'), report);
  } else {
    const chunks = [];
    for (let a = request.start_frame; a < request.end_frame; a += request.chunk_frames) {
      const b = Math.min(request.end_frame, a + request.chunk_frames);
      chunks.push({a, b, file: path.join(run, `segment-${String(a).padStart(6, '0')}-${b}.mp4`)});
    }
    let next = 0;
    const began = Date.now();
    async function worker(p) {
      while (next < chunks.length) {
        const chunk = chunks[next++], recordFile = chunk.file + '.record.json';
        if (fs.existsSync(chunk.file)) {
          if (!fs.existsSync(recordFile)) throw Error(`Segment has no verified record: ${chunk.file}; use a new output directory`);
          const record = JSON.parse(fs.readFileSync(recordFile, 'utf8'));
          if (record.source_hash !== sourceHash || record.sha256 !== checksum(chunk.file)) throw Error(`Cached segment checksum mismatch: ${chunk.file}`);
          checkVideo(await tool(['probe', chunk.file, '--json'], chunk.file + '.probe.json'), chunk.b - chunk.a);
          chunk.sha256 = record.sha256;
          console.log('CACHED', chunk.file);
          continue;
        }
        const frames = path.join(run, `frames-${chunk.a}-${chunk.b}`);
        fs.mkdirSync(frames, {recursive: true});
        for (let f = chunk.a; f < chunk.b; f++) {
          fs.writeFileSync(path.join(frames, `frame_${String(f - chunk.a).padStart(6, '0')}.png`), await capture(p, f / fps));
          if ((f - chunk.a) % 60 === 0) console.log('FRAME', f, '/', request.end_frame);
        }
        const pending = chunk.file + '.pending.mp4';
        const encoding = ['sequence', '--dir', frames, '--pattern', 'frame_%06d.png', '--fps', String(fps),
          '--preset', 'fast', '--quality', '18', '--no-hw', '-o', pending];
        if (fs.existsSync(pending)) fs.unlinkSync(pending); // Only this run's incomplete encode.
        await tool([...encoding, '--dry-run', '--json'], chunk.file + '.plan.json');
        await tool([...encoding, '--json'], chunk.file + '.encode.json');
        checkVideo(await tool(['probe', pending, '--json'], chunk.file + '.probe.json'), chunk.b - chunk.a);
        chunk.sha256 = checksum(pending);
        fs.renameSync(pending, chunk.file);
        save(recordFile, {...chunk, source_hash: sourceHash});
        fs.rmSync(frames, {recursive: true}); // Validated disposable PNGs only.
        console.log('CHUNK', chunk.a, chunk.b);
      }
    }
    const pages = [p];
    for (let i = 1; i < Math.min(request.workers, chunks.length); i++) pages.push(await page());
    await Promise.all(pages.map(worker));
    inputsUnchanged();
    const manifest = {schema: request.schema, source_hash: sourceHash, cache_key: cacheKey, ...runtime,
      config: request.config, sources: request.sources, toolchain_sha256: request.toolchain_sha256,
      width, height, fps, total_frames: request.total_frames,
      start_frame: request.start_frame, end_frame: request.end_frame,
      frames: request.end_frame - request.start_frame, duration: (request.end_frame - request.start_frame) / fps,
      deterministic_same_frame: true, chunks, elapsed_seconds: (Date.now() - began) / 1000};
    save(path.join(run, 'render-manifest.json'), manifest);
    save(path.join(output, 'render-manifest.pending.json'), manifest);
    console.log('RENDER COMPLETE', path.join(run, 'render-manifest.json'));
  }
} catch (error) {
  console.error('codefilm:', error.stack || String(error));
  process.exitCode = 1;
} finally { await stop(); }
