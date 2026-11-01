import {THREE,scene,renderer,camera,root,core,motorGroup,motor,head,gears,wings,shells,connectors,
  M,ground,grid,axes,key,hud,ctx,poseModel,resize,mesh,box,ball,rod,ring,bolt,tube} from './main.js';
import {stateAt,smooth,pulse,clamp} from './model.js';

// The edit cuts between deliberately different viewpoints. Interpolation is local
// to one shot; it never sweeps slowly through every camera position in the film.
const shots=[
 {start:0,end:3,id:'01',en:'AWAKENING',cn:'传感核心',p:[2.6,1.1,-6],q:[1.7,.9,-5.4],target:[0,.1,-1.55],fov:30},
 {start:3,end:5.5,id:'02',en:'FRONTAL SYMMETRY',cn:'正面 · 四翼联动',p:[0,6,-25],q:[0,5,-23],target:[0,.15,-.1],fov:35},
 {start:5.5,end:8,id:'03',en:'SIDE ELEVATION',cn:'侧面 · 结构轮廓',p:[22,7.3,3],q:[20,6.7,1.5],target:[0,0,.2],fov:35},
 {start:8,end:10.5,id:'04',en:'PLAN VIEW',cn:'俯视 · 翼脉骨架',p:[0,25,.02],q:[0,23,.02],target:[0,0,0],up:[0,0,-1],fov:38},
 {start:10.5,end:13,id:'05',en:'CARAPACE / RELEASE',cn:'背甲释放',p:[4.7,4.8,7.8],q:[4.3,4.4,7.0],target:[0,1,0],fov:35},
 {start:13,end:16,id:'06',en:'MOTOR / CUTAWAY',cn:'抽出电机 · 剖视转子',p:[4.2,1.15,1.15],q:[3.7,1.0,.85],target:[1.05,-.02,.05],fov:30},
 {start:16,end:19,id:'07',en:'TRANSMISSION',cn:'齿轮传动 · 微距',p:[.9,3.1,1.4],q:[.5,2.65,1.25],target:[0,.38,.05],fov:30},
 {start:19,end:22,id:'08',en:'CRANK → ROCKER',cn:'连杆驱动 · 翼根特写',p:[3.2,1.75,-3.0],q:[2.6,1.5,-2.8],target:[.53,.14,-.75],fov:31},
 {start:22,end:26,id:'09',en:'ANATOMY OF FLIGHT',cn:'分层拆解 · 结构展开',p:[14,5.5,23],q:[-12,7,22],target:[0,0,.2],fov:38},
 {start:26,end:29,id:'10',en:'EVERY PART / HOME',cn:'部件归位 · 重新锁合',p:[-10,12,-18],q:[-6,10,-17],target:[0,.3,.1],fov:36},
 {start:29,end:32,id:'11',en:'AURELIA B–04',cn:'机械蝴蝶',p:[9,11,-24],q:[7,10,-22],target:[0,1,-.3],fov:37}
];
const sky=new THREE.Color('#0b141a');scene.background=sky;scene.fog=new THREE.Fog(sky,30,90);
ground.material.color.set('#030709');ground.material.roughness=1;ground.material.metalness=0;ground.material.envMapIntensity=.08;
grid.visible=false;axes.visible=false;
renderer.toneMappingExposure=.88;renderer.localClippingEnabled=true;
key.intensity=3.1;key.color.set('#ffe3ba');
scene.traverse(o=>{if(o.isHemisphereLight)o.intensity=.65;});
function area(x,y,z,power,color){const l=new THREE.DirectionalLight(color,power);l.position.set(x,y,z);scene.add(l);return l;}
const rim=area(-9,4,7,3.5,'#42d7ed'),warm=area(7,3,-8,2.0,'#ff874c');
M.glass.color.set('#2b8d80');M.glass.opacity=.72;M.pale.color.set('#79ad95');M.pale.opacity=.72;
M.brass.color.set('#ba975c');M.ivory.color.set('#c6c9c1');

// Keep actual internal geometry behind the housing. Only the housing material is
// clipped during the cutaway, so the opening reveals a rotor instead of empty air.
const motorShells=motorGroup.children.filter(o=>o.isMesh);
const copper=new THREE.MeshStandardMaterial({color:'#b97038',metalness:.88,roughness:.25});
const graphite=new THREE.MeshStandardMaterial({color:'#18262d',metalness:.75,roughness:.28});
const rotor=new THREE.Group();motorGroup.add(rotor);
const shaft=mesh(new THREE.CylinderGeometry(.055,.055,1.66,20),M.silver,rotor);shaft.rotation.x=Math.PI/2;
for(let i=0;i<12;i++){const a=i/12*Math.PI*2;
  const bar=box(rotor,Math.cos(a)*.13,Math.sin(a)*.13,.05,.055,.055,1.08,i%2?M.silver:copper);bar.rotation.z=a;
}
for(const z of [-.47,.52]){const d=mesh(new THREE.CylinderGeometry(.19,.19,.075,24),copper,rotor);d.rotation.x=Math.PI/2;d.position.z=z;}
const coils=new THREE.Group();motorGroup.add(coils);
for(const side of [-1,1])for(let j=0;j<3;j++){
  const coil=mesh(new THREE.TorusGeometry(.085,.026,6,16),copper,coils);
  coil.position.set(side*.195,0,-.31+j*.32);coil.rotation.y=Math.PI/2;
}
const cutPlane=new THREE.Plane(new THREE.Vector3(-1,0,0),0);
for(const part of motorShells){part.material=part.material.clone();part.material.clippingPlanes=[];}

// A gear carrier, electronics tray, and two battery cells separate on their own
// axes during the anatomical shot, leaving readable gaps between each layer.
const transmission=new THREE.Group();core.add(transmission);
for(const {g} of gears)transmission.add(g);
box(transmission,0,.31,.08,.77,.045,1.30,graphite);
for(const x of [-.28,.28])for(const z of [-.48,.65])bolt(transmission,x,.35,z,.045);
const electronics=new THREE.Group();root.add(electronics);electronics.position.y=-.29;
const boardMat=new THREE.MeshStandardMaterial({color:'#164940',metalness:.35,roughness:.4});
box(electronics,0,0,.0,.76,.065,1.35,boardMat);
for(let i=0;i<7;i++){
  const z=-.5+i*.16;box(electronics,.16,.06,z,.24,.06,.09,i%2?graphite:M.silver);
  box(electronics,-.20,.045,z,.13,.035,.055,M.brass);
}
for(const x of [-.31,.31])for(const z of [-.55,.55])bolt(electronics,x,.055,z,.035);
const battery=new THREE.Group();root.add(battery);battery.position.y=-.52;
for(const x of [-.19,.19]){
  const cell=mesh(new THREE.CylinderGeometry(.14,.14,1.25,24),graphite,battery);cell.rotation.x=Math.PI/2;cell.position.x=x;
  for(const z of [-.60,.60]){const cap=mesh(new THREE.CylinderGeometry(.143,.143,.065,20),copper,battery);cap.rotation.x=Math.PI/2;cap.position.set(x,0,z);}
  box(battery,x,.139,0,.08,.012,.66,M.orange);
}
const bolts=[];
for(const x of [-.43,.43])for(const z of [-.78,.66]){
  const g=new THREE.Group();g.position.set(x,.2,z);root.add(g);
  const body=rod(g,[0,0,0],[0,-.24,0],.027,M.silver);bolt(g,0,.015,0,.061);
  for(let k=0;k<6;k++)ring(g,0,-.025-k*.032,0,.028,M.dark,.006);
  bolts.push({g,x,z});
}

const white='#e0e9e7',muted='#92a5aa',accent='#f28a4b';
function text(s,x,y,size=16,color=white,weight=400,mono=false){ctx.font=`${weight} ${size}px ${mono?'"SFMono-Regular",Consolas,monospace':'"Helvetica Neue",Arial,"PingFang SC",sans-serif'}`;ctx.fillStyle=color;ctx.fillText(s,x,y);}
function ln(a,b,color='#829b9a',width=1){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();}
function project(obj,p){return obj.localToWorld(new THREE.Vector3(...p)).project(camera);}
function callout(title,detail,obj,p,x,y){const v=project(obj,p);const a=[(v.x+1)*960,(1-v.y)*540];
  if(Math.abs(v.x)>1||Math.abs(v.y)>1||v.z>1)return;
  ctx.fillStyle='rgba(8,15,19,.72)';ctx.fillRect(x-9,y-48,279,76);
  ln(a,[x-20,y-10]);ln([x-20,y-10],[x+255,y-10]);ctx.fillStyle=accent;ctx.beginPath();ctx.arc(...a,3,0,7);ctx.fill();text(title,x,y-25,15,white,500,true);text(detail,x,y+14,13,muted);
}
function hudAt(t,s,shot){ctx.setTransform(hud.width/1920,0,0,hud.height/1080,0,0);ctx.clearRect(0,0,1920,1080);
  // A quiet film frame, with no simulator console obscuring the machinery.
  ctx.fillStyle='#080f13';ctx.fillRect(0,0,1920,60);ctx.fillRect(0,1020,1920,60);
  text('AURELIA / MECHANICAL LEPIDOPTERA',70,39,12,muted,500,true);
  text(`${shot.id} / 11`,1745,39,12,accent,500,true);
  const grad=ctx.createLinearGradient(0,770,0,1010);grad.addColorStop(0,'rgba(8,15,19,0)');grad.addColorStop(1,'rgba(8,15,19,.85)');ctx.fillStyle=grad;ctx.fillRect(0,770,1920,250);
  ctx.fillStyle=accent;ctx.fillRect(73,868,35,3);
  text(shot.en,72,913,34,white,500);text(shot.cn,74,947,18,muted,400);
  text(`DRIVE ${s.rpm.toFixed(0)} RPM  /  WING ${s.angle.toFixed(1)}°`,1400,949,12,muted,400,true);
  const u=clamp((t-shot.start)/(shot.end-shot.start));ln([73,985],[1847,985],'#24353c');ln([73,985],[73+1774*u,985],accent,2);
  text('KINETIC DESIGN STUDY  /  2026',72,1055,10,muted,400,true);
  text("MUSIC: NEON / SCOTT BUCKLEY / CC-BY 4.0 / scottbuckley.com.au",1120,1055,10,muted,400,true);
  root.updateMatrixWorld(true);
  if(shot.id==='05')callout('REMOVABLE CARAPACE','两片背甲独立抬升',shells[1].g,[0,.15,0],1350,278);
  if(shot.id==='06'){
    callout('ROTOR / COPPER WINDINGS','转子与铜线圈 · 外壳剖视',motorGroup,[.15,0,0],1250,300);
    callout('OUTPUT SHAFT','输出轴 → 曲柄连杆',motorGroup,[0,0,-.76],1200,640);
  }
  if(shot.id==='07')callout('MESHED GEAR PAIR','反向联动的齿轮组',transmission,[0,.43,.27],1280,240);
  if(shot.id==='08')callout('WING ROOT / ROCKER','连杆端点始终固定在摇臂上',root,[.66,.40,-.75],1270,270);
  if(shot.id==='09'){
    callout('01 / CARAPACE','背甲层',shells[1].g,[0,.1,0],1400,250);
    callout('02 / TRANSMISSION','传动层',transmission,[0,.4,0],1420,415);
    callout('03 / ELECTRONICS','控制板',electronics,[0,.05,0],1420,585);
    callout('04 / POWER','电源层',battery,[.16,0,0],1380,735);
  }
  if(t<1.2){const a=1-smooth(0,1.2,t);ctx.fillStyle=`rgba(3,8,12,${a})`;ctx.fillRect(0,60,1920,960);}
  if(t>31.2){ctx.fillStyle=`rgba(3,8,12,${smooth(31.2,32,t)})`;ctx.fillRect(0,60,1920,960);}
}

function render(t){resize();const shot=shots.find(k=>t>=k.start&&t<k.end)??shots.at(-1),u=smooth(shot.start,shot.end,t);
  const explode=pulse(t,22,23.8,26,28.6),shell=Math.max(pulse(t,10.5,12.3,26.5,28.5),explode);
  const s=stateAt(t,{shell,explode});s.fly=smooth(29.7,31.5,t);poseModel(s);
  // Lift and split the inspection layers while retaining their own dimensions.
  motorGroup.position.y=-explode*.85;transmission.position.y=explode*.95;
  electronics.position.y=-.29-explode*1.75;battery.position.y=-.52-explode*2.95;
  for(const sh of shells)sh.g.position.copy(sh.base).addScaledVector(sh.dir,shell*1.5);
  const loosen=pulse(t,10.5,11.5,27.8,28.8);
  for(const b of bolts){b.g.position.set(b.x,.2+loosen*1.2+explode*.7,b.z);b.g.rotation.y=loosen*6*Math.PI;}
  rotor.rotation.z=s.phase*3;
  const cutaway=shot.id==='06';
  for(const part of motorShells){part.material.clippingPlanes=cutaway?[cutPlane]:[];}
  // The support plate would cover the motor from above, so the cutaway is viewed
  // from its open right side, with a small real separation from the chassis.
  if(cutaway)motorGroup.position.x=1.05;
  else motorGroup.position.x=0;
  root.updateMatrixWorld(true);
  cutPlane.setFromNormalAndCoplanarPoint(new THREE.Vector3(-1,0,0).applyQuaternion(root.quaternion),motorGroup.getWorldPosition(new THREE.Vector3()));
  // Park the complete wing modules outside the open inspection volume. These
  // are real disassembly translations; rods and their pins move with each wing.
  const park=pulse(t,12.3,13,18.5,19);
  for(const w of wings){w.g.position.x+=w.side*park*5;w.g.position.y+=park;}
  for(const c of connectors){c.link.position.x+=c.side*park*5;c.link.position.y+=park;c.pin.position.x+=c.side*park*5;c.pin.position.y+=park;}
  // Bring true bright edge lights across each material without changing models.
  rim.intensity=shot.id==='01'?4.8:3.5;warm.intensity=cutaway?3.0:2.0;
  const p=shot.p.map((v,i)=>v+(shot.q[i]-v)*u);
  camera.up.set(...(shot.up??[0,1,0]));camera.position.set(...p);camera.fov=shot.fov;camera.updateProjectionMatrix();camera.lookAt(...shot.target);
  renderer.render(scene,camera);hudAt(t,s,shot);
  window.currentState={...s,shot:shot.id,view:shot.en,cutaway};
  window.cinematicAudit={shot:shot.id,cutaway,camera:p,target:shot.target,
    layers:{shell:shells[1].g.position.toArray(),gear:transmission.position.toArray(),motor:motorGroup.position.toArray(),board:electronics.position.toArray(),battery:battery.position.toArray()}};
  return window.currentState;
}
window.render=render;window.cinematicShots=shots;renderer.compile(scene,camera);render(0);window.READY=true;
