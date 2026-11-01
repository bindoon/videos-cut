import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright-core';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.resolve(process.argv[2]??path.join(root,'../../outputs/butterfly-cinematic-qa'));
await fs.mkdir(output,{recursive:true});
const timeline=JSON.parse(await fs.readFile(path.join(root,'cinematic-timeline.json'),'utf8'));
const server=http.createServer(async(req,res)=>{
 try{const file=path.resolve(root,'.'+new URL(req.url,'http://local').pathname);
  if(!file.startsWith(root+path.sep))throw Error('outside root');
  const data=await fs.readFile(file);res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.html')?'text/html':'application/octet-stream');res.end(data);
 }catch{res.writeHead(404);res.end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
let browser;
try{
 browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROME??'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--enable-gpu','--ignore-gpu-blocklist','--use-angle=metal','--force-color-profile=srgb']});
 const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 await page.goto(`http://127.0.0.1:${server.address().port}/cinematic.html`);await page.waitForFunction(()=>window.READY&&window.cinematicShots);
 let minClearance=Infinity,maxHorn=0,maxRod=0;const poses=[];
 const times=new Set(Array.from({length:161},(_,i)=>i/5));
 for(const s of timeline.scenes.slice(1))for(const d of [-1/30,0,1/30])times.add(s.start+d);
 for(const t of [...times].sort((a,b)=>a-b)){
  const result=await page.evaluate(t=>{window.render(t);return {...window.auditPose(),...window.cinematicAudit};},t);
  assert.ok(result.hornError<1e-10,`Wing detached ${t}`);assert.ok(result.rodError<1e-10,`Rod deformed ${t}`);assert.ok(result.groundClearance>.2,`Wing/ground ${t}`);
  minClearance=Math.min(minClearance,result.groundClearance);maxHorn=Math.max(maxHorn,result.hornError);maxRod=Math.max(maxRod,result.rodError);
  poses.push({t,...result});
 }
 const stills=[];
 for(const s of timeline.scenes){const t=s.start+(s.end-s.start)*.52;
  const a=await page.evaluate(t=>{window.render(t);return window.cinematicAudit;},t);
  const expected=String(stills.length+1).padStart(2,'0');assert.equal(a.shot,expected);
  const file=`shot-${expected}.png`;await page.screenshot({path:path.join(output,file)});stills.push({t,file,...a});
 }
 assert.equal(stills.length,11);assert.ok(stills[5].cutaway);
 const dir=v=>{const a=v.camera.map((x,i)=>x-v.target[i]),n=Math.hypot(...a);return a.map(x=>x/n);};
 const angle=(a,b)=>Math.acos(Math.min(1,Math.max(-1,dir(a).reduce((s,x,i)=>s+x*dir(b)[i],0))))*180/Math.PI;
 assert.ok(angle(stills[1],stills[2])>60,'Front and side views are insufficiently different');
 assert.ok(angle(stills[1],stills[3])>60,'Top view is not a real top view');
 const layers=stills[8].layers;
 assert.ok(layers.shell[1]>layers.gear[1]+1);
 assert.ok(layers.gear[1]>layers.motor[1]+1);
 assert.ok(layers.motor[1]>layers.board[1]+1);
 assert.ok(layers.board[1]>layers.battery[1]+1);
 // Revisit a cutaway and an assembled pose in both orders. Pixel identity catches
 // stale clipping planes and leftover disassembly transforms.
 for(const [a,b] of [[14.5,4.2],[24.1,17.5]]){
  await page.evaluate(t=>window.render(t),a);const shot=await page.screenshot();
  await page.evaluate(t=>window.render(t),b);await page.evaluate(t=>window.render(t),a);
  assert.ok(shot.equals(await page.screenshot()),`Time-addressing mismatch ${a}`);
 }
 assert.deepEqual(errors,[]);
 const report={passed:true,shotCount:11,poseCount:poses.length,minClearance,maxHorn,maxRod,
  frontSideAngle:angle(stills[1],stills[2]),frontTopAngle:angle(stills[1],stills[3]),layerSeparation:true,deterministic_same_frame:true,errors,stills,poses};
 await fs.writeFile(path.join(output,'cinematic-verification.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify({...report,poses:undefined,stills:undefined},null,2));
}finally{await browser?.close();await new Promise(r=>server.close(r));}
