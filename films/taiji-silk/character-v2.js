import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {DRACOLoader} from 'three/addons/loaders/DRACOLoader.js';
const V=a=>new THREE.Vector3(...a),Q=()=>new THREE.Quaternion();
export const clamp=x=>Math.max(0,Math.min(1,x));
export const smooth=x=>{x=clamp(x);return x*x*(3-2*x)};
export const ramp=(t,a,b)=>smooth((t-a)/(b-a));
function worldQ(b,q){b.quaternion.copy(b.parent.getWorldQuaternion(Q()).invert().multiply(q));b.updateWorldMatrix(false,true)}
function worldP(b,p){b.position.copy(b.parent.worldToLocal(p.clone()));b.updateWorldMatrix(false,true)}
function aim(b,c,p){const origin=b.getWorldPosition(V([0,0,0]));const d=c.getWorldPosition(V([0,0,0])).sub(origin).normalize();worldQ(b,Q().setFromUnitVectors(d,p.clone().sub(origin).normalize()).multiply(b.getWorldQuaternion(Q())))}
function solve(a,b,c,target,pole){const A=a.getWorldPosition(V([0,0,0])),B=b.getWorldPosition(V([0,0,0])),C=c.getWorldPosition(V([0,0,0]));const l1=A.distanceTo(B),l2=B.distanceTo(C),dir=target.clone().sub(A),d=Math.min(dir.length(),l1+l2-.0001);dir.normalize();const along=(l1*l1+d*d-l2*l2)/(2*d),h=Math.sqrt(Math.max(0,l1*l1-along*along));const bend=pole.clone().sub(A);bend.addScaledVector(dir,-bend.dot(dir)).normalize();aim(a,b,A.clone().addScaledVector(dir,along).addScaledVector(bend,h));aim(b,c,target)}
function boneMap(root){const b={};root.traverse(o=>{if(o.isBone)b[o.name]=o});return b}
function restMap(b){return new Map(Object.values(b).map(o=>[o,{p:o.position.clone(),q:o.quaternion.clone(),s:o.scale.clone()}]))}
function restore(rest){for(const [b,r] of rest){b.position.copy(r.p);b.quaternion.copy(r.q);b.scale.copy(r.s)}}
function skinSums(mesh,i,test){const a=mesh.geometry.attributes,indices=a.skinIndex,weights=a.skinWeight;let w=0;for(let j=0;j<4;j++)if(test(mesh.skeleton.bones[indices.getComponent(i,j)].name))w+=weights.getComponent(i,j);return w}
function filteredGeometry(mesh,predicate){const g=mesh.geometry.clone(),idx=g.index,keep=[];for(let i=0;i<idx.count;i+=3){const a=idx.getX(i),b=idx.getX(i+1),c=idx.getX(i+2);if(predicate(a,b,c))keep.push(a,b,c)}g.setIndex(keep);return g}

// The recognizable textured character and the authored 163-joint foot rig are
// separate source assets; both are displayed, and their ankle landmarks coincide.
export async function createCharacter(scene){
 const draco=new DRACOLoader().setDecoderPath('./node_modules/three/examples/jsm/libs/draco/gltf/');
 const loader=new GLTFLoader().setDRACOLoader(draco);
 const [gBody,gMH,gMuscle,gBone]=await Promise.all([
  loader.loadAsync('./models/man-base/man-base-character-rigged.glb'),loader.loadAsync('./models/makehuman/male-163.glb'),
  loader.loadAsync('./models/anatomy/z-muscles.glb'),loader.loadAsync('./models/anatomy/z-skeleton.glb')]);
 const body=gBody.scene,mh=gMH.scene;scene.add(body,mh);body.scale.setScalar(2.35);
 const B=boneMap(body),F=boneMap(mh),bodyRest=restMap(B),footRest=restMap(F);
 body.updateMatrixWorld(true);mh.updateMatrixWorld(true);
 // Native automatic weights include small cross-digit influences. Preserve the
 // webbing blend, but remove leakage onto a different toe where one toe owns
 // most of the vertex, so an isolated toe control cannot tug its neighbour tip.
 mh.traverse(o=>{if(!o.isSkinnedMesh)return;const a=o.geometry.attributes,w=a.skinWeight,ids=a.skinIndex;for(let i=0;i<w.count;i++){const sums=new Map();for(let j=0;j<4;j++){const n=o.skeleton.bones[ids.getComponent(i,j)].name,m=n.match(/^toe([1-5])-\d([RL])$/);if(m){const k=m[1]+m[2];sums.set(k,(sums.get(k)||0)+w.getComponent(i,j))}}const dominant=[...sums].sort((a,b)=>b[1]-a[1])[0];if(!dominant||dominant[1]<.6)continue;let total=0;const values=[];for(let j=0;j<4;j++){const n=o.skeleton.bones[ids.getComponent(i,j)].name,m=n.match(/^toe([1-5])-\d([RL])$/);const value=m&&m[1]+m[2]!==dominant[0]?0:w.getComponent(i,j);values.push(value);total+=value}for(let j=0;j<4;j++)w.setComponent(i,j,values[j]/total)}w.needsUpdate=true});
 const footQ={},heroFootQ={};for(const side of ['Right','Left'])heroFootQ[side]=B[side+'Foot'].getWorldQuaternion(Q());
 for(const side of ['R','L'])footQ[side]=F['foot'+side].getWorldQuaternion(Q());
 const uniforms={leg:{value:0},foot:{value:0}},bodySkins=[];
 body.traverse(o=>{if(!o.isSkinnedMesh)return;const g=o.geometry,cut=new Float32Array(g.attributes.position.count),leg=new Float32Array(cut.length);
  for(let i=0;i<cut.length;i++){cut[i]=skinSums(o,i,n=>/Foot|Toe/.test(n));leg[i]=skinSums(o,i,n=>/^Right(UpLeg|Leg)/.test(n));if(g.attributes.position.getY(i)<.94&&g.attributes.position.getX(i)<-.025)leg[i]=1}
  // Remove the old feet, including the ankle cuff, leaving the new surface to overlap it.
  const pos=g.attributes.position;const mask=i=>pos.getY(i)<.125;
  o.geometry=filteredGeometry(o,(a,b,c)=>!(mask(a)&&mask(b)&&mask(c)));
  o.geometry.setAttribute('anatomyMask',new THREE.BufferAttribute(leg,1));o.material=o.material.clone();o.material.side=THREE.FrontSide;o.material.alphaHash=true;
  o.material.onBeforeCompile=s=>{s.uniforms.cutaway=uniforms.leg;s.vertexShader='attribute float anatomyMask; varying float vAnatomy;\n'+s.vertexShader;s.vertexShader=s.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvAnatomy=anatomyMask;');s.fragmentShader='uniform float cutaway; varying float vAnatomy;\n'+s.fragmentShader;s.fragmentShader=s.fragmentShader.replace('#include <alphahash_fragment>','diffuseColor.a*=1.0-cutaway*smoothstep(0.08,0.70,vAnatomy);\n#include <alphahash_fragment>')};o.material.customProgramCacheKey=()=> 'taiji-v2-cutaway';o.castShadow=true;o.receiveShadow=true;bodySkins.push(o);
 });

 // Reference skin points in the unposed MakeHuman coordinate system. These
 // transfer skinning to named Z-Anatomy meshes; the geometry stays authored anatomy.
 const reference=[],skinMeshes=[];const temp=V([0,0,0]);
 mh.traverse(o=>{if(!o.isSkinnedMesh)return;o.updateMatrixWorld(true);const p=o.geometry.attributes.position;
  for(let i=0;i<p.count;i++){temp.fromBufferAttribute(p,i).applyMatrix4(o.matrixWorld);if(temp.x<-.025&&temp.y<1.05){const ids=[],ws=[];for(let j=0;j<4;j++){ids.push(o.geometry.attributes.skinIndex.getComponent(i,j));ws.push(o.geometry.attributes.skinWeight.getComponent(i,j))}reference.push({p:temp.clone(),ids,ws,skeleton:o.skeleton})}}
  skinMeshes.push(o);
 });
 const skeleton=skinMeshes[0].skeleton,grid=new Map(),cell=.025;
 const key=(x,y,z)=>`${x},${y},${z}`;
 for(const r of reference){const p=r.p,k=key(Math.floor(p.x/cell),Math.floor(p.y/cell),Math.floor(p.z/cell));if(!grid.has(k))grid.set(k,[]);grid.get(k).push(r)}
 function nearestWeights(p){const q=[p.x,p.y,p.z].map(x=>Math.floor(x/cell));let near=[];
  for(let radius=1;radius<=5;radius++){near=[];for(let x=-radius;x<=radius;x++)for(let y=-radius;y<=radius;y++)for(let z=-radius;z<=radius;z++)for(const r of grid.get(key(q[0]+x,q[1]+y,q[2]+z))||[])near.push({r,d:r.p.distanceToSquared(p)});if(near.length>=3)break}
  if(!near.length)near=reference.map(r=>({r,d:r.p.distanceToSquared(p)}));near.sort((a,b)=>a.d-b.d);const sums=new Map();for(const {r,d} of near.slice(0,3)){const f=1/(d+1e-6);for(let j=0;j<4;j++)sums.set(r.ids[j],(sums.get(r.ids[j])||0)+r.ws[j]*f)}const top=[...sums].sort((a,b)=>b[1]-a[1]).slice(0,4),total=top.reduce((n,x)=>n+x[1],0)||1;while(top.length<4)top.push([0,0]);return {ids:top.map(x=>x[0]),ws:top.map(x=>x[1]/total)};
 }
 function anatomicalToSkin(p){const y=p.y;
  if(y<.10){return V([-.2025+(p.x+.075)*1.10+.17*(p.z+.04),p.y*.95+.004,.01383+(p.z+.04)*1.18])}
  const u=clamp((y-.075)/.825),srcX=-.078-.017*u,dstX=-.2025+.0915*u;
  return V([dstX+(p.x-srcX)*1.03,.074+(y-.075)*1.0737,p.z+.049*(1-u)]);
 }
 const anatomy=[],muscleParts=[],boneParts=[];
 const palette={bone:'#dfd3ae',tendon:'#f0dfb7',muscle:'#aa4e48'};
 function tissue(kind){const m=new THREE.MeshPhysicalMaterial({color:palette[kind],roughness:kind==='bone'?.46:.56,metalness:0,clearcoat:kind==='muscle'?.16:.04,clearcoatRoughness:.4,transparent:true,opacity:0,depthWrite:false,side:THREE.DoubleSide});return m}
 for(const [source,type] of [[gMuscle.scene,'muscle'],[gBone.scene,'bone']]){
  source.updateMatrixWorld(true);source.traverse(o=>{if(!o.isMesh)return;const name=o.userData.zname||o.userData.name||o.name;if(!name.endsWith('.r'))return;const box=new THREE.Box3().setFromObject(o);if(box.max.y>1.0||box.min.y<-.01||box.getCenter(V([0,0,0])).x<-.22||/hand|pollicis|indicis|metacarpal|carpal|finger(?! of foot)/i.test(name))return;
   const geom=o.geometry.clone();geom.applyMatrix4(o.matrixWorld);const p=geom.attributes.position,ids=[],weights=[];
   for(let i=0;i<p.count;i++){const v=anatomicalToSkin(V([p.getX(i),p.getY(i),p.getZ(i)]));p.setXYZ(i,v.x,v.y,v.z);let w=nearestWeights(v);
    const digit=name.match(/(first|second|third|fourth|fifth) finger of foot/);if(digit&&/phalanx/.test(name)){const digitN=['first','second','third','fourth','fifth'].indexOf(digit[1])+1;let part=/Distal/.test(name)?(digitN===1?2:3):/Middle/.test(name)?2:1;const n=skeleton.bones.findIndex(b=>b.name===`toe${digitN}-${part}R`);if(n>=0)w={ids:[n,0,0,0],ws:[1,0,0,0]}}
    ids.push(...w.ids);weights.push(...w.ws);
   }
   geom.setAttribute('skinIndex',new THREE.Uint16BufferAttribute(ids,4));geom.setAttribute('skinWeight',new THREE.Float32BufferAttribute(weights,4));geom.computeVertexNormals();
   const tendon=o.userData.zmat==='Tendon',material=tissue(type==='bone'?'bone':tendon?'tendon':'muscle');
   const m=new THREE.SkinnedMesh(geom,material);m.name=name;m.bind(skeleton,new THREE.Matrix4());m.frustumCulled=false;m.castShadow=false;m.receiveShadow=true;mh.add(m);const item={m,name,type,tendon,foot:box.max.y<.18,sourceBox:box};anatomy.push(item);(type==='bone'?boneParts:muscleParts).push(item);
  });
 }
 // Keep the native foot skin and nail geometry, including a short ankle cuff.
 const footSkin=[],toeSamples=Array.from({length:5},()=>[]),heelSamples=[];
 for(const o of skinMeshes){const a=o.geometry.attributes,p=a.position;const points=[];for(let i=0;i<p.count;i++)points.push(V([p.getX(i),p.getY(i),p.getZ(i)]).applyMatrix4(o.matrixWorld));
  const keep=i=>points[i].y<.117&&(points[i].x<-.11||points[i].x>.11);
  o.geometry=filteredGeometry(o,(a,b,c)=>keep(a)&&keep(b)&&keep(c));
  if(!o.geometry.index.count){o.visible=false;continue}
  const nails=o.name==='base_4';o.material=new THREE.MeshPhysicalMaterial({color:nails?'#e2bca4':'#cfa58b',roughness:nails?.3:.68,clearcoat:nails?.35:.08,transparent:true,opacity:1});
  o.geometry.setAttribute('rightFootMask',new THREE.Float32BufferAttribute(points.map(p=>p.x<0?1:0),1));o.material.onBeforeCompile=s=>{s.uniforms.footFade=uniforms.foot;s.vertexShader='attribute float rightFootMask; varying float vRightFoot;\n'+s.vertexShader;s.vertexShader=s.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvRightFoot=rightFootMask;');s.fragmentShader='uniform float footFade; varying float vRightFoot;\n'+s.fragmentShader;s.fragmentShader=s.fragmentShader.replace('#include <alphatest_fragment>','diffuseColor.a*=1.0-footFade*vRightFoot;\n#include <alphatest_fragment>')};o.material.customProgramCacheKey=()=> 'separate-foot-opacity';o.material.depthWrite=true;o.castShadow=true;o.receiveShadow=true;footSkin.push(o);
  if(!nails){for(let i=0;i<p.count;i++){const point=points[i];if(point.x>-.11||point.y>.065)continue;const sum=[];for(let digit=1;digit<=5;digit++)sum.push(skinSums(o,i,n=>n.startsWith(`toe${digit}-`)&&n.endsWith('R')));const max=Math.max(...sum),digit=sum.indexOf(max);if(max>.4){const last=digit===0?2:3;const lastWeight=skinSums(o,i,n=>n===`toe${digit+1}-${last}R`);if(lastWeight>.32)toeSamples[digit].push({m:o,i})}else if(point.z<-.015)heelSamples.push({m:o,i})}}
 }
 // Join the two authored surfaces with a narrow mesh loft between their actual
 // open boundary loops. This avoids a visible cut seam at the shared ankle.
 function rim(mesh,side,lower,upper){const idx=mesh.geometry.index,p=mesh.geometry.attributes.position,edges=new Map();for(let i=0;i<idx.count;i+=3){const f=[idx.getX(i),idx.getX(i+1),idx.getX(i+2)];for(let j=0;j<3;j++){const a=f[j],b=f[(j+1)%3],k=a<b?`${a},${b}`:`${b},${a}`;edges.set(k,(edges.get(k)||0)+1)}}const ids=new Set();for(const [e,n] of edges)if(n===1)for(const i of e.split(',').map(Number)){if(p.getY(i)>lower&&p.getY(i)<upper&&p.getX(i)*side>.05)ids.add(i)}return [...ids].map(i=>({m:mesh,i}))}
 const seams=[];for(const side of [-1,1]){const top=bodySkins.flatMap(m=>rim(m,side,.11,.145)),bottom=footSkin.filter(m=>m.name==='base').flatMap(m=>rim(m,side,.09,.125));if(top.length<8||bottom.length<8)throw Error(`Missing ankle boundary ${side}: ${top.length}/${bottom.length}`);
  const g=new THREE.BufferGeometry(),positions=new Float32Array(5*97*3),indices=[];for(let j=0;j<4;j++)for(let i=0;i<96;i++){const a=j*97+i;indices.push(a,a+1,a+97,a+1,a+98,a+97)}g.setAttribute('position',new THREE.BufferAttribute(positions,3));g.setIndex(indices);const material=new THREE.MeshPhysicalMaterial({color:'#cfa98f',roughness:.68,side:THREE.DoubleSide,transparent:true});const m=new THREE.Mesh(g,material);m.frustumCulled=false;m.castShadow=true;m.receiveShadow=true;scene.add(m);seams.push({m,top,bottom,side});
 }
 function updateSeam(seam,alpha){
  function fit(samples){
   const pts=samples.map(({m,i})=>{const p=V([0,0,0]);m.getVertexPosition(i,p);return p.applyMatrix4(m.matrixWorld)});
   const lo=V([Infinity,Infinity,Infinity]),hi=V([-Infinity,-Infinity,-Infinity]);for(const p of pts){lo.min(p);hi.max(p)}
   const center=lo.clone().add(hi).multiplyScalar(.5);center.y=pts.reduce((n,p)=>n+p.y,0)/pts.length;
   let xx=0,xz=0,zz=0,xy=0,zy=0;for(const p of pts){const x=p.x-center.x,z=p.z-center.z,y=p.y-center.y;xx+=x*x;xz+=x*z;zz+=z*z;xy+=x*y;zy+=z*y}
   const det=xx*zz-xz*xz,dx=det?((xy*zz-zy*xz)/det):0,dz=det?((zy*xx-xy*xz)/det):0;
   return {center,rx:(hi.x-lo.x)*.5+.006,rz:(hi.z-lo.z)*.5+.006,dx,dz};
  }
  const a=fit(seam.bottom),b=fit(seam.top);a.center.y-=.009;b.center.y+=.018;
  const attr=seam.m.geometry.attributes.position;
  for(let j=0;j<5;j++)for(let i=0;i<=96;i++){
   const angle=-Math.PI+(i%96)*Math.PI*2/96,u=j/4,center=a.center.clone().lerp(b.center,u);
   const x=Math.cos(angle)*(a.rx+(b.rx-a.rx)*u),z=Math.sin(angle)*(a.rz+(b.rz-a.rz)*u);
   const y=center.y+x*(a.dx+(b.dx-a.dx)*u)+z*(a.dz+(b.dz-a.dz)*u);
   attr.setXYZ(j*97+i,center.x+x,y,center.z+z);
  }
  attr.needsUpdate=true;seam.m.geometry.computeVertexNormals();seam.m.material.opacity=alpha;seam.m.material.depthWrite=alpha>.98;seam.m.visible=alpha>.01;
 }

 mh.scale.setScalar(2.35);mh.updateMatrixWorld(true);
 const pivotRest=new Map();for(const side of ['R','L'])for(let digit=1;digit<=5;digit++)for(let joint=1;joint<=(digit===1?2:3);joint++){const b=F[`toe${digit}-${joint}${side}`];if(!b)throw Error('Missing individual toe joint');pivotRest.set(b,footRest.get(b).q.clone())}
 const contactY=.006,contacts=[],toeAngles=[],contactPoints=[];
 function minY(samples){let min=Infinity;for(const {m,i} of samples){m.getVertexPosition(i,temp);temp.applyMatrix4(m.matrixWorld);min=Math.min(min,temp.y)}return min}
 function update(t){
  restore(bodyRest);restore(footRest);body.position.y=0;body.updateMatrixWorld(true);mh.updateMatrixWorld(true);
  const move=Math.sin(Math.min(t,6)*.70-.8);B.Hips.position.set(0,79,0);B.Spine.rotation.y+=move*.07;body.updateMatrixWorld(true);worldP(F.root,B.Hips.getWorldPosition(V([0,0,0])).add(V([0,0,-.17])));
  for(const [side,s] of [['Right',-1],['Left',1]]){solve(B[side+'UpLeg'],B[side+'Leg'],B[side+'Foot'],V([s*.88,.17383,.03]),V([s*1.2,.8,1.2]));worldQ(B[side+'Foot'],Q().setFromAxisAngle(V([0,1,0]),s*.15).multiply(heroFootQ[side]))}
  const thighTwist=.14*ramp(t,25,28)*(1-ramp(t,30.5,33));
  const twistAxis=B.RightUpLeg.getWorldPosition(V([0,0,0])).sub(B.RightLeg.getWorldPosition(V([0,0,0]))).normalize();worldQ(B.RightUpLeg,Q().setFromAxisAngle(twistAxis,thighTwist).multiply(B.RightUpLeg.getWorldQuaternion(Q())));
  // A thigh roll also rolls its child shin. Re-solve the shin after that roll,
  // then pin the ankle, so the force-intent illustration cannot slide the foot.
  aim(B.RightLeg,B.RightFoot,V([-.88,.17383,.03]));worldP(B.RightFoot,V([-.88,.17383,.03]));worldQ(B.RightFoot,Q().setFromAxisAngle(V([0,1,0]),-.15).multiply(heroFootQ.Right));
  const act=t<6?move:t>31?Math.sin((t-31)*.7+3.4):Math.sin(3.4);
  solve(B.RightArm,B.RightForeArm,B.RightHand,V([-.30+.18*act,2.78+.12*act,.72]),V([-1.1,2.22,.6]));solve(B.LeftArm,B.LeftForeArm,B.LeftHand,V([1.17-.12*act,2.54+.12*act,.54]),V([.9,2.08,.3]));B.Head.rotation.y-=.18;body.updateMatrixWorld(true);
  for(const [side,suffix] of [['Right','R'],['Left','L']]){
   const up=F['upperleg01'+suffix],knee=F['lowerleg01'+suffix],ankle=F['foot'+suffix];
   worldP(up,B[side+'UpLeg'].getWorldPosition(V([0,0,0])));aim(up,knee,B[side+'Leg'].getWorldPosition(V([0,0,0])));if(suffix==='R')worldQ(up,Q().setFromAxisAngle(twistAxis,thighTwist).multiply(up.getWorldQuaternion(Q())));worldP(knee,B[side+'Leg'].getWorldPosition(V([0,0,0])));aim(knee,ankle,B[side+'Foot'].getWorldPosition(V([0,0,0])));worldP(ankle,B[side+'Foot'].getWorldPosition(V([0,0,0])));worldQ(ankle,Q().setFromAxisAngle(V([0,1,0]),suffix==='R'?-.15:.15).multiply(footQ[suffix]));
  }
  contacts.length=0;toeAngles.length=0;contactPoints.length=0;
  const flexAxis=V([1,0,0]).applyAxisAngle(V([0,1,0]),-.15);
  for(let digit=1;digit<=5;digit++){
   const grip=ramp(t,9.4+(digit-1)*.12,12.5+(digit-1)*.12),last=digit===1?2:3,base=F[`toe${digit}-1R`];
   function setBase(angle){base.quaternion.copy(pivotRest.get(base));base.updateWorldMatrix(false,true);worldQ(base,Q().setFromAxisAngle(flexAxis,angle).multiply(base.getWorldQuaternion(Q())));for(let j=2;j<=last;j++){const b=F[`toe${digit}-${j}R`];b.quaternion.copy(pivotRest.get(b));b.updateWorldMatrix(false,true);worldQ(b,Q().setFromAxisAngle(flexAxis,grip*(j===2?.36:.24)*(digit===1?.8:1)).multiply(b.getWorldQuaternion(Q())))}mh.updateMatrixWorld(true)}
   let lo=-.6,hi=.5;for(let j=0;j<15;j++){const a=(lo+hi)/2;setBase(a);if(minY(toeSamples[digit-1])>contactY)lo=a;else hi=a}const a=(lo+hi)/2;setBase(a);contacts.push(minY(toeSamples[digit-1]));toeAngles.push({digit,mtp:a,ip:grip*.36*(digit===1?.8:1),dip:last===3?grip*.24:0});
   let min=Infinity,pad=V([0,0,0]);for(const {m,i} of toeSamples[digit-1]){m.getVertexPosition(i,temp);temp.applyMatrix4(m.matrixWorld);if(temp.y<min){min=temp.y;pad.copy(temp)}}contactPoints.push(pad);
  }
  const footReveal=ramp(t,14,16)*(1-ramp(t,30.5,33)),legReveal=ramp(t,24.5,26.5)*(1-ramp(t,30.5,33));uniforms.leg.value=legReveal;uniforms.foot.value=footReveal*.98;
  for(const m of footSkin){m.material.opacity=1;m.material.depthWrite=footReveal<.1;m.visible=true}
  for(const item of anatomy){const a=item.foot?footReveal:legReveal;item.m.visible=a>.002;item.m.material.opacity=a;item.m.material.depthWrite=a>.95}
  body.updateMatrixWorld(true);mh.updateMatrixWorld(true);for(const seam of seams)updateSeam(seam,seam.side===-1?1-Math.max(footReveal,legReveal):1);
  return {t,contacts:[...contacts],toeAngles:[...toeAngles],thighTwist,footReveal,legReveal,heelMin:minY(heelSamples),toeSamples:toeSamples.map(a=>a.length),ankle:B.RightFoot.getWorldPosition(V([0,0,0])).toArray(),knee:B.RightLeg.getWorldPosition(V([0,0,0])).toArray(),hip:B.RightUpLeg.getWorldPosition(V([0,0,0])).toArray()};
 }
 draco.dispose();
 return {update,body,mh,B,F,anatomy,footSkin,inventory:{toeJoints:pivotRest.size,anatomyMeshes:anatomy.length,muscles:muscleParts.length,bones:boneParts.length},getToePoints:()=>contactPoints.map(p=>p.clone())};
}
