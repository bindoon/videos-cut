import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';

const scene=new THREE.Scene();scene.background=new THREE.Color('#eae6de');
const camera=new THREE.PerspectiveCamera(34,innerWidth/innerHeight,.05,60);
const renderer=new THREE.WebGLRenderer({canvas:document.querySelector('#scene'),antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(1);renderer.setSize(innerWidth,innerHeight);renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.08;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
const pmrem=new THREE.PMREMGenerator(renderer),room=new RoomEnvironment();scene.environment=pmrem.fromScene(room,.04).texture;room.dispose();pmrem.dispose();scene.environmentIntensity=.45;
scene.add(new THREE.HemisphereLight('#ffffff','#8d9c91',1.6));
const key=new THREE.DirectionalLight('#fff0d7',3.1);key.position.set(-3,7,5);key.castShadow=true;key.shadow.mapSize.set(2048,2048);Object.assign(key.shadow.camera,{left:-4,right:4,top:5,bottom:-3,near:.1,far:20});key.shadow.bias=-.0002;key.shadow.normalBias=.015;scene.add(key);
const fill=new THREE.DirectionalLight('#c2dde5',1.4);fill.position.set(4,3,-3);scene.add(fill);
const ground=new THREE.Mesh(new THREE.PlaneGeometry(200,200),new THREE.MeshStandardMaterial({color:'#ddd8cc',roughness:1}));ground.rotation.x=-Math.PI/2;ground.receiveShadow=true;scene.add(ground);
const gltf=await new GLTFLoader().loadAsync('./models/man-base/man-base-character-rigged.glb');
const model=gltf.scene;scene.add(model);model.scale.setScalar(2.35);
const bones={};model.traverse(o=>{if(o.isBone)bones[o.name]=o;if(o.isMesh){o.castShadow=true;o.receiveShadow=true;o.material.side=THREE.FrontSide}});
model.updateMatrixWorld(true);
const rest=new Map(Object.values(bones).map(b=>[b,{p:b.position.clone(),q:b.quaternion.clone(),s:b.scale.clone()}]));
const footSamples=[];
model.traverse(o=>{if(!o.isSkinnedMesh)return;const ids=new Set(o.skeleton.bones.map((b,i)=>/^(Right|Left)(Foot|ToeBase)$/.test(b.name)?i:-1));const joints=o.geometry.attributes.skinIndex,weights=o.geometry.attributes.skinWeight;for(let i=0;i<joints.count;i+=3){let w=0;for(let j=0;j<4;j++)if(ids.has(joints.getComponent(i,j)))w+=weights.getComponent(i,j);if(w>.6)footSamples.push([o,i])}});
const V=a=>new THREE.Vector3(...a),clamp=x=>Math.max(0,Math.min(1,x)),smooth=x=>{x=clamp(x);return x*x*(3-2*x)};
function reset(){model.position.y=0;for(const [b,r] of rest){b.position.copy(r.p);b.quaternion.copy(r.q);b.scale.copy(r.s)}model.updateMatrixWorld(true)}
function worldQ(b,q){const parent=b.parent.getWorldQuaternion(new THREE.Quaternion());b.quaternion.copy(parent.invert().multiply(q));model.updateMatrixWorld(true)}
function aim(b,child,target){
 const p=b.getWorldPosition(new THREE.Vector3()),c=child.getWorldPosition(new THREE.Vector3());
 const delta=new THREE.Quaternion().setFromUnitVectors(c.sub(p).normalize(),target.clone().sub(p).normalize());
 worldQ(b,delta.multiply(b.getWorldQuaternion(new THREE.Quaternion())));
}
function solve(upper,lower,end,target,pole){
 const a=upper.getWorldPosition(new THREE.Vector3()),b=lower.getWorldPosition(new THREE.Vector3()),c=end.getWorldPosition(new THREE.Vector3());
 const l1=a.distanceTo(b),l2=b.distanceTo(c),dir=target.clone().sub(a),dist=Math.min(dir.length(),l1+l2-.0001);dir.normalize();
 const along=(l1*l1+dist*dist-l2*l2)/(2*dist),height=Math.sqrt(Math.max(0,l1*l1-along*along));
 const bend=pole.clone().sub(a);bend.addScaledVector(dir,-bend.dot(dir)).normalize();
 const knee=a.clone().addScaledVector(dir,along).addScaledVector(bend,height);
 aim(upper,lower,knee);aim(lower,end,target);
}
const footQ={};for(const side of ['Right','Left'])footQ[side]=bones[side+'Foot'].getWorldQuaternion(new THREE.Quaternion());
function pose(t){
 reset();const wave=Math.sin(t*.85-.8);
 bones.Hips.position.set(0,79,0);bones.Spine.rotation.y+=wave*.07;model.updateMatrixWorld(true);
 for(const [side,sgn] of [['Right',-1],['Left',1]]){
  solve(bones[side+'UpLeg'],bones[side+'Leg'],bones[side+'Foot'],V([sgn*.88,.20,.03]),V([sgn*1.2,.8,1.2]));
  const q=new THREE.Quaternion().setFromAxisAngle(V([0,1,0]),sgn*.15).multiply(footQ[side]);worldQ(bones[side+'Foot'],q);
 }
 solve(bones.RightArm,bones.RightForeArm,bones.RightHand,V([-.30+.15*wave,2.78+.10*wave,.72]),V([-1.1,2.22,.6]));
 solve(bones.LeftArm,bones.LeftForeArm,bones.LeftHand,V([1.17-.10*wave,2.54+.12*wave,.54]),V([.9,2.08,.30]));
 // This asset has hand bones but no finger joints; retain its natural hand mesh.
 bones.RightHand.quaternion.copy(rest.get(bones.RightHand).q).multiply(new THREE.Quaternion().setFromAxisAngle(V([0,1,0]),-.2));
 bones.LeftHand.quaternion.copy(rest.get(bones.LeftHand).q).multiply(new THREE.Quaternion().setFromAxisAngle(V([0,1,0]),.2));
 bones.Head.rotation.y-=.18;model.updateMatrixWorld(true);
 let min=Infinity;const v=new THREE.Vector3();for(const [m,i] of footSamples){m.getVertexPosition(i,v);v.applyMatrix4(m.matrixWorld);min=Math.min(min,v.y)}
 model.position.y=.004-min;model.updateMatrixWorld(true);
}
const hud=document.querySelector('#hud'),ctx=hud.getContext('2d');
function text(s,x,y,size,color='#24464a',weight=400){ctx.fillStyle=color;ctx.font=`${weight} ${size}px "Noto Sans SC",sans-serif`;ctx.fillText(s,x,y)}
function draw(t){
 pose(t);const u=smooth((t-3)/1.7);
 camera.position.copy(V([5.0,3.6,8.3]).lerp(V([2.2,3.35,4.2]),u));camera.lookAt(V([-.35,1.75,0]).lerp(V([-.05,2.67,.05]),u));camera.updateProjectionMatrix();renderer.render(scene,camera);
 hud.width=innerWidth;hud.height=innerHeight;ctx.setTransform(innerWidth/1920,0,0,innerHeight/1080,0,0);
 text('太 极 · 模 型 试 装',78,82,25,'#24464a',500);text('TAIJI / CHARACTER STUDY',78,115,13,'#7b8780');
 text('更自然的人物',78,260,45,'#24464a',500);text('真实比例 · 皮肤与服装贴图 · 骨骼蒙皮',80,310,21,'#6e7b74');
 text(t<3?'全身动作测试':'面部与上身细节',80,399,24,'#a17d41');
 text('外部 GLB 模型载入 / 太极姿态适配',80,932,20,'#6e7b74');
 text('试装素材：训练便服；尚未制作太极服与逐趾控制。',80,973,17,'#7b8780');
 window.MODEL_STUDY={t,bones:Object.keys(bones),animations:gltf.animations.map(a=>a.name),loaded:true,footSamples:footSamples.length};
}
await document.fonts.ready;await document.fonts.load('500 24px "Noto Sans SC"');
window.render=async t=>draw(t);draw(0);window.READY=true;
