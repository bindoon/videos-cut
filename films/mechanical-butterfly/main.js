import * as THREE from 'three';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {P,clamp,smooth,stateAt,linkage} from './model.js';

const canvas=document.querySelector('#scene'),hud=document.querySelector('#hud'),ctx=hud.getContext('2d');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,preserveDrawingBuffer:true});
renderer.setPixelRatio(1);renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.15;
const scene=new THREE.Scene();scene.background=new THREE.Color('#f3f0e8');
scene.fog=new THREE.Fog('#f3f0e8',38,90);
const camera=new THREE.PerspectiveCamera(36,16/9,.1,120);
const pmrem=new THREE.PMREMGenerator(renderer),room=new RoomEnvironment();
scene.environment=pmrem.fromScene(room,.035).texture;room.dispose();pmrem.dispose();
scene.add(new THREE.HemisphereLight(0xfff9e9,0x65706d,2));
function light(x,y,z,power,color){const l=new THREE.DirectionalLight(color,power);l.position.set(x,y,z);scene.add(l);return l;}
const key=light(-8,14,-6,4.5,0xfff0d8);key.castShadow=true;key.shadow.mapSize.set(2048,2048);
Object.assign(key.shadow.camera,{left:-15,right:15,top:15,bottom:-15,near:.5,far:50});
key.shadow.bias=-.0003;key.shadow.normalBias=.035;light(9,6,3,2.5,0xbde7e3);light(0,4,-12,2,0xffffff);
const material=(color,metalness=.6,roughness=.3,extra={})=>new THREE.MeshStandardMaterial({color,metalness,roughness,...extra});
const M={ivory:material('#deddd3',.5,.28),dark:material('#263934',.8,.25),black:material('#172320',.55,.38),
  brass:material('#b58d4d',.85,.24),edge:material('#37594d',.8,.25),silver:material('#a3b4ab',.9,.2),
  orange:material('#f06433',.45,.24),teal:material('#3d9684',.65,.3),
  glass:material('#4b8d72',.15,.32,{transparent:true,opacity:.48,side:THREE.DoubleSide,depthWrite:false}),
  pale:material('#b4c8aa',.20,.34,{transparent:true,opacity:.66,side:THREE.DoubleSide,depthWrite:false}),
  glow:material('#a2f7d2',.2,.2,{emissive:'#5deab3',emissiveIntensity:1.6})};
const ground=new THREE.Mesh(new THREE.PlaneGeometry(200,200),material('#eeeae1',.05,.94));
ground.rotation.x=-Math.PI/2;ground.position.y=-4.2;ground.receiveShadow=true;scene.add(ground);
const grid=new THREE.GridHelper(120,120,0xd8d7cb,0xe6e2d8);grid.position.y=-4.195;grid.material.transparent=true;grid.material.opacity=.35;scene.add(grid);
const root=new THREE.Group();scene.add(root);
const sphereGeo=new THREE.SphereGeometry(1,12,8),cylGeo=new THREE.CylinderGeometry(1,1,1,12),boxGeo=new THREE.BoxGeometry(1,1,1);
let meshCount=0;
function mesh(geo,mat,parent=root){const m=new THREE.Mesh(geo,mat);m.castShadow=true;m.receiveShadow=true;parent.add(m);meshCount++;return m;}
function box(parent,x,y,z,sx,sy,sz,mat){const m=mesh(boxGeo,mat,parent);m.position.set(x,y,z);m.scale.set(sx,sy,sz);return m;}
function ball(parent,x,y,z,r,mat,scale=[1,1,1]){const m=mesh(sphereGeo,mat,parent);m.position.set(x,y,z);m.scale.set(r*scale[0],r*scale[1],r*scale[2]);return m;}
function rod(parent,a,b,r,mat){const m=mesh(cylGeo,mat,parent);updateRod(m,a,b,r);return m;}
const up=new THREE.Vector3(0,1,0);
function updateRod(m,a,b,r){const av=new THREE.Vector3(...a),bv=new THREE.Vector3(...b),d=bv.clone().sub(av);m.position.copy(av.add(bv).multiplyScalar(.5));m.scale.set(r,d.length(),r);m.quaternion.setFromUnitVectors(up,d.normalize());}
function tube(parent,points,r,mat){const curve=new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p)));return mesh(new THREE.TubeGeometry(curve,Math.max(12,points.length*6),r,6,false),mat,parent);}
function bolt(parent,x,y,z,r=.065){const b=mesh(new THREE.CylinderGeometry(r,r,.035,6),M.silver,parent);b.position.set(x,y,z);box(parent,x,y+.021,z,r*.8,.008,r*.19,M.black);return b;}
function ring(parent,x,y,z,r,mat,thick=.05){const m=mesh(new THREE.TorusGeometry(r,thick,8,32),mat,parent);m.rotation.x=Math.PI/2;m.position.set(x,y,z);return m;}

// Thorax: a structural frame that remains mounted when the shell is lifted.
const core=new THREE.Group();root.add(core);
box(core,0,-.08,0,1.05,.25,2.05,M.dark);box(core,0,.14,0,.7,.24,1.75,M.black);
for(const side of [-1,1]){
  rod(core,[side*.48,0,-1.05],[side*.48,0,1.02],.085,M.brass);
  for(const z of [-.75,.35]){rod(core,[-.8,.08,z],[.8,.08,z],.10,M.silver);ring(core,side*.66,.15,z,.15,M.orange,.04);}
  for(const z of [-.95,0,.85])bolt(core,side*.39,.29,z);
  for(let i=0;i<5;i++)box(core,side*.56,-.12,-.55+i*.24,.07,.32,.045,M.silver);
}
const motorGroup=new THREE.Group();core.add(motorGroup);
const motor=mesh(new THREE.CylinderGeometry(.29,.29,1.35,24),M.dark,motorGroup);motor.rotation.x=Math.PI/2;motor.position.set(0,0,.05);
for(const z of [-.66,.72]){const cap=mesh(new THREE.CylinderGeometry(.30,.30,.08,24),M.brass,motorGroup);cap.rotation.x=Math.PI/2;cap.position.z=z;}
for(let i=0;i<9;i++){const a=i/9*Math.PI*2;rod(motorGroup,[.295*Math.cos(a),.295*Math.sin(a),-.5],[.295*Math.cos(a),.295*Math.sin(a),.5],.018,M.silver);}

// Decorative exposed meshed spur gears; the driven pair uses opposite phase.
const gears=[];
function gear(x,y,z,r,teeth,ratio,offset=0){const g=new THREE.Group();g.position.set(x,y,z);core.add(g);
  const hub=mesh(new THREE.CylinderGeometry(r*.87,r*.87,.09,teeth),M.brass,g);ring(g,0,.055,0,r*.65,M.dark,.032);
  for(let i=0;i<teeth;i++){const a=i/teeth*2*Math.PI;const m=box(g,r*Math.cos(a),0,r*Math.sin(a),r*.23,.12,r*.15,M.brass);m.rotation.y=-a;}
  for(let i=0;i<5;i++){const a=i/5*2*Math.PI;box(g,r*.44*Math.cos(a),.065,r*.44*Math.sin(a),r*.18,.025,r*.15,M.dark);}
  bolt(g,0,.10,0,r*.22);gears.push({g,ratio,offset});return g;}
gear(0,.37,.0,.27,20,1);gear(0,.37,.54,.27,20,-1,Math.PI/20);gear(0,.37,-.40,.13,10,-2);

const shells=[];
function shell(parent,pos,scale,dir){const g=new THREE.Group();g.position.set(...pos);parent.add(g);
  const m=ball(g,0,0,0,1,M.ivory,scale);m.geometry=new THREE.SphereGeometry(1,28,14,0,Math.PI*2,0,Math.PI*.64);
  box(g,0,scale[1]*.97,0,.09,.017,scale[2]*1.12,M.orange);
  for(const side of [-1,1])for(const z of [-.45,.45])bolt(g,side*scale[0]*.62,scale[1]*.73,z*scale[2]);
  shells.push({g,base:new THREE.Vector3(...pos),dir:new THREE.Vector3(...dir)});return g;
}
shell(root,[0,.32,-.65],[.72,.30,.65],[0,1.7,-.1]);shell(root,[0,.32,.53],[.67,.29,.59],[0,1.9,.2]);

// Segmented abdomen, each with an independent explosion vector.
const segments=[];
for(let i=0;i<7;i++){const g=new THREE.Group();const z=1.18+i*.30;g.position.set(0,-.04,z);root.add(g);
  const width=.45*(1-i*.085);ball(g,0,0,0,1,i%2?M.dark:M.ivory,[width,.23-i*.014,.23]);
  ring(g,0,.06,0,width*.57,M.brass,.026);box(g,0,.22-i*.014,0,.065,.025,.25,M.orange);
  for(const side of [-1,1])bolt(g,side*width*.65,.10,0,.045);
  segments.push({g,z,i});}
rod(root,[0,0,1],[0,0,3.25],.075,M.dark);
ball(root,0,-.02,3.30,.12,M.brass,[.6,.6,1.8]);

// Sensor head and slender antennae.
const head=new THREE.Group();head.position.set(0,.04,-1.50);root.add(head);
ball(head,0,0,0,1,M.dark,[.44,.34,.43]);
for(const side of [-1,1]){
  ball(head,side*.30,.10,-.24,.19,M.brass);ball(head,side*.33,.12,-.34,.13,M.glow,[1,1,.45]);
  tube(head,[[side*.23,.2,-.23],[side*.48,.65,-.8],[side*.77,.84,-1.45],[side*.91,.64,-1.68]],.026,M.dark);
  ball(head,side*.91,.64,-1.68,.072,M.orange);
}
box(head,0,.23,-.08,.21,.07,.14,M.ivory);

// Six folded landing feet, distinct from the four wing actuators.
const legs=[];
for(const side of [-1,1])for(let i=0;i<3;i++){
  const g=new THREE.Group();root.add(g);const z=-.65+i*.64;
  const points=[[side*.40,-.10,z],[side*(.8+i*.06),-.52,z+.18],[side*(1.05+i*.07),-1.22,z+.65],[side*(1.25+i*.09),-1.5,z+.5]];
  for(let j=0;j<3;j++)rod(g,points[j],points[j+1],j===0?.055:.032,j===0?M.brass:M.dark);
  for(const p of points.slice(0,3))ball(g,...p,.077,M.silver);
  legs.push({g,side});
}

// Wings are local X/Z shapes. Mirror the entire local frame for the left pair.
const wings=[],connectors=[],cranks=[];
function makeOutline(type){const s=new THREE.Shape();s.moveTo(0,0);
  if(type==='front'){
    s.bezierCurveTo(1.3,-.65,3.1,-3.35,4.5,-3.65);
    s.bezierCurveTo(5.5,-4.1,6.5,-3.65,6.55,-3.0);
    s.bezierCurveTo(6.5,-1.7,5.25,-.75,4.0,-.12);
    s.bezierCurveTo(2.9,.58,1.35,1.05,0,0);
  }else{
    s.bezierCurveTo(1.1,-.18,2.7,-.4,4.25,.0);
    s.bezierCurveTo(5.1,.38,5.0,1.50,4.25,2.20);
    s.bezierCurveTo(3.95,2.55,3.2,2.57,3.05,3.02);
    s.bezierCurveTo(2.85,3.7,2.65,3.65,2.58,2.90);
    s.bezierCurveTo(1.35,3.0,.70,1.45,0,0);
  }return s;}
const frontRibs=[[[0,0],[1.5,-1],[3.5,-2.9],[5.9,-3.5]],[[0,0],[2,-.9],[4,-1.9],[6.48,-2.7]],[[0,0],[1.9,-.20],[4,-.75],[5.8,-1.35]],[[0,0],[1.3,.23],[2.8,.17],[4.1,-.15]]];
const backRibs=[[[0,0],[1.2,.3],[3,.35],[4.8,.65]],[[0,0],[1.2,.8],[3,1.2],[4.25,2.2]],[[0,0],[.8,.9],[2,2.2],[2.75,3.35]],[[0,0],[.7,.8],[1.1,1.8],[1.7,2.6]]];
function wing(side,type){const g=new THREE.Group(),z=type==='front'?-.75:.35;g.position.set(side*P.hingeX,P.hingeY,z);g.scale.x=side;root.add(g);
  const shape=makeOutline(type),geom=new THREE.ShapeGeometry(shape,30);geom.rotateX(Math.PI/2);
  const membrane=mesh(geom,type==='front'?M.glass:M.pale,g);membrane.castShadow=false;
  const outline=shape.getPoints(60).map(v=>[v.x,0,v.y]);tube(g,outline,.045,M.edge);
  const ribs=type==='front'?frontRibs:backRibs;
  for(const rib of ribs)tube(g,rib.map(([x,z])=>[x,.035,z]),.032,M.brass);
  // Branch veins connect the spars, giving the membrane a structural lattice.
  for(let k=0;k<3;k++)for(let n=1;n<5;n++){
    const u=n/5;const c1=new THREE.CatmullRomCurve3(ribs[k].map(([x,z])=>new THREE.Vector3(x,.026,z))),c2=new THREE.CatmullRomCurve3(ribs[k+1].map(([x,z])=>new THREE.Vector3(x,.026,z)));
    const a=c1.getPoint(u),b=c2.getPoint(clamp(u+.09));rod(g,a.toArray(),b.toArray(),.011,M.edge);
  }
  for(let i=0;i<outline.length-1;i+=5){const p=outline[i];if(p[0]>.8){ball(g,p[0],.016,p[2],.055,M.brass,[1,.7,1]);}}
  const patches=type==='front'?[[4.6,-2.95],[5.3,-2.30],[4.5,-1.18]]:[[3.45,.6],[3.7,1.45],[2.35,2.1]];
  for(const [x,z] of patches){const m=ball(g,x,.027,z,1,M.ivory,[.30,.025,.16]);m.rotation.y=-.5;box(g,x,.058,z,.11,.014,.12,M.orange);}
  box(g,.38,.01,0,.8,.12,.22,M.dark);box(g,.26,.08,-.015,.34,.06,.28,M.brass);
  rod(g,[0,0,0],[0,P.rocker,0],.07,M.orange);ball(g,0,P.rocker,0,.10,M.silver);
  const hinge=mesh(new THREE.CylinderGeometry(.15,.15,.30,20),M.dark,g);hinge.rotation.x=Math.PI/2;
  for(const x of [.13,.43,.72])bolt(g,x,.092,0,.055);
  wings.push({g,side,type,z});
  const crank=new THREE.Group();crank.position.z=z;root.add(crank);
  const disc=mesh(new THREE.CylinderGeometry(P.crank*1.18,P.crank*1.18,.09,24),M.brass,crank);disc.rotation.x=Math.PI/2;
  cranks.push({g:crank,type});
  const link=rod(root,[0,0,z],[side*.5,.4,z],.040,M.silver),pin=ball(root,0,0,z,.08,M.orange);
  connectors.push({link,pin,side,type,z});
}
for(const side of [-1,1])for(const type of ['front','back'])wing(side,type);

// Small toroidal bearing stack and coil on the head/drive axis.
for(let i=0;i<6;i++){const m=mesh(new THREE.TorusGeometry(.25,.025,6,20),M.brass,root);m.position.set(0,0,-1.10-i*.055);}
const axes=new THREE.Group();scene.add(axes);axes.position.set(-7.0,-4.17,3.7);
for(const [to,mat] of [[[.6,0,0],M.orange],[[0,.6,0],M.teal],[[0,0,.6],M.brass]])rod(axes,[0,0,0],to,.015,mat);

const shots=[
  {t:0,p:[15,12,19],target:[0,0,0]},
  {t:4,p:[12,17,17],target:[0,.15,0]},
  {t:8,p:[8,19,18],target:[0,.10,0]},
  {t:10.5,p:[8,16,17],target:[0,.25,0]},
  {t:12.2,p:[6.7,9,12],target:[0,.25,0]},
  {t:15,p:[5.5,8,11.5],target:[0,.3,0]},
  {t:16.5,p:[12,17,23],target:[0,.5,.2]},
  {t:18,p:[-10,20,24],target:[0,.5,.2]},
  {t:20,p:[-21,15,8],target:[0,.5,.2]},
  {t:22,p:[-14,14,-20],target:[0,.2,0]},
  {t:24,p:[0,17,-25],target:[0,.5,0]},
  {t:26,p:[1,13,-22],target:[0,1,-1]},
];
function cameraAt(t){let i=0;while(i<shots.length-2&&t>shots[i+1].t)i++;const a=shots[i],b=shots[i+1],u=smooth(a.t,b.t,t);
  return {p:a.p.map((v,j)=>v+(b.p[j]-v)*u),target:a.target.map((v,j)=>v+(b.target[j]-v)*u)};}
const beatNames=['SYSTEM WAKE','WING KINEMATICS','CARAPACE RELEASE','DRIVE TRAIN','EXPLODED ASSEMBLY','REASSEMBLY','DEPARTURE'];
const beatChinese=['系统唤醒 / 四翼展开','扑翼联动 / 连杆驱动','掀开背甲 / 释放外壳','深入机芯 / 传动特写','分层拆解 / 环绕检视','归位锁合 / 重构机体','振翅起飞 / 自由之形'];
const orange='#ed6238',ink='#273931',muted='#8f9487',lineColor='#d6d6c8',teal='#548b73';
function font(size=12,weight=400,mono=false){ctx.font=`${weight} ${size}px ${mono?'"SFMono-Regular",Consolas,monospace':'"Helvetica Neue",Arial,"PingFang SC",sans-serif'}`;}
function text(str,x,y,size=12,color=ink,weight=400,mono=false){font(size,weight,mono);ctx.fillStyle=color;ctx.fillText(str,x,y);}
function line(x1,y1,x2,y2,color=lineColor,width=1){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();}
function rect(x,y,w,h,color){ctx.fillStyle=color;ctx.fillRect(x,y,w,h);}
function circle(x,y,r,color,fill=false){ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx[fill?'fillStyle':'strokeStyle']=color;fill?ctx.fill():ctx.stroke();}
function panel(x,y,w,h,id,title){ctx.fillStyle='rgba(252,251,246,.89)';ctx.strokeStyle='#dedfd1';ctx.lineWidth=1;ctx.beginPath();ctx.roundRect(x,y,w,h,5);ctx.fill();ctx.stroke();rect(x+17,y+17,3,15,orange);text(title,x+29,y+29,12,ink,600,true);text(id,x+w-30,y+29,10,muted,400,true);}
function graph(x,y,w,h,f,color=orange){line(x,y+h,x+w,y+h);line(x,y,x,y+h);ctx.strokeStyle=color;ctx.lineWidth=1.7;ctx.beginPath();for(let i=0;i<=120;i++){const py=y+h*(1-f(i/120));i?ctx.lineTo(x+w*i/120,py):ctx.moveTo(x,py);}ctx.stroke();}
function bar(x,y,w,value,color=orange){rect(x,y,w,4,'#e5e5da');rect(x,y,w*clamp(value),4,color);}
const buttons=[];let manual=null,orbit=[0,0],zoom=1,paused=false,showPanels=true,clock=0,lastUser=0;
function button(x,y,w,label,active,fn){buttons.push({x,y,w,h:29,fn});ctx.fillStyle=active?orange:'#f6f5ee';ctx.strokeStyle=active?orange:lineColor;ctx.beginPath();ctx.roundRect(x,y,w,29,3);ctx.fill();ctx.stroke();text(label,x+9,y+19,10,active?'#fff':ink,600,true);}
function label(str,anchor,x,y){root.updateMatrixWorld(true);const v=root.localToWorld(new THREE.Vector3(...anchor)).project(camera),px=(v.x+1)*960,py=(1-v.y)*540;
  if(px<340||px>1560||py<150||py>870)return;
  circle(px,py,3,orange,true);line(px,py,x-12,y-4,'#b2b8a6');line(x-12,y-4,x+105,y-4,'#b2b8a6');text(str,x,y-11,10,muted,500,true);
}
function drawHUD(s){const w=hud.width,h=hud.height;ctx.setTransform(w/1920,0,0,h/1080,0,0);ctx.clearRect(0,0,1920,1080);buttons.length=0;
  if(!showPanels)return;
  // Fine corner marks keep the layout quiet while retaining the engineering-desk style.
  for(const [x,y] of [[354,172],[1566,172],[354,890],[1566,890]]){line(x-8,y,x+8,y,'#c6cdbd');line(x,y-8,x,y+8,'#c6cdbd');}
  rect(0,0,153,111,orange);
  ctx.save();ctx.translate(46,56);ctx.strokeStyle='#fff';ctx.lineWidth=1.4;
  for(const sign of [-1,1]){ctx.beginPath();ctx.moveTo(0,0);ctx.bezierCurveTo(sign*8,-23,sign*33,-27,sign*26,-6);ctx.bezierCurveTo(sign*28,18,sign*8,19,0,0);ctx.stroke();}
  line(0,-18,0,16,'#fff',2);ctx.restore();text('B–04',88,62,15,'#fff',500,true);
  text('ROBOTIC LEPIDOPTERA / KINETIC STUDY',181,35,10,muted,400,true);
  text('Aurelia B–04',180,76,38,ink,600);text('机械蝴蝶  /  四翼联动实验体',182,101,12,muted,400);
  const run=Math.floor(s.t*30);text('WING DRIVE',771,36,10,muted,400,true);
  for(let i=0;i<40;i++)rect(771+i*6,49,4,13,i/40<(s.angle+40)/86?orange:'#dddcd1');
  text(`${s.rpm.toFixed(0)} RPM`,1042,61,13,ink,600,true);
  for(const [x,title,value] of [[1198,'SIM ID','B04–1024'],[1382,'RUNTIME',`00:${String(Math.floor(s.t)).padStart(2,'0')}:${String(run%30).padStart(2,'0')}`],[1565,'STATUS',s.explode>.1?'INSPECT':s.fly>.1?'DEPART':'ACTIVE'],[1748,'PLAYBACK','1 / 4 ×']]){
    line(x-24,27,x-24,84);text(title,x,35,9,muted,400,true);text(value,x,65,12,x===1565?teal:ink,600,true);}
  panel(29,145,286,204,'01','FLAPPING DRIVE');text(s.hz.toFixed(1),48,217,42,ink,600);text('HZ',113,218,12,muted,400,true);
  text(s.rpm.toFixed(0),229,210,27,ink,500,true);text('RPM',249,229,10,muted,400,true);
  graph(49,247,246,58,u=>(linkage(s.phase+(u-1)*Math.PI*4).angle+.6)/1.45);
  text('MOTOR → CRANK → ROCKER',49,333,10,muted,400,true);
  panel(29,365,286,200,'02','WING TELEMETRY');text(`${s.angle.toFixed(1)}°`,48,433,38,ink,500);
  text('FOREWING / HINGE ANGLE',49,457,10,muted,400,true);
  for(const [i,n,v] of [[0,'FORE L',s.angle],[1,'FORE R',s.angle],[2,'HIND L',s.backAngle],[3,'HIND R',s.backAngle]]){
    const y=485+i*19;text(n,49,y,9,muted,400,true);bar(109,y-5,137,(v+40)/86,i<2?orange:teal);text(`${v.toFixed(0)}°`,263,y,10,ink,400,true);}
  panel(29,581,286,220,'03','LINKAGE / X–Y');
  const ox=91,oy=722,sc=190;
  const pr=p=>[ox+p[0]*sc,oy-p[1]*sc];
  const a=pr([0,0]),b=pr(s.front.p),c=pr(s.front.q),d=pr([P.hingeX,P.hingeY]);
  line(...a,...d,'#cbd0c1',3);line(...a,...b,orange,5);line(...b,...c,teal,4);line(...c,...d,ink,4);
  for(const v of [a,b,c,d]){circle(...v,5,ink,true);circle(...v,2,'#fff',true);}
  text('CLOSURE ERROR',49,769,9,muted,400,true);text(`${s.front.closure.toExponential(1)}`,191,769,11,teal,500,true);
  text('C = 0.23   R = 0.43   L = 0.77',49,788,9,muted,400,true);
  panel(1605,145,286,179,'04','ASSEMBLIES');
  button(1623,193,118,'ASSEMBLED',manual?.shell===0&&manual?.explode===0,()=>manual={shell:0,explode:0});
  button(1750,193,121,'CARAPACE',manual?.shell===1,()=>manual={shell:1,explode:0});
  button(1623,233,118,'EXPLODE',manual?.explode===1,()=>manual={shell:1,explode:1});
  button(1750,233,121,'AUTO TOUR',!manual,()=>{manual=null;orbit=[0,0];zoom=1;});
  text('SHELL',1624,299,10,muted,400,true);bar(1691,294,174,s.shell,orange);
  panel(1605,340,286,154,'05','MODEL INVENTORY');
  const rows=[['WING ASSEMBLIES','04'],['LANDING LEGS','06'],['RENDERED MESHES',String(meshCount)],['DRIVE RATIO','1 : 1']];
  for(let i=0;i<rows.length;i++){text(rows[i][0],1625,393+i*25,10,muted,400,true);text(rows[i][1],1829,393+i*25,12,ink,500,true);}
  panel(1605,510,286,154,'06','DISPLAY');
  button(1623,558,76,'HERO',false,()=>{orbit=[0,0];zoom=1;});
  button(1708,558,76,'TOP',false,()=>{orbit=[0,1.05];zoom=1;});
  button(1793,558,78,'MACRO',false,()=>{zoom=.65;});
  text('DRAG TO ORBIT / SCROLL TO ZOOM',1624,620,9,muted,400,true);
  text('SPACE PAUSE  ·  H HIDE PANELS',1624,641,9,muted,400,true);
  panel(1605,680,286,121,'07','FLIGHT CONTROL');
  const rates=[1.2,2.4,3.6];for(let i=0;i<3;i++)button(1623+i*84,729,77,`${rates[i]} HZ`,(manual?.hz??P.hz)===rates[i],()=>manual={...(manual??{}),hz:rates[i]});
  text('ILLUSTRATIVE KINEMATIC MODEL',1624,781,9,muted,400,true);
  label('FOREWING / COMPOSITE FRAME',[3.2,.2,-2.2],1140,229);
  if(s.shell>.4)label('LIFTED CARAPACE',[0,1.7,.2],1130,327);
  if(s.explode>.25)label('SEGMENTED ABDOMEN',[0,.0,3.2],1110,797);
  text('OPERATION MODE',362,815,10,muted,400,true);text(beatNames[s.beat],360,849,30,orange,600);
  text(beatChinese[s.beat],362,878,15,ink,400);
  panel(350,924,1220,100,'08','OPERATION LOG');
  button(370,968,55,paused?'PLAY':'Ⅱ',false,()=>paused=!paused);
  const start=454,end=1528;line(start,981,end,981,'#c9ccbd',2);line(start,981,start+(end-start)*s.t/26,981,orange,2);
  for(const t of [0,4,8,12,16,21,24,26]){const x=start+(end-start)*t/26;line(x,974,x,988,'#a6ad9b');}
  circle(start+(end-start)*s.t/26,981,6,orange,true);
  text(`${s.t.toFixed(2).padStart(5,'0')} / 26.00`,454,1007,10,muted,400,true);
  text('7 SEQUENCES / PURE TIME MODEL',1277,1007,9,muted,400,true);
  text('AURELIA LAB / PROCEDURAL MECHANISMS',30,1053,9,muted,400,true);
  text('CONCEPT KINEMATICS · NOT A FLIGHT SOLVER',713,1053,9,muted,400,true);
  text('FOUR WINGS. ONE HEART.',1695,1053,9,muted,400,true);
}

let W=0,H=0;
function resize(){const w=innerWidth,h=innerHeight;if(w===W&&h===H)return;W=w;H=h;renderer.setSize(w,h,false);hud.width=w;hud.height=h;camera.aspect=w/h;camera.updateProjectionMatrix();}
function poseModel(s){window.currentState=s;
  root.position.set(0,s.hover+s.fly*2.8,-s.fly*3.8);root.rotation.set(-s.fly*.16,.05*Math.sin(s.t*.35),0);
  for(const w of wings){const kin=w.type==='front'?s.front:s.back;
    w.g.rotation.z=w.side*kin.angle;w.g.position.set(w.side*(P.hingeX+s.explode*1.8),P.hingeY+s.explode*.55,w.z+(w.type==='front'?-1:1)*s.explode*.6);}
  for(const c of connectors){const kin=c.type==='front'?s.front:s.back,dx=c.side*s.explode*1.8,dy=s.explode*.55,dz=(c.type==='front'?-1:1)*s.explode*.6;
    updateRod(c.link,[c.side*kin.p[0]+dx,kin.p[1]+dy,c.z+dz],[c.side*kin.q[0]+dx,kin.q[1]+dy,c.z+dz],.040);
    c.pin.position.set(c.side*kin.p[0]+dx,kin.p[1]+dy,c.z+dz);}
  for(const c of cranks)c.g.rotation.z=(c.type==='front'?s.phase:s.phase-.32);
  for(const sh of shells)sh.g.position.copy(sh.base).addScaledVector(sh.dir,s.shell);
  for(const seg of segments){seg.g.position.set(0,-.04-s.explode*.12*seg.i,seg.z+s.explode*.18*(seg.i+1));seg.g.rotation.x=.012*Math.sin(s.phase-seg.i*.4);}
  for(const {g,ratio,offset} of gears)g.rotation.y=s.phase*ratio+offset;
  for(const l of legs)l.g.rotation.z=l.side*s.fly*.35;
}
function render(t){resize();const s=stateAt(t,manual??{});poseModel(s);
  const cam=cameraAt(t);let pos=new THREE.Vector3(...cam.p),target=new THREE.Vector3(...cam.target);
  if(orbit[0]||orbit[1]){const spherical=new THREE.Spherical().setFromVector3(pos.clone().sub(target));spherical.theta+=orbit[0];spherical.phi=clamp(spherical.phi-orbit[1],.12,Math.PI*.48);pos.setFromSpherical(spherical).add(target);}
  camera.position.copy(target.clone().add(pos.sub(target).multiplyScalar(zoom)));camera.lookAt(target);
  renderer.render(scene,camera);drawHUD(s);return s;
}
window.render=render;window.modelParameters=P;window.meshInventory=meshCount;
window.auditPose=()=>{
  root.updateMatrixWorld(true);
  let hornError=0,rodError=0,minWingY=Infinity;
  for(const w of wings){
    const membrane=w.g.children[0],vertices=membrane.geometry.attributes.position;
    for(let i=0;i<vertices.count;i++){
      const p=membrane.localToWorld(new THREE.Vector3().fromBufferAttribute(vertices,i));
      minWingY=Math.min(minWingY,p.y);
    }
  }
  for(const c of connectors){
    const w=wings.find(w=>w.side===c.side&&w.type===c.type);
    const horn=w.g.localToWorld(new THREE.Vector3(0,P.rocker,0));
    const end=c.link.localToWorld(new THREE.Vector3(0,.5,0));
    const start=c.link.localToWorld(new THREE.Vector3(0,-.5,0));
    hornError=Math.max(hornError,horn.distanceTo(end));
    rodError=Math.max(rodError,Math.abs(start.distanceTo(end)-P.rod));
  }
  return {hornError,rodError,groundClearance:minWingY-ground.position.y,meshes:meshCount};
};
// A URL without ?interactive=1 remains a deterministic still/render surface.
let dragging=false,prev=[0,0],moved=false;
const touch=()=>{lastUser=performance.now();};
hud.addEventListener('pointerdown',e=>{dragging=true;moved=false;prev=[e.clientX,e.clientY];touch();hud.setPointerCapture(e.pointerId);});
hud.addEventListener('pointermove',e=>{if(!dragging)return;const dx=e.clientX-prev[0],dy=e.clientY-prev[1];if(Math.abs(dx)+Math.abs(dy)>2)moved=true;orbit[0]-=dx*.005;orbit[1]+=dy*.005;prev=[e.clientX,e.clientY];touch();});
hud.addEventListener('pointerup',e=>{dragging=false;if(moved)return;const x=e.clientX/W*1920,y=e.clientY/H*1080;const b=buttons.find(b=>x>=b.x&&x<=b.x+b.w&&y>=b.y&&y<=b.y+b.h);if(b)b.fn();if(y>958&&y<1018&&x>454&&x<1528)clock=clamp((x-454)/1074)*26;touch();render(clock);});
hud.addEventListener('wheel',e=>{e.preventDefault();zoom=clamp(zoom+e.deltaY*.0007,.5,1.8);touch();},{passive:false});
addEventListener('keydown',e=>{if(e.code==='Space'){e.preventDefault();paused=!paused;}if(e.key.toLowerCase()==='h')showPanels=!showPanels;touch();});
await document.fonts.ready;
renderer.compile(scene,camera);render(0);window.READY=true;
if(new URLSearchParams(location.search).get('interactive')==='1'||document.documentElement.dataset.interactive==='true'){
  let prevTime=performance.now();function tick(now){if(!paused)clock=(clock+Math.min(.05,(now-prevTime)/1000))%26;prevTime=now;
    if(lastUser&&now-lastUser>25000){manual=null;orbit=[0,0];zoom=1;lastUser=0;}
    render(clock);requestAnimationFrame(tick);}requestAnimationFrame(tick);
}
export {THREE,scene,renderer,camera,root,core,motorGroup,motor,head,gears,wings,shells,segments,
  connectors,cranks,M,ground,grid,axes,key,hud,ctx,poseModel,resize,mesh,box,ball,rod,ring,bolt,tube};
