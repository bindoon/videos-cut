// Real CMAB roofs → indexed massing geometry. Physical scale is 1:10,000.
// Postprocessing derives from LemoLab (MIT); see vendor/lemo/LICENSE.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { makePost } from './vendor/lemo/post.js';

export function makeCity(W, H, M) {
  const renderer = new THREE.WebGLRenderer({antialias:false,preserveDrawingBuffer:true});
  renderer.setPixelRatio(1);renderer.setSize(W,H);
  renderer.toneMapping=THREE.NeutralToneMapping;renderer.toneMappingExposure=1;
  renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.shadowMap.autoUpdate=false;
  document.querySelector('#stage').appendChild(renderer.domElement);
  const scene=new THREE.Scene();scene.background=new THREE.Color('#070a0f');
  const camera=new THREE.PerspectiveCamera(32,W/H,.0008,20);
  const pm=new THREE.PMREMGenerator(renderer);scene.environment=pm.fromScene(new RoomEnvironment(),.025).texture;
  scene.environmentIntensity=.12;
  const post=makePost(renderer,scene,camera,W,H,{ssaa:1,ao:true,aoRadius:.006,aoScale:1.2,aoThickness:.003,aoAmt:.50});
  post.bloom.strength=.44;post.bloom.radius=.55;post.bloom.threshold=.84;
  post.vig.uniforms.amt.value=.48;
  const key=new THREE.DirectionalLight('#e8eef6',2.35);key.position.set(-1.4,2.4,1.5);key.castShadow=true;
  key.shadow.mapSize.set(4096,4096);Object.assign(key.shadow.camera,{left:-1.7,right:1.7,top:1.7,bottom:-1.7,near:.1,far:7});
  key.shadow.bias=-.000015;key.shadow.normalBias=.00012;key.shadow.radius=3;
  scene.add(key,key.target);
  const fill=new THREE.HemisphereLight('#dae8ff','#1d2430',.20);scene.add(fill);
  const rim=new THREE.DirectionalLight('#8ca5c7',.35);rim.position.set(1.4,.8,-1.7);scene.add(rim);
  const U={uLight:{value:0},uMode:{value:0},uT:{value:0},uProgress:{value:0},uCentre:{value:new THREE.Vector2()},uAccent:{value:new THREE.Color('#ffc47e')},uMap:{value:null},uSize:{value:new THREE.Vector2(...M.size)}};
  const map=document.createElement('canvas');map.width=map.height=2048;const ctx=map.getContext('2d');
  ctx.fillStyle='#000';ctx.fillRect(0,0,2048,2048);
  const coord=([x,z])=>[(x/M.size[0]+.5)*2048,(z/M.size[1]+.5)*2048];
  for(const p of M.water){ctx.beginPath();for(const r of p.rings){r.forEach((a,i)=>{const q=coord(a);i?ctx.lineTo(...q):ctx.moveTo(...q)});ctx.closePath()}
    // Red = all water; green = West Lake. River/canal inlays remain data.
    ctx.fillStyle=p.name==='西湖'?'#ffff00':'#ff0000';ctx.fill('evenodd');}
  ctx.globalCompositeOperation='lighter';
  for(const r of M.routes){if(!['river','canal'].includes(r.kind))continue;ctx.beginPath();r.points.forEach((p,i)=>i?ctx.lineTo(...coord(p)):ctx.moveTo(...coord(p)));ctx.lineWidth=r.kind==='canal'?5:2;ctx.strokeStyle='#0000ff';ctx.stroke()}
  const tex=new THREE.CanvasTexture(map);tex.flipY=false;tex.colorSpace=THREE.NoColorSpace;tex.anisotropy=8;U.uMap.value=tex;
  const head=`uniform float uLight,uMode,uT,uProgress;uniform vec2 uCentre,uSize;uniform vec3 uAccent;uniform sampler2D uMap;
    varying vec3 vWorld,vNorm;varying float vHeight;
    vec3 projected(){
      vec2 p=vWorld.xz,uv=p/uSize+.5;vec3 water=texture2D(uMap,uv).rgb;
      vec2 d=p-uCentre;float r=length(d);float phase=uMode;
      float radius=.06+uProgress*.5;
      float mask=1.-smoothstep(radius-.05,radius+.07,r);
      float wave=exp(-pow((r-radius)/.018,2.));
      float grid=(1.-smoothstep(.0003,.0012,abs(fract(p.x*100.+.5)-.5)/100.))+(1.-smoothstep(.0003,.0012,abs(fract(p.y*100.+.5)-.5)/100.));
      vec3 col=uAccent*(mask*.55+wave*.5);
      if(phase>1.5&&phase<2.5){mask=max(water.b*.8,exp(-pow((p.x-uCentre.x)/.10,2.))*.35);col=uAccent*mask*(.6+.4*sin(p.y*45.+uT*2.));}
      if(phase>3.5&&phase<4.5){col=uAccent*water.g*.9+vec3(.1,.45,.6)*water.r*.18;}
      if(phase>4.5&&phase<5.5){mask=(1.-smoothstep(.14,.25,abs(d.x)))*(1.-smoothstep(.25,.45,abs(d.y)));col=uAccent*mask*(.40+grid*.18);}
      if(phase>5.5&&phase<6.5){col=uAccent*mask*.45+vec3(.08,.35,.4)*water.g*.55;}
      if(phase>6.5&&phase<8.5){float sweep=smoothstep(-.40,.65,p.x)*smoothstep(.02,.60,uProgress);col=mix(vec3(.06,.20,.28),uAccent,sweep)*(.18+mask*.52);col+=uAccent*water.r*.22;}
      if(phase>8.5&&phase<9.5){col=vec3(.16,.52,.58)*water.g*.9+vec3(.25,.35,.68)*water.b*.6+uAccent*mask*.12;}
      if(phase>9.5&&phase<10.5){float h=clamp(vHeight/180.,0.,1.);col=mix(vec3(.15,.2,.65),vec3(.95,.66,.32),h)*(.3+mask*.6);}
      if(phase>10.5){float rip=pow(.5+.5*cos(r*105.-uProgress*8.),14.);col=mix(vec3(.16,.36,.48),uAccent,clamp(r*1.4,0.,1.))*(.18+rip*.38)*smoothstep(0.,.2,uProgress);}
      float facing=.48+.52*max(dot(normalize(vNorm),normalize(vec3(-.5,2.,.4)-vWorld)),0.);
      return col*facing*uLight;
    }`;
  function material(ground=false){const m=new THREE.MeshStandardMaterial({color:'#f1f2ef',roughness:.90,metalness:0});
    m.onBeforeCompile=s=>{Object.assign(s.uniforms,U);
      s.vertexShader=s.vertexShader.replace('#include <common>','#include <common>\nattribute float aHeight;varying vec3 vWorld,vNorm;varying float vHeight;').replace('#include <fog_vertex>','#include <fog_vertex>\nvWorld=(modelMatrix*vec4(transformed,1.)).xyz;vNorm=normalize(mat3(modelMatrix)*objectNormal);vHeight=aHeight;');
      s.fragmentShader=s.fragmentShader.replace('#include <common>','#include <common>\n'+head);
      if(ground)s.fragmentShader=s.fragmentShader.replace('#include <color_fragment>','#include <color_fragment>\nvec2 uv0=vWorld.xz/uSize+.5;float wm=texture2D(uMap,uv0).r;diffuseColor.rgb=mix(diffuseColor.rgb,vec3(.045,.09,.125),wm);');
      s.fragmentShader=s.fragmentShader.replace('#include <opaque_fragment>',`outgoingLight+=projected()*${ground?'.26':'1.6'};\n#include <opaque_fragment>`);};
    m.customProgramCacheKey=()=>ground?'hz-ground':'hz-city';return m;}

  // Separate vertices at wall corners preserve crisp white-model edges.
  const positions=[],normals=[],heights=[],indices=[];
  function vertex(p,n,h){const i=positions.length/3;positions.push(...p);normals.push(...n);heights.push(h);return i;}
  for(const [h,,,,,rs] of M.buildings){const y=h/10000;
    for(let ri=0;ri<rs.length;ri++){const r=rs[ri];let area=0;for(let i=0;i<r.length;i++){const a=r[i],b=r[(i+1)%r.length];area+=a[0]*b[1]-b[0]*a[1]}
      const sign=(area>0?1:-1)*(ri?-1:1);
      for(let j=0;j<r.length;j++){const [x0,z0]=r[j],[x1,z1]=r[(j+1)%r.length];const dx=x1-x0,dz=z1-z0,l=Math.hypot(dx,dz);if(l<1e-8)continue;
        const n=[dz/l*sign,0,-dx/l*sign];const a=vertex([x0,0,z0],n,h),b=vertex([x1,0,z1],n,h),c=vertex([x1,y,z1],n,h),d=vertex([x0,y,z0],n,h);
        const cx=-dz*y,cz=dx*y;if(cx*n[0]+cz*n[2]>0)indices.push(a,b,c,a,c,d);else indices.push(a,c,b,a,d,c);}}
    const outer=rs[0].map(p=>new THREE.Vector2(...p)),holes=rs.slice(1).map(r=>r.map(p=>new THREE.Vector2(...p))),all=outer.concat(...holes),off=positions.length/3;
    for(const p of all)vertex([p.x,y,p.y],[0,1,0],h);
    for(const [a,b,c] of THREE.ShapeUtils.triangulateShape(outer,holes)){const p=all[a],q=all[b],r=all[c];if((q.y-p.y)*(r.x-p.x)-(q.x-p.x)*(r.y-p.y)>0)indices.push(off+a,off+b,off+c);else indices.push(off+a,off+c,off+b);}}
  const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geo.setAttribute('normal',new THREE.Float32BufferAttribute(normals,3));geo.setAttribute('aHeight',new THREE.Float32BufferAttribute(heights,1));geo.setIndex(indices);geo.computeBoundingSphere();
  const city=new THREE.Mesh(geo,material());city.castShadow=city.receiveShadow=true;scene.add(city);
  const plane=new THREE.PlaneGeometry(M.size[0],M.size[1]).rotateX(-Math.PI/2);plane.setAttribute('aHeight',new THREE.Float32BufferAttribute(new Float32Array(plane.attributes.position.count),1));
  const plate=new THREE.Mesh(plane,material(true));plate.receiveShadow=true;plate.position.y=-.00002;scene.add(plate);
  const base=new THREE.Mesh(new THREE.BoxGeometry(M.size[0]+.016,.018,M.size[1]+.016),new THREE.MeshStandardMaterial({color:'#444c56',roughness:.6}));base.position.y=-.0095;scene.add(base);
  const routes=new THREE.Group();scene.add(routes);
  for(const r of M.routes){if(!(['canal','causeway'].includes(r.kind)||r.name.includes('苏堤')||r.bridge==='yes'))continue;
    const g=new THREE.BufferGeometry().setFromPoints(r.points.map(([x,z])=>new THREE.Vector3(x,.0008,z)));
    const m=new THREE.LineBasicMaterial({color:r.kind==='canal'?'#83ecff':'#ffe2a6',transparent:true,opacity:0,depthTest:false});const l=new THREE.Line(g,m);l.userData=r;routes.add(l);}
  renderer.shadowMap.needsUpdate=true;
  return {renderer,scene,camera,post,key,fill,rim,U,routes,geometry:geo};
}
