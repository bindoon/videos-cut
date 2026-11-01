import * as THREE from 'three';

// Every position, reveal and camera is a pure function of film time.
const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
const smooth=x=>{x=clamp(x);return x*x*(3-2*x)};
const ramp=(t,a,b)=>smooth((t-a)/(b-a));
const mix=(a,b,u)=>a+(b-a)*u;
const V=a=>new THREE.Vector3(...a);
const scene=new THREE.Scene();
scene.background=new THREE.Color('#eeeae1');
scene.fog=new THREE.Fog('#eeeae1',16,37);
const camera=new THREE.PerspectiveCamera(35,innerWidth/innerHeight,.04,70);
const renderer=new THREE.WebGLRenderer({canvas:document.querySelector('#scene'),antialias:true,alpha:false,preserveDrawingBuffer:true});
renderer.setPixelRatio(1);renderer.setSize(innerWidth,innerHeight);
renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.22;
renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
scene.add(new THREE.HemisphereLight('#ffffff','#7e8d8c',2.1));
const key=new THREE.DirectionalLight('#fff6e5',3.2);key.position.set(-4,9,6);key.castShadow=true;
key.shadow.mapSize.set(2048,2048);Object.assign(key.shadow.camera,{left:-5,right:5,top:6,bottom:-4,near:.1,far:23});key.shadow.bias=-.0005;scene.add(key);
const rim=new THREE.DirectionalLight('#bce9ed',2.2);rim.position.set(4,4,-4);scene.add(rim);

const mat=(color,opts={})=>new THREE.MeshStandardMaterial({color,roughness:.57,metalness:0,...opts});
const M={robe:mat('#315a69',{roughness:.86}),robeLight:mat('#537d87',{roughness:.9}),seam:mat('#b8c9c3'),skin:mat('#d7c4a8'),hair:mat('#273a3b'),bone:mat('#f5e7c8',{roughness:.4}),muscle:mat('#9f4542'),muscle2:mat('#c16a59'),fiber:mat('#df9c7e'),tendon:mat('#ede0b8'),gold:mat('#b48132',{metalness:.54,roughness:.3}),teal:mat('#1b8d86',{metalness:.2}),dark:mat('#183d44')};
const skinMat=M.skin.clone();skinMat.transparent=true;
const calfCloth=M.robe.clone();calfCloth.transparent=true;
const thighCloth=M.robe.clone();thighCloth.transparent=true;
const muscleMat=M.muscle.clone();muscleMat.transparent=true;
const fiberMat=M.fiber.clone();fiberMat.transparent=true;
const tendonMat=M.tendon.clone();tendonMat.transparent=true;
const boneMat=M.bone.clone();boneMat.transparent=true;
const anatomyMaterials=[muscleMat,fiberMat,tendonMat,boneMat];
const sphereGeom=new THREE.SphereGeometry(1,24,16);
function mesh(g,m,parent=scene){const o=new THREE.Mesh(g,m);o.castShadow=true;o.receiveShadow=true;parent.add(o);return o}
function ell(parent,p,s,m){const o=mesh(sphereGeom,m,parent);o.position.copy(V(p));o.scale.set(...s);return o}
function rod(parent,a,b,r,m,r2=r){const A=V(a),B=V(b),d=B.clone().sub(A);const o=mesh(new THREE.CylinderGeometry(r2,r,d.length(),12),m,parent);o.position.copy(A.add(B).multiplyScalar(.5));o.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),d.normalize());return o}
function tube(parent,pts,r,m,segments=45){const curve=new THREE.CatmullRomCurve3(pts.map(V));return mesh(new THREE.TubeGeometry(curve,segments,r,7,false),m,parent)}
function line(parent,pts,color,opacity=1){const o=new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts.map(V)),new THREE.LineBasicMaterial({color,transparent:true,opacity}));parent.add(o);return o}
function spindle(parent,a,b,width,depth,m){const A=V(a),B=V(b);const o=ell(parent,A.clone().add(B).multiplyScalar(.5).toArray(),[width,A.distanceTo(B)*.53,depth],m);o.quaternion.setFromUnitVectors(V([0,1,0]),B.sub(A).normalize());return o}

// The stage opens below the contact plane to expose the root metaphor.
const floorMat=mat('#e5e0d4',{transparent:true,opacity:1,roughness:1,depthWrite:false});
const floor=mesh(new THREE.CircleGeometry(12,100),floorMat);floor.rotation.x=-Math.PI/2;floor.position.y=-.012;floor.castShadow=false;
const grid=new THREE.Group();scene.add(grid);
for(let i=1;i<=5;i++){
 const pts=Array.from({length:181},(_,j)=>[Math.cos(j*Math.PI/90)*i*.8,.003,Math.sin(j*Math.PI/90)*i*.8]);
 line(grid,pts,'#8d9b91',.18);
}
line(grid,[[-4,.005,0],[4,.005,0]],'#8d9b91',.15);line(grid,[[0,.005,-3],[0,.005,3]],'#8d9b91',.15);
const stage=mesh(new THREE.CylinderGeometry(1.37,1.37,.035,96),mat('#ded7c4',{transparent:true,opacity:.52}));stage.position.set(-.97,-.04,.35);
stage.material.depthWrite=false;

// Rig: a wide, low stance. Right foot stays planted during the torque illustration.
const person=new THREE.Group();scene.add(person);
const body=new THREE.Group();person.add(body);
const torso=ell(body,[0,3.03,-.05],[.59,.82,.35],M.robe);
ell(body,[0,2.53,-.02],[.65,.29,.39],M.robeLight);
ell(body,[0,3.65,-.035],[.23,.19,.235],M.robeLight);
const front=new THREE.Group();front.position.set(0,3.1,.29);body.add(front);
tube(front,[[0,-.65,.04],[.06,-.1,.08],[.035,.4,.02],[.1,.66,-.1]],.016,M.seam);
for(let j=0;j<4;j++){
 const y=.34-j*.21;tube(front,[[-.12,y,0],[-.035,y+.025,.055],[.08,y,.05],[.18,y+.018,-.005]],.014,M.seam,16);
 ell(front,[.15,y,.025],[.026,.025,.024],M.bone);
}
for(const side of [-1,1]){
 const pos=[],indices=[];
 for(let j=0;j<=16;j++)for(let i=0;i<=14;i++){
  const u=i/14,v=j/16,x=side*(.025+u*(.50+.13*v));
  pos.push(x,2.64-v*(.48+.10*u),.33+.07*v+.025*Math.sin(u*17+v*3));
 }
 for(let j=0;j<16;j++)for(let i=0;i<14;i++){const a=j*15+i;indices.push(a,a+1,a+15,a+1,a+16,a+15)}
 const geom=new THREE.BufferGeometry();geom.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));geom.setIndex(indices);geom.computeVertexNormals();
 const fabric=M.robe.clone();fabric.side=THREE.DoubleSide;mesh(geom,fabric,body);
}
const head=new THREE.Group();head.position.set(0,4.08,-.015);head.rotation.y=-.38;body.add(head);
ell(head,[0,0,0],[.255,.355,.235],M.skin);
ell(head,[0,.17,-.045],[.266,.22,.23],M.hair);
ell(head,[0,.12,-.19],[.23,.23,.09],M.hair);
ell(head,[0,-.075,.235],[.052,.11,.058],M.skin);
ell(head,[0,-.14,.267],[.062,.042,.04],M.skin);
for(let s of [-1,1]){
 ell(head,[s*.254,-.02,-.012],[.046,.09,.054],M.skin);
 tube(head,[[s*.055,.035,.218],[s*.108,.055,.219],[s*.16,.041,.19]],.009,M.hair,12);
 tube(head,[[s*.061,-.004,.225],[s*.104,-.011,.228],[s*.142,-.003,.207]],.006,M.hair,12);
}
tube(head,[[-.066,-.21,.199],[0,-.216,.218],[.063,-.206,.201]],.006,M.hair,15);

function clothSegment(parent,radius,length=1,material=M.robe){
 const pts=[];for(let j=0;j<=28;j++){const u=j/28;pts.push(new THREE.Vector2(radius*(.78+.22*Math.sin(Math.PI*u)),(u-.5)*length))}
 const g=new THREE.LatheGeometry(pts,32),a=g.attributes.position;
 for(let i=0;i<a.count;i++){const x=a.getX(i),z=a.getZ(i),y=a.getY(i);const f=1+.035*Math.cos(Math.atan2(z,x)*8+y*4)*Math.sin(Math.PI*(y/length+.5));a.setXYZ(i,x*f,y,z*f)}
 g.computeVertexNormals();return mesh(g,material,parent);
}
function rigSegment(parent,r,m){const o=clothSegment(parent,r,1,m);return o}
function setSegment(o,a,b){const A=V(a),B=V(b);o.position.copy(A.clone().add(B).multiplyScalar(.5));o.scale.y=A.distanceTo(B);o.quaternion.setFromUnitVectors(V([0,1,0]),B.sub(A).normalize())}
const leftThigh=rigSegment(person,.36,M.robe),leftCalf=rigSegment(person,.29,M.robe);
const rightThigh=rigSegment(person,.37,thighCloth),rightCalf=rigSegment(person,.28,calfCloth);
const hipR=[-.38,2.56,-.03],kneeR=[-1.03,1.48,.35],ankleR=[-1.0,.48,.05];
const hipL=[.36,2.56,-.04],kneeL=[1.0,1.44,.12],ankleL=[1.36,.38,-.08];
setSegment(rightThigh,hipR,kneeR);setSegment(rightCalf,kneeR,ankleR);
setSegment(leftThigh,hipL,kneeL);setSegment(leftCalf,kneeL,ankleL);
ell(person,kneeL,[.235,.25,.235],M.robe);
ell(person,kneeR,[.23,.24,.23],calfCloth);

function hand(parent){const g=new THREE.Group();parent.add(g);
 ell(g,[0,0,0],[.13,.2,.052],M.skin);
 for(let i=0;i<4;i++){
  const x=(i-1.5)*.068,l=[.23,.28,.26,.20][i];
  rod(g,[x,.105,0],[x*1.18,.105+l, .012],.027,M.skin,.021);
  ell(g,[x*1.18,.105+l,.012],[.022,.027,.024],M.skin);
  tube(g,[[x-.017,.19,.049],[x+.014,.19,.05]],.0025,M.skin,4);
 }
 rod(g,[-.09,-.025,.0],[-.22,.095,.035],.04,M.skin,.029);
 ell(g,[-.22,.095,.035],[.033,.038,.031],M.skin);
 return g;
}
const armRU=rigSegment(body,.24,M.robe),armRF=rigSegment(body,.20,M.robeLight);
const armLU=rigSegment(body,.24,M.robe),armLF=rigSegment(body,.20,M.robeLight);
const handR=hand(body),handL=hand(body);

// Foot with five individual articulated toe rays, metatarsals, tendons and pads.
const foot=new THREE.Group();foot.position.set(-1,0,.05);scene.add(foot);
const surface=new THREE.Group();foot.add(surface);
ell(surface,[0,.20,-.11],[.235,.21,.32],skinMat);
ell(surface,[0,.235,.26],[.245,.155,.40],skinMat);
ell(surface,[0,.15,.52],[.335,.13,.23],skinMat);
ell(surface,[0,.40,-.045],[.145,.26,.16],skinMat);
const toes=[],toeX=[-.255,-.09,.048,.17,.266],toeZ=[.57,.635,.62,.575,.51],toeLen=[.30,.32,.285,.235,.19];
const pads=[];
for(let i=0;i<5;i++){
 const toe=new THREE.Group();toe.position.set(toeX[i],.135,toeZ[i]);foot.add(toe);
 const r=i===0?.085:.055;
 ell(toe,[0,-.012,toeLen[i]*.43],[r,.077,toeLen[i]*.62],skinMat);
 ell(toe,[0,-.025,toeLen[i]*.83],[r*.86,.066,r*1.13],skinMat);
 const nail=ell(toe,[0,.038,toeLen[i]*.86],[r*.64,.009,r*.70],mat('#e7d8bc'));surface.add();toe.add(nail);
 rod(toe,[0,0,0],[0,-.01,toeLen[i]*.48],r*.41,boneMat,r*.35);
 rod(toe,[0,-.01,toeLen[i]*.48],[0,-.03,toeLen[i]*.9],r*.31,boneMat,r*.24);
 ell(toe,[0,-.01,toeLen[i]*.48],[r*.46,r*.43,r*.46],boneMat);
 const pad=mesh(new THREE.CircleGeometry(r*1.08,28),new THREE.MeshBasicMaterial({color:'#c49b45',transparent:true,opacity:0,depthWrite:false}),foot);pad.rotation.x=-Math.PI/2;pad.position.set(toeX[i],.012,toeZ[i]+toeLen[i]*.78);pads.push(pad);
 toes.push({g:toe,nail,i,r});
 rod(foot,[toeX[i]*.27,.23,-.05],[toeX[i],.18,toeZ[i]+.01],r*.50,boneMat,r*.38);
 // Dorsal interossei, between the metatarsals; pale extensor and flexor paths.
 if(i<4)spindle(foot,[toeX[i]*.4+.025,.255,.05],[toeX[i]+.04,.21,.50],.041,.035,muscleMat);
 for(let j=-1;j<=1;j++)tube(foot,[[toeX[i]*.3+j*.012,.39,-.12],[toeX[i]*.5+j*.013,.32,.18],[toeX[i]+j*.01,.245,.52],[toeX[i]+j*.008,.17,toeZ[i]+toeLen[i]*.65]],.007,tendonMat,30);
 tube(foot,[[toeX[i]*.2,.095,-.26],[toeX[i]*.65,.09,.26],[toeX[i],.088,toeZ[i]+toeLen[i]*.8]],.011,tendonMat,26);
}
ell(foot,[0,.19,-.20],[.16,.14,.19],boneMat);ell(foot,[0,.34,-.07],[.12,.12,.14],boneMat);
spindle(foot,[-.18,.16,-.18],[-.25,.15,.52],.065,.075,muscleMat);
spindle(foot,[.16,.14,-.18],[.25,.14,.45],.05,.055,muscleMat);
for(let j=0;j<12;j++)tube(foot,[[-.20+j*.004,.19,-.12],[-.26+j*.005,.20,.15],[-.26+j*.004,.19,.45]],.0035,fiberMat,20);

// The other foot remains clothed, preserving the relation to the opening stance.
const otherFoot=new THREE.Group();scene.add(otherFoot);otherFoot.position.set(1.37,0,-.04);otherFoot.rotation.y=-.40;
ell(otherFoot,[0,.15,.22],[.23,.16,.48],M.robeLight);ell(otherFoot,[0,.06,.27],[.24,.04,.48],M.dark);

const anatomyLeg=new THREE.Group();scene.add(anatomyLeg);
rod(anatomyLeg,ankleR,kneeR,.062,boneMat,.085);rod(anatomyLeg,[-.87,.48,.04],[-.87,1.45,.33],.035,boneMat,.045);
ell(anatomyLeg,kneeR,[.14,.15,.14],boneMat);rod(anatomyLeg,kneeR,hipR,.095,boneMat,.12);
ell(anatomyLeg,hipR,[.18,.18,.18],boneMat);
function muscle(a,b,w,d,phase=0){spindle(anatomyLeg,a,b,w,d,muscleMat);
 const A=V(a),B=V(b),axis=B.clone().sub(A),basis=V([0,0,1]).cross(axis).normalize(),basis2=axis.clone().normalize().cross(basis);
 for(let n=0;n<12;n++){
  const q=(n/12)*Math.PI*2,pts=[];
  for(let j=0;j<=14;j++){const u=j/14;const center=A.clone().lerp(B,u);const r=Math.pow(Math.sin(Math.PI*u),.8);center.addScaledVector(basis,Math.cos(q+phase*u)*w*r).addScaledVector(basis2,Math.sin(q+phase*u)*d*r);pts.push(center.toArray())}
  tube(anatomyLeg,pts,.004,fiberMat,22);
 }
}
muscle([-1.10,.63,-.02],[-1.17,1.42,.25],.135,.14);
muscle([-.93,.64,-.04],[-.91,1.42,.25],.12,.12);
muscle([-.92,.56,.16],[-.91,1.39,.43],.09,.11);
tube(anatomyLeg,[[-1.08,.78,-.06],[-1.06,.4,-.16],[-1,.18,-.21]],.028,tendonMat);
const thighStart=anatomyLeg.children.length;
muscle([-1.04,1.53,.44],[-.44,2.53,.22],.17,.15,.3);
muscle([-.87,1.55,.40],[-.24,2.47,.02],.14,.15,-.2);
muscle([-1.18,1.57,.29],[-.55,2.53,-.09],.14,.17,.5);
muscle([-1.05,1.63,.21],[-.42,2.47,-.26],.16,.11);
ell(anatomyLeg,[-1.035,1.49,.49],[.095,.125,.04],tendonMat);
const thighMuscles=new THREE.Group();
const thighParts=anatomyLeg.children.slice(thighStart,-1);
anatomyLeg.add(thighMuscles);thighMuscles.position.copy(V(kneeR));
for(const part of thighParts){thighMuscles.add(part);part.position.sub(V(kneeR))}

// Roots are a drawing metaphor, not anatomy. Curves start at toe contacts.
const roots=new THREE.Group();roots.position.copy(foot.position);scene.add(roots);
const rootMaterials=[],rootMeshes=[];
function rootBranch(points,r,branchIndex){
 const m=mat(branchIndex%2?'#9a743d':'#49776e',{transparent:true,opacity:.85,roughness:.8,depthWrite:false});rootMaterials.push(m);
 const o=tube(roots,points,r,m,28),curve=new THREE.CatmullRomCurve3(points.map(V)),a=o.geometry.attributes.position;
 for(let j=0;j<=28;j++){const c=curve.getPointAt(j/28),f=1-.92*(j/28);for(let k=0;k<8;k++){const n=j*8+k;a.setXYZ(n,c.x+(a.getX(n)-c.x)*f,c.y+(a.getY(n)-c.y)*f,c.z+(a.getZ(n)-c.z)*f)}}
 o.geometry.computeVertexNormals();o.castShadow=false;rootMeshes.push(o);
}
for(let i=0;i<5;i++){
 const x=toeX[i],z=toeZ[i]+toeLen[i]*.78;
 rootBranch([[x,0,z],[x+.035,-.20,z+.02],[x+(i-2)*.13,-.51,z+.08],[x+(i-2)*.25,-.90,z+.15]],.018,i);
 for(let j=0;j<3;j++){
  const a=[x+(i-2)*.06,-.26-j*.12,z+.04+j*.02],sgn=j%2?1:-1;
  rootBranch([a,[a[0]+sgn*.12,-.47-j*.1,a[2]+.07],[a[0]+sgn*(.29+i*.025),-.64-j*.12,a[2]+.18]],.008,i+j);
 }
}
rootBranch([[0,0,-.21],[.02,-.25,-.25],[-.18,-.55,-.49],[-.4,-.86,-.54]],.022,0);
const strata=new THREE.Group();scene.add(strata);
for(let i=0;i<4;i++)line(strata,[[-2.32,-.22-i*.23,.4],[-1.95,-.2-i*.23,.5],[-1.4,-.24-i*.23,.5],[-.7,-.19-i*.23,.52],[-.0,-.22-i*.23,.5]],'#c1b59a',.22);

const arrows=new THREE.Group();scene.add(arrows);
const torqueMaterial=mat('#b17b25',{transparent:true,opacity:1,metalness:.35});
function arcArrow(parent,center,r,start,end,colorMat){
 const g=new THREE.Group();g.position.copy(V(center));parent.add(g);
 const pts=Array.from({length:70},(_,j)=>{const a=mix(start,end,j/69);return [r*Math.cos(a),.012,r*Math.sin(a)]});
 tube(g,pts,.015,colorMat,60);
 const a=end,before=end-.03*Math.sign(end-start);const p=V([r*Math.cos(a),.012,r*Math.sin(a)]),dir=p.clone().sub(V([r*Math.cos(before),.012,r*Math.sin(before)])).normalize();
 const cone=mesh(new THREE.ConeGeometry(.065,.19,20),colorMat,g);cone.position.copy(p);cone.quaternion.setFromUnitVectors(V([0,1,0]),dir);return g;
}
arcArrow(arrows,[-1,.045,.36],.85,-.5,3.9,torqueMaterial);
arcArrow(arrows,[-1,.05,.36],1.02,3.4,5.75,torqueMaterial);
const spiral=new THREE.Group();scene.add(spiral);
const spiralMat=mat('#21867d',{transparent:true,opacity:1,metalness:.25});
// Right-handed frame: positive rotation about the knee-to-hip axis is CCW
// to an observer looking from hip to foot. Use this same sign for muscle twist.
const legAxis=V(hipR).sub(V(kneeR)).normalize();
const frameX=V([0,0,1]).cross(legAxis).normalize(),frameZ=legAxis.clone().cross(frameX);
for(let k=0;k<3;k++){
 const pts=[];for(let j=0;j<=100;j++){
  const u=j/100,a=k*Math.PI*2/3+u*Math.PI*2.0;
  const p=V(kneeR).lerp(V(hipR),u).addScaledVector(frameX,Math.cos(a)*.29).addScaledVector(frameZ,Math.sin(a)*.29);pts.push(p.toArray());
 }
 tube(spiral,pts,.013,spiralMat,90);
 const tip=V(pts.at(-1)),dir=tip.clone().sub(V(pts.at(-3))).normalize();const cone=mesh(new THREE.ConeGeometry(.055,.15,16),spiralMat,spiral);cone.position.copy(tip);cone.quaternion.setFromUnitVectors(V([0,1,0]),dir);
}
const flow=new THREE.Group();scene.add(flow);
const flowMat=mat('#c19c52',{transparent:true,opacity:.8,metalness:.2});
tube(flow,[[-1,.07,.75],[-.95,.55,.26],[-1.12,1.4,.45],[-.46,2.35,.3],[.12,2.9,.34],[.35,3.45,.19],[1.0,3.2,.4],[1.5,3.34,.6]],.022,flowMat,95);
const pulse=ell(scene,[-1,.1,.7],[.045,.045,.045],M.gold);
const flowCurve=new THREE.CatmullRomCurve3([[-1,.07,.75],[-.95,.55,.26],[-1.12,1.4,.45],[-.46,2.35,.3],[.12,2.9,.34],[.35,3.45,.19],[1.0,3.2,.4],[1.5,3.34,.6]].map(V));

const hud=document.querySelector('#hud'),ctx=hud.getContext('2d');
const C={ink:'#173f45',muted:'#71817a',gold:'#a67d36',teal:'#237f78',line:'#a9b4aa'};
function text(s,x,y,size=24,color=C.ink,weight=400,align='left'){
 ctx.fillStyle=color;ctx.font=`${weight} ${size}px "Noto Sans SC",sans-serif`;ctx.textAlign=align;ctx.fillText(s,x,y);
}
function rule(x,y,w,color=C.line){ctx.strokeStyle=color;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+w,y);ctx.stroke()}
function projected(p){const q=V(p).project(camera);return [(q.x*.5+.5)*1920,(-q.y*.5+.5)*1080]}
function leader(p,label,x,y,color=C.ink){const q=projected(p);ctx.strokeStyle=color;ctx.globalAlpha=.75;ctx.lineWidth=1.3;ctx.beginPath();ctx.moveTo(...q);ctx.lineTo(x-23,y-8);ctx.lineTo(x-8,y-8);ctx.stroke();ctx.beginPath();ctx.arc(...q,4,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();ctx.globalAlpha=1;ctx.font='400 22px "Noto Sans SC"';ctx.fillStyle='#eeeae1ed';ctx.fillRect(x-5,y-28,ctx.measureText(label).width+14,39);text(label,x,y,22,color)}
const chapters=[['01','以身带手','THE WHOLE MOVEMENT',0,6],['02','视线落到脚下','FOLLOW THE ROOT',6,9],['03','由表入里','BENEATH THE SURFACE',9,14],['04','五趾抓地 · 如树生根','FIVE CONTACTS, ONE ROOT',14,20],['05','脚底向外拧劲','OUTWARD TORQUE INTENT',20,25],['06','大腿向左缠转','A COUNTERING SPIRAL',25,31],['07','一根贯穿 · 一气相连','ONE CONTINUOUS THREAD',31,36]];
function drawHud(t){
 const w=innerWidth,h=innerHeight;hud.width=w;hud.height=h;ctx.setTransform(w/1920,0,0,h/1080,0,0);ctx.clearRect(0,0,1920,1080);
 ctx.fillStyle='#eeeae1f5';ctx.fillRect(0,0,1920,130);ctx.fillRect(0,946,1920,134);
 // Quiet editorial frame, with all labels in the final raster.
 text('缠 丝 劲',74,76,27,C.ink,500);text('ROOTED IN SPIRAL',74,108,12,C.muted,500);
 text('太极 · 劲意与解剖示意',1846,77,18,C.muted,400,'right');
 rule(74,129,1772,'#b7bfb3');
 const ch=chapters.find(c=>t>=c[3]&&t<c[4])||chapters.at(-1);
 const entrance=ramp(t,ch[3],ch[3]+.6);
 ctx.globalAlpha=entrance;text(ch[0],76,231,19,C.gold,500);text(ch[1],76,289,40,C.ink,500);text(ch[2],78,329,13,C.muted,500);rule(78,361,56,C.gold);ctx.globalAlpha=1;
 if(t<6){
  text('根',76,516,116,C.ink,300);text('从足底，读懂一条螺旋。',79,570,23,C.ink);
  text('沉肩 · 松胯 · 重心缓移',79,613,18,C.muted);
  leader([-.98,.12,.65],'承重脚',1380,799,C.gold);
 }else if(t<9){text('完整动作 → 足底特写',79,422,21,C.muted)}
 else if(t<14){
  text('皮肤淡出，显露骨骼、肌群与肌腱。',79,420,21,C.ink);
  leader([-1.13,.235,.40],'足背伸肌腱',1390,455,C.gold);
  leader([-1.24,.16,.31],'足内在肌 · 示意',1390,559,C.ink);
  leader([-.99,.20,-.11],'跗骨 / 跖骨',1390,668,C.ink);
 }else if(t<20){
  text('五趾贴地，趾腹下压。',79,420,24,C.ink);text('树根是“扎根感”的可视化比喻。',79,461,18,C.muted);
  leader([-.99,.015,.87],'趾腹接触区',1430,550,C.gold);
  leader([-1.05,-.49,.9],'向下扎根',1430,742,C.teal);
 }else if(t<25){
  text('脚底稳住，向外产生拧地的劲意。',79,421,22,C.ink);
  text('金色弧线 = 向外拧劲',79,469,18,C.gold);
  text('箭头示意力矩；脚掌保持接地。',79,508,18,C.muted);
  leader([-.19,.045,.52],'外旋劲意',1460,550,C.gold);
 }else if(t<31){
  text('脚下的拧劲，接入腿部螺旋。',79,421,23,C.ink);
  text('青色螺旋 = 大腿向左缠转',79,468,19,C.teal);
  text('“向左”按从髋向足俯视的逆时针标示。',79,511,17,C.muted);
  leader([-.56,2.13,.35],'大腿肌群',1450,405,C.ink);
  leader([-.99,1.47,.45],'膝部保留屈曲',1450,570,C.muted);
  leader([-1,.34,.12],'足底锚定',1450,782,C.gold);
  // Explicit top-view rotation inset removes screen-space ambiguity.
  ctx.save();ctx.translate(270,715);ctx.strokeStyle=C.line;ctx.lineWidth=1;ctx.beginPath();ctx.arc(0,0,71,0,Math.PI*2);ctx.stroke();
  ctx.strokeStyle=C.teal;ctx.lineWidth=4;ctx.beginPath();ctx.arc(0,0,54,.4,-4.5,true);ctx.stroke();const a=-4.5;ctx.translate(Math.cos(a)*54,Math.sin(a)*54);ctx.rotate(a-Math.PI/2);ctx.fillStyle=C.teal;ctx.beginPath();ctx.moveTo(10,0);ctx.lineTo(-8,-7);ctx.lineTo(-8,7);ctx.fill();ctx.restore();text('俯视 / 向左缠转',270,830,16,C.teal,400,'center');
 }else{
  text('足下有根',79,456,41,C.ink,400);text('腿上有缠',79,520,41,C.ink,400);text('周身相随',79,584,41,C.ink,400);
  text('抓地  →  拧劲  →  缠转  →  整体动作',79,656,20,C.gold);
 }
 rule(74,946,1772,'#b7bfb3');
 text('动作与解剖为艺术化示意；旋转关系随姿态而变。',75,991,16,C.muted);
 text('根 · 缠丝   /   2026',1846,991,15,C.muted,400,'right');
 ctx.fillStyle='#c8cdbf';ctx.fillRect(75,1034,1770,2);ctx.fillStyle=C.teal;ctx.fillRect(75,1034,1770*clamp(t/36),2);
 for(const c of chapters){ctx.fillStyle=c===ch?C.teal:'#9fae9f';ctx.fillRect(75+1770*c[3]/36,1030,2,10)}
}

function cameraAt(t){
 const cams=[
  [0,[7.2,4.7,10.9],[0,2.05,0],35],
  [6,[6.7,4.5,10.7],[-.05,2,0],35],
  [9,[1.35,1.85,3.05],[-.97,.24,.25],33],
  [14,[1.1,1.60,3.2],[-.98,.17,.31],33],
  [20,[1.3,1.40,3.5],[-.98,-.12,.34],35],
  [24.5,[1.15,2.5,3.5],[-.98,-.1,.32],36],
  [27,[2.85,2.9,5.8],[-.76,1.30,.14],33],
  [31,[2.9,3.0,5.9],[-.75,1.33,.10],33],
  [33.8,[6.3,4.3,10.4],[0,1.95,.05],35],
  [36,[6.6,4.5,10.8],[0,1.98,.04],35]
 ];
 let i=cams.findIndex((c,j)=>j<cams.length-1&&t>=c[0]&&t<cams[j+1][0]);if(i<0)i=cams.length-2;
 const a=cams[i],b=cams[i+1],u=smooth((t-a[0])/(b[0]-a[0]));camera.position.copy(V(a[1]).lerp(V(b[1]),u));camera.lookAt(V(a[2]).lerp(V(b[2]),u));camera.fov=mix(a[3],b[3],u);camera.updateProjectionMatrix();
}
function update(t){
 t=clamp(t,0,35.9999);
 const action=Math.sin((clamp(t,0,6)/6)*Math.PI-Math.PI*.5);
 const reprise=ramp(t,32,35.8);
 const move=action*(1-reprise)+Math.sin((t-32)*.65)*reprise;
 body.rotation.y=.10*move;body.position.x=.055*move;
 const shoulderR=[-.51,3.52,.00],elbowR=[-.83+.13*move,3.0+.14*move,.55],wristR=[-.32+.26*move,3.45+.13*move,.86];
 const shoulderL=[.51,3.52,0],elbowL=[1.00,3.02+.10*move,.25],wristL=[1.56-.08*move,3.18+.13*move,.48];
 setSegment(armRU,shoulderR,elbowR);setSegment(armRF,elbowR,wristR);setSegment(armLU,shoulderL,elbowL);setSegment(armLF,elbowL,wristL);
 handR.position.copy(V(wristR));handR.rotation.set(.25,-.55,.20+move*.12);handL.position.copy(V(wristL));handL.rotation.set(-.6,-.3,-1.1+move*.1);
 const reveal=ramp(t,9.1,11.5)*(1-ramp(t,32,34.3));
 skinMat.opacity=1-.89*reveal;skinMat.depthWrite=reveal<.5;skinMat.visible=skinMat.opacity>.03;
 toes.forEach(({nail})=>nail.visible=reveal<.7);
 const legReveal=ramp(t,24.5,26.8)*(1-ramp(t,32,34.3));
 calfCloth.opacity=1-.94*legReveal;thighCloth.opacity=1-.94*legReveal;calfCloth.depthWrite=legReveal<.5;thighCloth.depthWrite=legReveal<.5;
 anatomyLeg.visible=legReveal>.01;
 for(const m of anatomyMaterials){m.opacity=.95;m.visible=reveal>.001}
 const grip=ramp(t,14,16.7);
 toes.forEach(({g,i,r})=>{const a=grip*.24;g.rotation.x=a;const extent=Math.hypot(.066*Math.cos(a),r*1.13*Math.sin(a));g.position.y=mix(.038,.012,grip)+.025*Math.cos(a)+toeLen[i]*.83*Math.sin(a)+extent});
 pads.forEach(p=>p.material.opacity=grip*(.32+.09*Math.sin(t*2))*(1-ramp(t,33,35)));
 const rootGrowth=ramp(t,15.3,19.4);roots.scale.y=Math.max(.001,rootGrowth*.72);roots.visible=t>=15.3;
 roots.traverse(o=>{if(o.isMesh)o.material.opacity=.78*(1-.65*ramp(t,32,35))});
 floorMat.opacity=1-.87*ramp(t,14.8,17.5)+.7*ramp(t,31.3,34.5);floorMat.opacity=clamp(floorMat.opacity);
 stage.material.opacity=.46*(1-ramp(t,14,16));strata.visible=t>15&&t<32;
 arrows.visible=t>=20&&t<33.5;torqueMaterial.opacity=ramp(t,20,21)*(1-ramp(t,31.5,33.5));
 arrows.rotation.y=-ramp(t,20,24.5)*.36; // torque indicator moves, the planted foot does not.
 // Keep the arc centered on the contact patch while its group turns.
 arrows.position.set(-1+Math.cos(arrows.rotation.y)-.36*Math.sin(arrows.rotation.y),0,.36-Math.sin(arrows.rotation.y)-.36*Math.cos(arrows.rotation.y));
 spiral.visible=t>=25.5&&t<34;spiralMat.opacity=ramp(t,25.5,27)*(1-ramp(t,32.3,34));
 thighMuscles.quaternion.setFromAxisAngle(legAxis,.21*ramp(t,26,29));
 flow.visible=t>=31;pulse.visible=t>=31;flowMat.opacity=ramp(t,31,32.5)*.75;pulse.position.copy(flowCurve.getPoint((((t-31)*.23)%1+1)%1));
 cameraAt(t);renderer.render(scene,camera);drawHud(t);
 window.FILM_STATE={t,reveal,legReveal,rootGrowth,grip,footPosition:foot.position.toArray(),footRotation:foot.rotation.toArray(),toeContacts:toes.map(({g,i,r})=>g.position.y-.025*Math.cos(g.rotation.x)-toeLen[i]*.83*Math.sin(g.rotation.x)-Math.hypot(.066*Math.cos(g.rotation.x),r*1.13*Math.sin(g.rotation.x))),thighTwist:thighMuscles.quaternion.toArray(),camera:camera.position.toArray()};
}
await document.fonts.ready;
await Promise.all([300,400,500].map(w=>document.fonts.load(`${w} 24px "Noto Sans SC"`)));
window.render=async t=>update(t);update(0);window.READY=true;
const interactive=document.documentElement.dataset.interactive==='true'||new URLSearchParams(location.search).has('interactive');
if(interactive){
 document.querySelector('#controls').style.display='flex';let playing=true,time=0,last=performance.now();const seek=document.querySelector('#seek');
 document.querySelector('#play').onclick=()=>{playing=!playing;document.querySelector('#play').textContent=playing?'暂停':'播放'};
 seek.oninput=()=>{time=+seek.value;update(time)};
 const loop=now=>{if(playing)time=(time+Math.min(.08,(now-last)/1000))%36;last=now;update(time);seek.value=time;document.querySelector('#time').textContent=`00:${String(Math.floor(time)).padStart(2,'0')}`;requestAnimationFrame(loop)};requestAnimationFrame(loop);
}
