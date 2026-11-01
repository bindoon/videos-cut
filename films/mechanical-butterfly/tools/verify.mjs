// Checks actual transformed geometry, independent time addressing, and controls.
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {chromium} from 'playwright-core';
import {P,linkage,stateAt} from '../model.js';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.resolve(process.argv[2]??path.join(root,'../../outputs/mechanical-butterfly-qa'));
await fs.mkdir(output,{recursive:true});
let maxClosure=0;
for(let i=0;i<=7200;i++){
  const k=linkage(i*Math.PI*2/7200);
  const rod=Math.hypot(k.q[0]-k.p[0],k.q[1]-k.p[1]);
  const rocker=Math.hypot(k.q[0]-P.hingeX,k.q[1]-P.hingeY);
  maxClosure=Math.max(maxClosure,Math.abs(rod-P.rod));
  assert.ok(Math.abs(rocker-P.rocker)<1e-12);assert.ok(Math.abs(rod-P.rod)<1e-12);
  assert.ok(k.angle>-.7&&k.angle<.85);
}
const server=http.createServer(async(req,res)=>{
  try{const name=decodeURIComponent(new URL(req.url,'http://local').pathname);const f=path.resolve(root,'.'+(name==='/'?'/index.html':name));
    if(!f.startsWith(root+path.sep)){res.writeHead(403);res.end();return;}
    const data=await fs.readFile(f);res.setHeader('Content-Type',f.endsWith('.js')?'text/javascript':f.endsWith('.html')?'text/html':'application/octet-stream');res.end(data);
  }catch{res.writeHead(404);res.end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
let browser;
try{
  browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-gpu','--ignore-gpu-blocklist','--use-angle=metal','--force-color-profile=srgb']});
  const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);await page.waitForFunction(()=>window.READY);
  let maxHorn=0,maxRod=0,minGroundClearance=Infinity;const poses=[];
  // Every 0.2 s, including both sides of each transition and the final pose.
  for(let frame=0;frame<=130;frame++){
    const t=frame/5;
    const pose=await page.evaluate(t=>{window.render(t);return {...window.auditPose(),angle:window.currentState.angle,explode:window.currentState.explode};},t);
    maxHorn=Math.max(maxHorn,pose.hornError);maxRod=Math.max(maxRod,pose.rodError);minGroundClearance=Math.min(minGroundClearance,pose.groundClearance);
    assert.ok(pose.hornError<1e-10,`Horn detached at ${t}: ${pose.hornError}`);
    assert.ok(pose.rodError<1e-10,`Rod length changed at ${t}: ${pose.rodError}`);
    assert.ok(pose.groundClearance>.2,`Wing intersects ground at ${t}: ${pose.groundClearance}`);
    poses.push({t,...pose});
  }
  await page.evaluate(()=>window.render(6.25));const a=await page.screenshot();
  await page.evaluate(()=>window.render(18.4));await page.evaluate(()=>window.render(6.25));
  assert.ok(a.equals(await page.screenshot()),'A → B → A pixel mismatch');
  const stills=[];
  for(const t of [2.08,6.08,10.08,14.08,18.6,22.56,25.04]){
    await page.evaluate(t=>window.render(t),t);const name=`beat-${String(t).replace('.','-')}.png`;
    await page.screenshot({path:path.join(output,name)});stills.push({t,file:name});
  }
  // Confirm the actual click targets produce visible pose changes.
  await page.mouse.click(1805/1.5,208/1.5);await page.evaluate(()=>window.render(6));
  assert.equal(await page.evaluate(()=>window.currentState.shell),1);
  await page.mouse.click(1680/1.5,248/1.5);await page.evaluate(()=>window.render(6));
  assert.equal(await page.evaluate(()=>window.currentState.explode),1);
  await page.mouse.click(1805/1.5,248/1.5);await page.evaluate(()=>window.render(6));
  assert.equal(await page.evaluate(()=>window.currentState.explode),stateAt(6).explode);
  await page.mouse.click(1825/1.5,744/1.5);await page.evaluate(()=>window.render(6));
  assert.equal(await page.evaluate(()=>window.currentState.hz),3.6);
  await page.keyboard.press('h');await page.evaluate(()=>window.render(6));
  assert.equal(await page.evaluate(()=>document.querySelector('#hud').getContext('2d').getImageData(50,120,1,1).data[3]),0);
  await page.keyboard.press('h');assert.deepEqual(errors,[]);
  let standalone;
  if(process.argv[3]){
    const offline=await browser.newPage({viewport:{width:1280,height:720}}),requests=[];
    offline.on('pageerror',e=>errors.push(String(e)));
    offline.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url());});
    await offline.goto(pathToFileURL(path.resolve(process.argv[3])).href);
    await offline.waitForFunction(()=>window.READY&&window.currentState.t>.1);
    const initial=await offline.evaluate(()=>window.currentState.t);
    await offline.waitForFunction(t=>window.currentState.t>t+.1,initial);
    await offline.keyboard.press('Space');
    const held=await offline.evaluate(()=>window.currentState.t);
    await offline.evaluate(()=>new Promise(resolve=>{let n=0;function f(){if(++n===8)resolve();else requestAnimationFrame(f);}requestAnimationFrame(f);}));
    assert.equal(await offline.evaluate(()=>window.currentState.t),held);
    await offline.mouse.click(1805/1.5,208/1.5);
    assert.equal(await offline.evaluate(()=>window.currentState.shell),1);
    const before=await offline.screenshot();
    await offline.mouse.move(700,350);await offline.mouse.down();await offline.mouse.move(820,390,{steps:6});await offline.mouse.up();
    assert.ok(!before.equals(await offline.screenshot()),'Orbit did not change offline pixels');
    assert.deepEqual(requests,[]);assert.deepEqual(errors,[]);
    standalone={file:path.resolve(process.argv[3]),externalRequests:requests,autoplay:true,pause:true,carapace:true,orbit:true};
    await offline.screenshot({path:path.join(output,'offline-interactive.png')});
  }
  const report={passed:true,phase_samples:7201,pose_samples:131,maxClosure,maxHorn,maxRod,minGroundClearance,deterministic_same_frame:true,controls:['carapace','explode','auto','frequency','hide-panels'],standalone,pageErrors:errors,stills,poses};
  await fs.writeFile(path.join(output,'geometry-verification.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({...report,poses:undefined,stills:undefined},null,2));
}finally{await browser?.close();await new Promise(r=>server.close(r));}
