import * as THREE from 'three';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {createCharacter,clamp,smooth,ramp} from './character-v2.js';
const V=a=>new THREE.Vector3(...a),lerp=(a,b,u)=>a+(b-a)*u;
const scene=new THREE.Scene();scene.background=new THREE.Color('#ece8df');scene.fog=new THREE.Fog('#ece8df',14,35);
const camera=new THREE.PerspectiveCamera(34,innerWidth/innerHeight,.025,55);
const renderer=new THREE.WebGLRenderer({canvas:document.querySelector('#scene'),antialias:true,preserveDrawingBuffer:true});renderer.setPixelRatio(1);renderer.setSize(innerWidth,innerHeight);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.02;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
const pmrem=new THREE.PMREMGenerator(renderer),room=new RoomEnvironment();scene.environment=pmrem.fromScene(room,.04).texture;room.dispose();pmrem.dispose();scene.environmentIntensity=.4;
scene.add(new THREE.HemisphereLight('#fffaf0','#7e9895',1.9));
const key=new THREE.DirectionalLight('#fff0d9',2.9);key.position.set(-3,7,5);key.castShadow=true;key.shadow.mapSize.set(2048,2048);Object.assign(key.shadow.camera,{left:-4,right:4,top:5,bottom:-3,near:.1,far:20});key.shadow.bias=-.0002;key.shadow.normalBias=.008;scene.add(key);
const fill=new THREE.DirectionalLight('#c1e2e8',1.5);fill.position.set(3,4,-3);scene.add(fill);
const groundMaterial=new THREE.MeshStandardMaterial({color:'#ded8cb',roughness:1,transparent:true,opacity:1,depthWrite:false});
const ground=new THREE.Mesh(new THREE.PlaneGeometry(120,120),groundMaterial);ground.rotation.x=-Math.PI/2;ground.position.y=-.004;ground.receiveShadow=true;ground.renderOrder=-100;scene.add(ground);
const mat=(c,o={})=>new THREE.MeshStandardMaterial({color:c,roughness:.5,...o});
function tube(parent,pts,r,m,segments=60){const c=new THREE.CatmullRomCurve3(pts.map(p=>p.isVector3?p:V(p))),o=new THREE.Mesh(new THREE.TubeGeometry(c,segments,r,7,false),m);parent.add(o);return {o,c}}
const stage=new THREE.Group();scene.add(stage);
for(let n=1;n<=4;n++){const points=Array.from({length:121},(_,i)=>V([-.2+Math.cos(i*Math.PI/60)*n*.72,.003,Math.sin(i*Math.PI/60)*n*.72]));const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:'#98a79d',transparent:true,opacity:.19}));stage.add(line)}
const human=await createCharacter(scene);let state=human.update(13.8);const pads=human.getToePoints();
// Fine procedural microtexture only changes shading; it does not invent anatomy.
const noiseCanvas=document.createElement('canvas');noiseCanvas.width=noiseCanvas.height=512;const nc=noiseCanvas.getContext('2d'),pixels=nc.createImageData(512,512);let seed=7431;for(let i=0;i<pixels.data.length;i+=4){seed=(1664525*seed+1013904223)>>>0;const x=124+(seed>>>24)%30;pixels.data[i]=pixels.data[i+1]=pixels.data[i+2]=x;pixels.data[i+3]=255}nc.putImageData(pixels,0,0);const pores=new THREE.CanvasTexture(noiseCanvas);pores.wrapS=pores.wrapT=THREE.RepeatWrapping;pores.repeat.set(11,11);for(const m of human.footSkin){if(m.geometry.attributes.uv){m.material.bumpMap=pores;m.material.bumpScale=.0008;m.material.needsUpdate=true}}
for(const item of human.anatomy){
 const m=item.m.material;m.transparent=true;m.alphaHash=false;m.alphaTest=.015;item.m.renderOrder=1;
 m.onBeforeCompile=s=>{
  s.vertexShader='attribute float legWindow; varying float vLegWindow; varying vec3 tissueP;\n'+s.vertexShader;
  s.vertexShader=s.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvLegWindow=legWindow;tissueP=position;');
  s.fragmentShader='varying float vLegWindow; varying vec3 tissueP;\n'+s.fragmentShader;
  s.fragmentShader=s.fragmentShader.replace('#include <alphahash_fragment>','diffuseColor.a*=vLegWindow;\n#include <alphahash_fragment>');
  if(item.type==='muscle'&&!item.tendon)s.fragmentShader=s.fragmentShader.replace('#include <color_fragment>','#include <color_fragment>\ndiffuseColor.rgb*=0.92+0.08*sin(tissueP.x*1500.0+sin(tissueP.y*140.0)*0.6);');
 };
 m.customProgramCacheKey=()=> 'leg-muscle-window-v3'+item.tendon;
}

const contacts=new THREE.Group();scene.add(contacts);const contactDiscs=[];
for(const p of pads){const m=new THREE.Mesh(new THREE.CircleGeometry(.033,28),new THREE.MeshBasicMaterial({color:'#c39a45',transparent:true,opacity:0,depthWrite:false}));m.rotation.x=-Math.PI/2;m.position.set(p.x,.008,p.z);contacts.add(m);contactDiscs.push(m)}
const roots=new THREE.Group();scene.add(roots);const rootMats=[],rootItems=[];
function rootBranch(pts,r,color){const m=mat(color,{transparent:true,opacity:.85,depthWrite:false,roughness:.8});rootMats.push(m);const {o,c}=tube(roots,pts,r,m,36),a=o.geometry.attributes.position;for(let j=0;j<=36;j++){const p=c.getPointAt(j/36),f=1-.96*(j/36);for(let k=0;k<8;k++){const i=j*8+k;a.setXYZ(i,p.x+(a.getX(i)-p.x)*f,p.y+(a.getY(i)-p.y)*f,p.z+(a.getZ(i)-p.z)*f)}}o.geometry.computeVertexNormals();rootItems.push({o,start:Math.abs(pts[0][1])/.85})}
for(let i=0;i<5;i++){const p=pads[i];const x=p.x,z=p.z;rootBranch([[x,0,z],[x+.015,-.16,z+.025],[x+(i-2)*.05,-.38,z+.05],[x+(i-2)*.11,-.65,z+.10]],.013,i%2?'#a17b41':'#397f77');for(let j=0;j<4;j++){const y=-.16-j*.07,s=j%2?1:-1;rootBranch([[x+(i-2)*.025,y,z+.035],[x+s*.09,y-.13,z+.08],[x+s*(.18+j*.02),y-.23,z+.17]],.0045,'#6e937d')}}
const torque=new THREE.Group();scene.add(torque);const torqueM=mat('#b28436',{metalness:.5,roughness:.32,transparent:true});
function curvedArrow(parent,center,r,start,end,material){const g=new THREE.Group();g.position.copy(V(center));parent.add(g);const pts=Array.from({length:80},(_,j)=>[r*Math.cos(lerp(start,end,j/79)),0,r*Math.sin(lerp(start,end,j/79))]);tube(g,pts,.009,material,70);const endP=V(pts.at(-1)),d=endP.clone().sub(V(pts.at(-3))).normalize(),cone=new THREE.Mesh(new THREE.ConeGeometry(.035,.105,20),material);cone.position.copy(endP);cone.quaternion.setFromUnitVectors(V([0,1,0]),d);g.add(cone);return g}
curvedArrow(torque,[-.88,.021,.24],.52,-.45,4.50,torqueM);curvedArrow(torque,[-.88,.021,.24],.61,3.9,5.7,torqueM);
const legSpiral=new THREE.Group();scene.add(legSpiral);const spiralM=mat('#5e9a8c',{metalness:.1,transparent:true,opacity:.6,depthWrite:false});
const knee=V(state.knee),hip=V(state.hip);
// Fine surface guides accompany the actual muscle deformation, rather than
// replacing it with a large corkscrew around the whole leg.
for(const [bottom,top,r] of [[V(state.ankle).add(V([0,.30,0])),knee,.12],[knee,hip.clone().lerp(knee,.23),.17]]){
 const axis=top.clone().sub(bottom).normalize(),side=V([0,0,1]).cross(axis).normalize(),front=axis.clone().cross(side);
 for(let k=0;k<2;k++){
  const pts=[];for(let j=0;j<=64;j++){const u=j/64,a=-u*Math.PI*.9+k*Math.PI+.6,rad=r*(.70+.30*Math.sin(u*Math.PI));pts.push(bottom.clone().lerp(top,u).addScaledVector(side,Math.cos(a)*rad).addScaledVector(front,Math.sin(a)*rad))}
  tube(legSpiral,pts,.0032,spiralM,64);
 }
}
const forceM=mat('#be9349',{transparent:true,opacity:0,metalness:.2});const forcePath=[pads[0],V([-.88,.35,.06]),knee,hip,V([.05,2.38,.2]),V([.36,2.95,.18]),V([1.1,2.65,.5])];const {o:force,c:forceCurve}=tube(scene,forcePath,.012,forceM,100);const pulse=new THREE.Mesh(new THREE.SphereGeometry(.027,16,12),mat('#d1ac5d'));scene.add(pulse);

const hud=document.querySelector('#hud'),ctx=hud.getContext('2d');
const color={ink:'#23484b',muted:'#74827a',gold:'#9e7838',teal:'#247e76'};
function text(s,x,y,size=22,c=color.ink,weight=400,align='left'){ctx.fillStyle=c;ctx.font=`${weight} ${size}px "Noto Sans SC",sans-serif`;ctx.textAlign=align;ctx.fillText(s,x,y)}
function rule(x,y,w,c='#bac1b4'){ctx.strokeStyle=c;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+w,y);ctx.stroke()}
function project(p){const q=(p.isVector3?p.clone():V(p)).project(camera);return [(q.x*.5+.5)*1920,(-q.y*.5+.5)*1080]}
function label(p,s,x,y,c=color.ink){const q=project(p);ctx.strokeStyle=c;ctx.lineWidth=1.2;ctx.globalAlpha=.75;ctx.beginPath();ctx.moveTo(...q);ctx.lineTo(x-24,y-8);ctx.lineTo(x-8,y-8);ctx.stroke();ctx.beginPath();ctx.arc(...q,3.5,0,Math.PI*2);ctx.fillStyle=c;ctx.fill();ctx.globalAlpha=1;ctx.font='400 21px "Noto Sans SC"';ctx.fillStyle='#ece8dff2';ctx.fillRect(x-6,y-28,ctx.measureText(s).width+16,39);text(s,x,y,21,c)}
const chapters=[['01','根 · 缠丝','ROOTED IN SPIRAL',0,6],['02','把视线落到脚下','FOLLOW THE ROOT',6,9],['03','脚趾屈曲 · 抓稳地面','CURL, PRESS, HOLD',9,14],['04','抓稳之后 · 如树扎根','A METAPHOR FOR GRIP',14,19],['05','足底不移 · 腿部外旋','ROOTED FOOT, TURNING LEG',19,24],['06','肌群左缠 · 细微拉紧','WIND, TENSION, REBOUND',24,30.5],['07','足下有根 · 周身相随','ONE CONTINUOUS THREAD',30.5,36]];
function drawHud(t){hud.width=innerWidth;hud.height=innerHeight;ctx.setTransform(innerWidth/1920,0,0,innerHeight/1080,0,0);ctx.fillStyle='#ece8dff5';ctx.fillRect(0,0,1920,130);ctx.fillRect(0,946,1920,134);text('缠 丝 劲',75,76,27,color.ink,500);text('ROOTED MOTION',75,108,12,color.muted,500);text('动作 · 足底 · 螺旋',1845,77,18,color.muted,400,'right');rule(75,130,1770);const ch=chapters.find(c=>t>=c[3]&&t<c[4])||chapters.at(-1);ctx.globalAlpha=ramp(t,ch[3],ch[3]+.5);text(ch[0],76,227,18,color.gold,500);text(ch[1],76,285,36,color.ink,500);text(ch[2],78,325,13,color.muted,500);rule(78,356,57,color.gold);ctx.globalAlpha=1;
 if(t<6){text('一条从足底开始的螺旋。',78,431,25);text('缓移重心，松胯，舒展双臂。',78,477,20,color.muted);label([-.88,.04,.35],'承重脚',1440,786,color.gold)}
 else if(t<9){text('镜头沿着承重腿，进入足部。',78,423,22,color.muted)}
 else if(t<14){text('趾节逐步弯曲，趾腹向后收抓。',78,423,21);text('足跟保持接地，先抓稳，再生根。',78,468,20,color.muted);label(human.getToePoints()[0],'拇趾缓缓屈曲',1430,431,color.gold);label(human.getToePoints()[3],'四趾依次收抓',1430,605,color.ink);text('抓地进度',78,634,18,color.muted);for(let i=0;i<5;i++){const u=ramp(t,9.4+i*.12,12.5+i*.12);ctx.fillStyle=u>.95?color.gold:'#bdc4b7';ctx.beginPath();ctx.arc(95+i*51,684,9+3*u,0,Math.PI*2);ctx.fill();text(String(i+1),95+i*51,725,13,color.muted,400,'center')}}
 else if(t<19){text('脚趾抓稳之后，根须才向下展开。',78,423,21);text('根须只比喻抓地感，不是身体结构。',78,468,19,color.muted);label(human.getToePoints()[2],'脚趾已抓稳',1420,413,color.gold);label([-.85,-.37,.48],'扎根感 · 视觉比喻',1420,765,color.teal)}
 else if(t<24){text('脚底守住原位，小腿与大腿轻轻外旋。',78,423,20);text('由足向上，旋转逐渐传到腿部。',78,469,19,color.muted);label(human.getToePoints()[2],'五趾持续抓地',1450,815,color.gold);label(V(state.knee).lerp(V(state.ankle),.5),'小腿 · 细微外旋',1450,592,color.teal);label(V(state.hip).lerp(V(state.knee),.55),'大腿 · 随之转动',1450,410,color.gold)}
 else if(t<30.5){text('外旋加载时，肌群缓缓向左缠紧。',78,423,21);text('微小收紧、回弹，再次拉紧。',78,468,20,color.teal);text('左缠观察方向：从髋向足俯视。',78,512,17,color.muted);label(V(state.hip).lerp(V(state.knee),.50),'大腿肌群 · 左缠拉紧',1450,412);label(V(state.knee).lerp(V(state.ankle),.5),'小腿肌群 · 连续传导',1450,610,color.teal);label(human.getToePoints()[2],'足底锚定 · 持续抓地',1450,815,color.gold)}
 else{text('抓地',78,446,43);text('扎根',78,514,43);text('缠转',78,582,43);text('从足至腿，周身相随。',78,656,23,color.gold)}
 rule(75,946,1770);text('太极劲意为艺术化示意；解剖网格用于展示结构，并非肌力仿真。',75,984,15,color.muted);text('Z-Anatomy · CC BY-SA 4.0 / BodyParts3D © DBCLS · CC BY-SA 2.1 JP',1845,984,13,color.muted,400,'right');text('MakeHuman / Innerscene / Grab3D · CC0',1845,1013,12,color.muted,400,'right');ctx.fillStyle='#c2c9ba';ctx.fillRect(75,1041,1770,2);ctx.fillStyle=color.teal;ctx.fillRect(75,1041,1770*t/36,2)}
function cameraAt(t){const cams=[
 [0,[5,3.6,8.7],[-.15,1.77,0],34],[6,[4.8,3.5,8.4],[-.15,1.75,0],34],
 [9,[.12,.65,1.90],[-.88,.10,.25],33],[14,[-.10,.54,1.89],[-.88,.09,.25],33],
 [17,[.20,.82,2.28],[-.88,-.12,.25],35],[19,[.28,1.00,2.57],[-.88,-.04,.25],35],
 [21.6,[1.90,2.12,5.85],[-.64,.95,.10],34],[24,[1.90,2.12,5.85],[-.64,.95,.10],34],
 [28.8,[1.45,2.02,5.65],[-.64,.98,.10],34],[30.5,[1.90,2.2,5.55],[-.64,1.10,.10],34],
 [33.7,[4.5,3.5,8.1],[-.1,1.72,0],34],[36,[4.8,3.6,8.5],[-.1,1.75,0],34]];
 let i=cams.findIndex((c,j)=>j<cams.length-1&&t>=c[0]&&t<cams[j+1][0]);if(i<0)i=cams.length-2;const a=cams[i],b=cams[i+1],u=smooth((t-a[0])/(b[0]-a[0]));camera.position.copy(V(a[1]).lerp(V(b[1]),u));camera.lookAt(V(a[2]).lerp(V(b[2]),u));camera.fov=lerp(a[3],b[3],u);camera.updateProjectionMatrix()}
function render(t){
 t=Math.max(0,Math.min(t,35.9999));state=human.update(t);cameraAt(t);
 const grip=ramp(t,9.5,13),toePoints=human.getToePoints();
 for(let i=0;i<5;i++){const d=contactDiscs[i];d.position.set(toePoints[i].x,.008,toePoints[i].z);d.material.opacity=.28*grip*(1-ramp(t,30.5,33))}
 const rootGrowth=ramp(t,14.3,18);roots.visible=rootGrowth>0;
 for(const {o,start} of rootItems){const grow=clamp((rootGrowth-start)/(1-start));o.geometry.setDrawRange(0,Math.floor(grow*36)*42)}
 for(const m of rootMats)m.opacity=.75*(1-ramp(t,30,33)*.65);
 groundMaterial.opacity=clamp(1-.86*ramp(t,14.5,16.3)+.8*ramp(t,30.5,33.7));
 torque.visible=t>=19.4&&t<32;torqueM.opacity=.8*ramp(t,19.4,20.5)*(1-ramp(t,30.5,32));
 legSpiral.visible=t>=23&&t<32;spiralM.opacity=.5*ramp(t,23,24)*(1-ramp(t,30.5,32));
 force.visible=t>30.5;forceM.opacity=ramp(t,30.5,32.5)*.8;pulse.visible=t>30.5;pulse.position.copy(forceCurve.getPoint((((t-30.5)*.22)%1+1)%1));
 renderer.render(scene,camera);drawHud(t);
 window.V2_STATE={...state,rootGrowth,rootsVisible:roots.visible,rootDrawCounts:rootItems.map(({o})=>o.geometry.drawRange.count),inventory:human.inventory,camera:camera.position.toArray()};
}
await document.fonts.ready;await Promise.all([400,500].map(w=>document.fonts.load(`${w} 24px "Noto Sans SC"`)));window.render=async t=>render(t);window.V2_CHARACTER=human;render(0);window.READY=true;
