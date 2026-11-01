import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {chromium} from 'playwright-core';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.resolve(process.argv[2]);await fs.mkdir(output,{recursive:true});
const server=http.createServer(async(req,res)=>{
 try{let name=new URL(req.url,'http://local').pathname;if(name==='/')name='/index.html';
  const file=path.resolve(root,'.'+decodeURIComponent(name));if(!file.startsWith(root+path.sep))throw Error('outside');
  res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.html')?'text/html':'application/octet-stream');res.end(await fs.readFile(file));
 }catch{res.writeHead(404);res.end()}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
let browser;
try{
 browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROME??'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--use-angle=metal','--enable-gpu','--ignore-gpu-blocklist']});
 const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto(`http://127.0.0.1:${server.address().port}/index.html`);await page.waitForFunction(()=>window.READY);
 const states=[];
 for(let frame=0;frame<864;frame+=6){
  const s=await page.evaluate(async t=>{await window.render(t);return window.FILM_STATE},frame/24);
  assert.deepEqual(s.footPosition,[-1,0,.05],'The bearing foot slipped');
  assert.deepEqual(s.footRotation,[0,0,0,'XYZ'],'Torque must not make the planted foot slide');
  assert.ok(s.camera.every(Number.isFinite));
  if(s.t>=16.75)for(const contact of s.toeContacts)assert.ok(Math.abs(contact-.012)<1e-9,`Toe floats or penetrates ${s.t}`);
  states.push(s);
 }
 const at=async t=>page.evaluate(async t=>{await window.render(t);return window.FILM_STATE},t);
 assert.equal((await at(10)).rootGrowth,0);assert.equal((await at(20)).rootGrowth,1);
 const initial=await at(25),twisted=await at(29);
 assert.ok(twisted.thighTwist[1]>initial.thighTwist[1]+.08,'Thigh must turn CCW from hip toward foot');
 for(const [a,b] of [[0,28],[18,5],[28,12],[35.9,0]]){
  await at(a);const one=await page.screenshot();await at(b);await at(a);assert.ok(one.equals(await page.screenshot()),`Non-deterministic frame ${a}`);
 }
 const stills=[];
 for(const t of [0,3,8,12,16,19,23,28,34,35.9]){await at(t);const name=`frame-${String(t).replace('.','-')}.png`;await page.screenshot({path:path.join(output,name)});stills.push({t,file:name})}
 // Verify the actual offline handoff, including bundled fonts and playback controls.
 if(process.argv[3]){
  const offline=await browser.newPage({viewport:{width:1280,height:720}});offline.on('pageerror',e=>errors.push(String(e)));
  const external=[];offline.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url())});
  await offline.goto(pathToFileURL(path.resolve(process.argv[3])).href);await offline.waitForFunction(()=>window.READY);
  await offline.locator('#play').click();
  await offline.locator('#seek').fill('19');
  await offline.waitForFunction(()=>Math.abs(window.FILM_STATE.t-19)<.001);
  assert.equal(await offline.locator('#play').textContent(),'播放');assert.deepEqual(external,[]);
  assert.ok(await offline.evaluate(()=>document.fonts.check('400 24px "Noto Sans SC"')));
  await offline.screenshot({path:path.join(output,'offline-interactive.png')});await offline.close();
 }
 assert.deepEqual(errors,[]);
 const report={passed:true,poses:states.length,plantedFoot:true,toeContactHeight:.012,thighCounterclockwise:true,deterministic_same_frame:true,offlineInteractive:!!process.argv[3],errors,stills};
 await fs.writeFile(path.join(output,'pose-verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}finally{await browser?.close();await new Promise(r=>server.close(r))}
