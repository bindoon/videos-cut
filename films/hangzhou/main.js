import * as THREE from 'three';
import {makeCity} from './city.js';

const [M,TL,ST]=await Promise.all(['model','timeline','stats'].map(n=>fetch(`./data/${n}.json`).then(r=>{if(!r.ok)throw Error(`${n}: ${r.status}`);return r.json()})));
await document.fonts.load('400 32px "Noto Sans SC"');await document.fonts.load('300 90px "Noto Sans SC"');await document.fonts.ready;
// GTAO builds a noise texture during setup; seed it identically in every
// offline worker so the film does not change with rendering order.
let noiseSeed=0x48414e47;Math.random=()=>{noiseSeed=(Math.imul(noiseSeed,1664525)+1013904223)>>>0;return noiseSeed/4294967296};
const W=innerWidth,H=innerHeight,C=makeCity(W,H,M),A=M.anchors;
window.FILM_DEBUG=C;
const hud=document.querySelector('#hud');hud.width=W;hud.height=H;const g=hud.getContext('2d');
const colors=['#efd5ad','#ffc17a','#81e3e7','#e5b86c','#7ce8df','#edb16e','#dbb7e6','#85b9ff','#9edfe8','#d2b2f1','#b9b7ff','#e8c793'];
const smooth=(a,b,x)=>{const t=THREE.MathUtils.clamp((x-a)/(b-a),0,1);return t*t*(3-2*t)};
const mix=THREE.MathUtils.lerp;
const cameras=[
  [[.09,.070,.49],[.06,.005,.20]],
  [[-.31,.75,1.10],[-.06,0,.10]],
  [[.28,1.05,.61],[-.18,0,-.28]],
  [[.60,.68,.72],[.02,0,.20]],
  [[-.60,.36,.62],[-.30,0,.14]],
  [[.49,.58,.93],[.02,0,.30]],
  [[-.85,1.02,1.00],[-.13,0,.15]],
  [[1.02,.85,1.08],[.25,0,.18]],
  [[.12,.62,1.23],[.40,0,.30]],
  [[.70,1.95,1.47],[0,0,0]],
  [[.78,.095,.55],[.37,.010,.12]],
  [[.32,2.70,2.05],[0,0,0]]
];
const keyTimes=TL.scenes.map(s=>s.start+(s.end-s.start)*.48);
const posCurve=new THREE.CatmullRomCurve3(cameras.map(x=>new THREE.Vector3(...x[0])),false,'catmullrom',.25);
const aimCurve=new THREE.CatmullRomCurve3(cameras.map(x=>new THREE.Vector3(...x[1])),false,'catmullrom',.25);
const centreKeys=['oldcity','oldcity','canal','oldcity','westlake','oldcity','oldcity','qianjiang','river','westlake','qianjiang','westlake'];
function font(size,weight=400){g.font=`${weight} ${size}px "Noto Sans SC",sans-serif`}
function text(s,x,y,size=24,color='#e5e9ed',weight=400,align='left'){font(size,weight);g.textAlign=align;g.fillStyle=color;g.fillText(s,x,y)}
function line(x,y,x1,y1,color,width=1){g.strokeStyle=color;g.lineWidth=width;g.beginPath();g.moveTo(x,y);g.lineTo(x1,y1);g.stroke()}
function screen(key,height=.004){const [x,z]=A[key],p=new THREE.Vector3(x,height,z).project(C.camera);return[(p.x+1)*960,(1-p.y)*540,p.z]}
function pin(key,zh,en,dx=50,dy=-85,color='#ffd39b'){
  const [x,y,z]=screen(key);if(z>1||x<350||x>1860||y<160||y>920)return;
  const xx=x+dx,yy=y+dy;g.save();g.globalAlpha=.9;
  line(x,y,x,yy+25,color,1);line(x,yy+25,xx,yy+25,color,1);
  g.beginPath();g.arc(x,y,3,0,Math.PI*2);g.fillStyle=color;g.fill();
  font(23,500);const wid=Math.max(g.measureText(zh).width,150)+30;
  g.fillStyle='rgba(5,10,17,.80)';g.fillRect(xx-10,yy-18,wid,58);
  text(zh,xx+2,yy+5,23,'#f0f1ee',500);text(en,xx+2,yy+28,15,'#c3c8cd');g.restore();
}

function drawHud(t,si,p){
  const s=TL.scenes[si],accent=colors[si];g.setTransform(W/1920,0,0,H/1080,0,0);g.clearRect(0,0,1920,1080);
  const alpha=smooth(0,1.0,t)*(1-smooth(TL.duration-.7,TL.duration,t));g.globalAlpha=alpha;
  const left=g.createLinearGradient(0,0,650,0);left.addColorStop(0,'rgba(2,5,10,.78)');left.addColorStop(.65,'rgba(2,5,10,.24)');left.addColorStop(1,'rgba(2,5,10,0)');g.fillStyle=left;g.fillRect(0,0,700,1080);
  const bot=g.createLinearGradient(0,880,0,1080);bot.addColorStop(0,'rgba(0,0,0,0)');bot.addColorStop(1,'rgba(0,0,0,.83)');g.fillStyle=bot;g.fillRect(0,880,1920,200);
  text('H A N G Z H O U',72,64,20,'#e2e7eb',500);
  text('杭州 · 1:10,000 城市白模',72,96,20,'#a6b0bc');
  text('CMAB · © OpenStreetMap contributors',72,123,14,'#83909d');
  // The top timeline is editorial, with labelled anchors; spacing is not a
  // false linear scale of years or an inferred construction date per roof.
  const marks=['589','907','1090','1138','1913','2001','今日'];const xx=760,yy=74,span=1030;
  line(xx,yy,xx+span,yy,'#68717b',1);
  for(let i=0;i<marks.length;i++){const x=xx+i*span/6;line(x,yy-5,x,yy+5,'#78828d');text(marks[i],x,yy+29,15,'#9aa3ae',400,'center')}
  const index=[0,0,0.55,1,2,3,4,5,5.5,5.7,6,6][si];const px=xx+Math.min(6,index+p*.12)*span/6;
  g.fillStyle=accent;g.beginPath();g.moveTo(px,yy-8);g.lineTo(px-5,yy-17);g.lineTo(px+5,yy-17);g.fill();
  const enter=smooth(0,.09,p),exit=1-smooth(.94,1,p),fade=enter*exit;
  g.save();g.globalAlpha=alpha*fade;
  if(si===0){
    text('一城山水',74,383,71,'#f2f1ed',300);text('千年生长',74,472,71,'#f2f1ed',300);
    line(76,515,180,515,accent,3);text('THE RINGS OF HANGZHOU',75,556,21,'#c1c9cf',300);
    text(`${ST.building_parts.toLocaleString()} 栋建筑轮廓`,76,637,23,'#d0d7de');
    text(`${ST.scene_rectangle_km2.toFixed(1)} km² · 主城区取景`,76,674,19,'#9aa7b5');
  }else if(si===11){
    text('一城山水，千年生长',76,405,52,'#f0f0ea',300);
    text('THE RINGS OF HANGZHOU',78,449,25,'#c3cbd2',300);line(78,483,193,483,accent,3);
    text('杭州',78,562,40,'#f3e4c7',300);
    text('从西湖，到钱塘江。',80,607,26,'#c2cad1');
    text('画面：Three.js 程序化渲染',80,704,18,'#98a5b3');
    text('建筑：CMAB · Zhang, Zhao & Long (2025)',80,736,16,'#98a5b3');
    text('水系：© OpenStreetMap contributors',80,766,16,'#98a5b3');
  }else{
    text(`${String(si).padStart(2,'0')}  /  城市的年轮`,76,310,19,'#9aa5b2');line(77,334,135,334,accent,3);
    text(s.year,72,442,s.year.length>7?60:94,'#f0f1ed',300);
    text(s.title,77,500,31,'#e3e7e9',500);text(s.en,78,537,16,'#a6b2bf',300);
    if(si<=6){text('历史位置与光层示意',78,593,16,'#8e9ca9');text('底模为现代建筑数据',78,620,15,'#7f8e9c')}
    if(si===7){text('西湖时代 → 钱塘江时代',78,600,23,accent,300)}
    if(si===8){text('湖 · 河 · 江',78,601,27,accent,300)}
    if(si===9){
      const labels=[['2011','西湖文化景观'],['2014','大运河'],['2019','良渚古城遗址']];
      for(let j=0;j<3;j++){const y=601+j*53;line(79,y-9,103,y-9,colors[4+j],2);text(labels[j][0],118,y,21,'#e7e3db',300);text(labels[j][1],191,y,19,'#b9c6d2')}
      text('良渚位于主模型西北侧，未纳入本次取景',79,790,14,'#8f9eaf');
    }
    if(si===10){text('高度：CMAB 估算 / OSM 标注',78,605,17,'#9faaba');const gr=g.createLinearGradient(80,0,305,0);gr.addColorStop(0,'#7478e1');gr.addColorStop(.5,'#be91b1');gr.addColorStop(1,'#e7bc79');g.fillStyle=gr;g.fillRect(80,629,225,4);text('低',80,662,15,'#9faaba');text('高',300,662,15,'#9faaba')}
  }
  if(si===1)pin('oldcity','杭州旧城','Historic city area',50,-100,accent);
  if(si===2)pin('canal','京杭大运河','The Grand Canal',60,-80,accent);
  if(si===3)pin('palace','吴越 · 钱塘','Wuyue / Qiantang',40,-70,accent);
  if(si===4){pin('westlake','西湖','West Lake',70,-110,accent);pin('sudi','苏堤','Su Causeway',-70,60,'#ffe2aa')}
  if(si===5){pin('palace','南宋皇城遗址一带','Southern Song palace area',50,-80,accent);pin('wulin','街市向北延展','The city stretches north',70,-90,accent)}
  if(si===6)pin('westlake','西湖与城','The lake meets the city',50,-90,accent);
  if(si===7)pin('qianjiang','钱江新城','Qianjiang New City',55,-100,accent);
  if(si===8){pin('qianjiang','钱江新城','Qianjiang New City',-60,-120,accent);pin('olympic','钱江世纪城一侧','Qianjiang Century City',80,-60,accent)}
  if(si===10){pin('qianjiang','钱江新城','Qianjiang skyline',50,-100,accent)}
  g.restore();
  const cue=TL.cues.find(c=>c.start<=t&&t<c.end);if(cue){
    // Caption coordinates are independent of moving 3D geometry, and use the
    // exact serialized SRT times produced from the narration PCM.
    font(31,500);const cw=g.measureText(cue.text).width;font(18,300);const ew=g.measureText(cue.en).width;
    const plate=Math.min(1770,Math.max(cw,ew)+52);g.fillStyle='rgba(2,6,10,.86)';g.beginPath();g.roundRect(960-plate/2,941,plate,87,10);g.fill();
    text(cue.text,960,978,31,'#f1f2ed',500,'center');text(cue.en,960,1012,18,'#c1cbd3',300,'center');
  }
  text('真实城市数据 · 代码逐帧绘制',1848,1046,14,'#778591',300,'right');
  g.globalAlpha=1;
}

window.DUR=TL.duration;window.TL=TL;window.MODEL_STATS=ST;
window.render=t=>{
  t=THREE.MathUtils.clamp(t,0,TL.duration-1e-6);let si=TL.scenes.findIndex(s=>s.start<=t&&t<s.end);if(si<0)si=TL.scenes.length-1;
  const s=TL.scenes[si],p=THREE.MathUtils.clamp((t-s.start)/(s.end-s.start),0,1);
  let ki=keyTimes.findIndex(x=>x>t)-1;if(ki<0)ki=t<keyTimes[0]?-1:keyTimes.length-1;
  let u;
  if(ki<0)u=0;else if(ki>=keyTimes.length-1)u=1;else u=(ki+(t-keyTimes[ki])/(keyTimes[ki+1]-keyTimes[ki]))/(keyTimes.length-1);
  const cp=posCurve.getPoint(u),aim=aimCurve.getPoint(u);
  // A slight deterministic drift keeps the first and last holds alive.
  if(t<keyTimes[0])cp.x-=.028*(1-t/keyTimes[0]);
  if(t>keyTimes.at(-1))cp.y+=.14*smooth(keyTimes.at(-1),TL.duration,t);
  C.camera.position.copy(cp);C.camera.lookAt(aim);
  // A macro near plane loses depth precision when the camera cranes out.
  // Scale it with focus distance so the plinth and top do not z-fight.
  const dist=cp.distanceTo(aim);C.camera.near=Math.max(.002,dist*.025);C.camera.far=Math.max(6,dist+4);C.camera.updateProjectionMatrix();C.camera.updateMatrixWorld();
  const open=smooth(.4,2.0,t),close=smooth(TL.duration-7,TL.duration-2,t);
  const lights=si===0?mix(2.35,.55,smooth(1,5,t)):si===11?mix(.44,2.3,close):.43;
  C.key.intensity=lights;C.fill.intensity=si===0||si===11?.20:.10;C.rim.intensity=.20;
  C.U.uLight.value=si===0?.12*open:(si===11?(1-close)*.8:.76*smooth(0,.10,p)*(1-smooth(.96,1,p)));
  C.U.uMode.value=si;C.U.uT.value=t;C.U.uProgress.value=smooth(0,.78,p);C.U.uCentre.value.set(...A[centreKeys[si]]);C.U.uAccent.value.set(colors[si]);
  for(const l of C.routes.children){const r=l.userData;let opacity=0;if(si===2&&r.kind==='canal')opacity=.85*smooth(0,.2,p);if(si===4&&(r.kind==='causeway'||r.name.includes('苏堤')))opacity=.95*smooth(.1,.5,p);if(si===8&&r.bridge==='yes')opacity=.85*smooth(0,.4,p);l.material.opacity=opacity;}
  C.post.dof.focus=dist;
  const near=dist<.8;const clarity=window.CITY_CLARITY??1;C.post.dof.aper=(near?3.0:1.6)/clarity;C.post.dof.maxCoc=(near?10:3)/clarity;C.post.dof.aoAmt=near?.45:0;
  C.post.bloom.strength=si===4?.34:.43;
  C.post.vig.uniforms.fade.value=smooth(0,.6,t)*(1-smooth(TL.duration-.6,TL.duration,t));
  C.post.composer.render();drawHud(t,si,p);
  window.FRAME_STATE={t,scene:s.id,cue:TL.cues.findIndex(c=>c.start<=t&&t<c.end),camera:cp.toArray(),lookAt:aim.toArray()};
};
window.render(0);window.READY=true;
if(new URLSearchParams(location.search).has('play')){const start=performance.now();function loop(now){window.render(((now-start)/1000)%TL.duration);requestAnimationFrame(loop)}requestAnimationFrame(loop)}
