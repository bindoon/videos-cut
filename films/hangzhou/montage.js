// The original city remains the spatial spine. Real photographs and footage
// enter on a separate Three.js plane; narration time never changes.
import * as THREE from 'three';
window.CITY_CLARITY=1.8;
await import('./main.js');
window.READY=false;
const cityRender=window.render;
const [EDIT,SOURCES]=await Promise.all(['montage-edit.json','data/montage/sources.json'].map(x=>fetch(x).then(r=>{if(!r.ok)throw Error(x);return r.json()})));
const W=innerWidth,H=innerHeight;
const canvas=document.createElement('canvas');document.body.append(canvas);
const renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:false,preserveDrawingBuffer:true});
renderer.setSize(W,H);renderer.setPixelRatio(1);renderer.outputColorSpace=THREE.SRGBColorSpace;
const scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(-1,1,1,-1,0,1);
const smooth=(a,b,x)=>{const u=Math.max(0,Math.min(1,(x-a)/(b-a)));return u*u*(3-2*u)};
const footage=new Map(),textures=new Map();
for(const source of SOURCES){
  let texture;
  if(source.file.endsWith('.webm')){
    const video=document.createElement('video');video.muted=true;video.preload='auto';video.playsInline=true;
    const ready=new Promise((resolve,reject)=>{video.addEventListener('loadeddata',resolve,{once:true});video.addEventListener('error',()=>reject(Error('Cannot decode '+source.file)),{once:true})});
    video.src='./data/montage/'+source.file;video.load();await ready;
    const surface=document.createElement('canvas');surface.width=video.videoWidth;surface.height=video.videoHeight;
    const ctx=surface.getContext('2d');ctx.drawImage(video,0,0);texture=new THREE.CanvasTexture(surface);
    footage.set(source.id,{video,surface,ctx});
  }else{
    texture=await new THREE.TextureLoader().loadAsync('./data/montage/'+source.file);
  }
  texture.colorSpace=THREE.SRGBColorSpace;texture.minFilter=THREE.LinearFilter;texture.magFilter=THREE.LinearFilter;
  textures.set(source.id,texture);
}
const mat=new THREE.ShaderMaterial({transparent:true,depthTest:false,depthWrite:false,
  uniforms:{image:{value:textures.get('westlake')},imageAspect:{value:1.777},frameAspect:{value:W/H},alpha:{value:0},phase:{value:0},direction:{value:1},entry:{value:0},wipe:{value:0},split:{value:0}},
  vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}',
  fragmentShader:`uniform sampler2D image;uniform float imageAspect,frameAspect,alpha,phase,direction,entry,wipe,split;varying vec2 vUv;
  void main(){
    vec2 coord=vUv;coord.x=mix(vUv.x,(vUv.x-.64)/.36,split);
    float aspect=frameAspect*mix(1.,.36,split);
    vec2 cover=vec2(min(1.,aspect/imageAspect),min(1.,imageAspect/aspect));
    float zoom=1.06+.13*phase;
    vec2 uv=(coord-.5)*cover/zoom+.5;
    uv.x+=direction*(phase-.5)*.055;uv.y+=(phase-.5)*.009;
    vec4 col=texture2D(image,uv);
    float edge=smoothstep(0.,.72,1.-vUv.y);
    float vig=1.-.22*pow(length((vUv-.5)*vec2(1.,.82)),1.3);
    col.rgb*=vig;
    col.rgb=mix(col.rgb,col.rgb*vec3(.84,.92,1.),.12);
    float mask=mix(1.,1.-smoothstep(entry*1.5-.25,entry*1.5+.12,vUv.x),wipe);
    float beam=exp(-pow((vUv.x-(entry*1.5-.25))*24.,2.))*wipe*(1.-smoothstep(.65,1.,entry));
    col.rgb+=vec3(1.,.73,.38)*beam*.15;
    gl_FragColor=vec4(col.rgb,alpha*mask*mix(1.,smoothstep(.63,.65,vUv.x),split));
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }`});
scene.add(new THREE.Mesh(new THREE.PlaneGeometry(2,2),mat));
const hud=document.createElement('canvas');hud.width=W;hud.height=H;document.body.append(hud);const g=hud.getContext('2d');
function text(s,x,y,size=22,color='#eee9df',weight=400,align='left'){
  g.font=`${weight} ${size}px "Noto Sans SC",sans-serif`;g.textAlign=align;g.fillStyle=color;g.fillText(s,x,y);
}
async function seekVideo(source,time){
  const item=footage.get(source);if(!item)return;
  const t=Math.min(item.video.duration-.08,Math.max(.001,time));
  if(Math.abs(item.video.currentTime-t)>1e-5){
    await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{item.video.removeEventListener('seeked',done);reject(Error('Video seek timed out'))},10000);
      function done(){clearTimeout(timer);resolve()}
      item.video.addEventListener('seeked',done,{once:true});item.video.currentTime=t;
    });
  }
  item.ctx.drawImage(item.video,0,0);textures.get(source).needsUpdate=true;
}
function drawCredits(t){
  const p=smooth(0,.7,t);g.globalAlpha=p;
  g.fillStyle='#071019';g.fillRect(48,156,1824,730);
  text('杭州 · 山水与城市的年轮',90,223,40,'#f4dfb7',300);
  text('真实城市数据 × Three.js × 开放实拍素材',92,267,23,'#b5c6d0');
  const used=new Set(EDIT.shots.map(s=>s.asset));const names=[...new Set(SOURCES.filter(s=>used.has(s.id)).map(s=>s.author).filter(Boolean))];
  const rows=[];for(let i=0;i<names.length;i+=3)rows.push(names.slice(i,i+3).join(' / '));
  rows.forEach((row,i)=>text(row,94,326+i*38,19,'#c0ccd4'));
  text('素材：Wikimedia Commons · 已裁切、调色、运镜与混剪；完整条目见随片素材来源.md',94,687,21,'#aebec8');
  text('本混剪版：CC BY-SA 4.0 · creativecommons.org/licenses/by-sa/4.0/',94,733,22,'#cbd8de');
  text('建筑 CMAB · 水系 © OpenStreetMap contributors · 创作参考 Eian《一座城的年轮》',94,783,20,'#8fa4b1');
  text('配音：语音合成 · 配乐与转场：代码制作',94,830,20,'#8fa4b1');g.globalAlpha=1;
}
window.render=async t=>{
  const slot=EDIT.shots.find(s=>s.at<=t&&t<s.until);
  if(!slot){cityRender(t);document.querySelector('#hud').style.opacity=1;mat.uniforms.alpha.value=0;renderer.render(scene,camera);g.setTransform(1,0,0,1,0,0);g.clearRect(0,0,W,H);return;}
  const local=Math.max(0,Math.min(slot.end-slot.start-1e-7,t-slot.at)),sourceTime=slot.at+local;
  cityRender(sourceTime);
  g.setTransform(W/1920,0,0,H/1080,0,0);g.clearRect(0,0,1920,1080);
  if(slot.asset==='credits'){
    document.querySelector('#hud').style.opacity=0;
    mat.uniforms.alpha.value=0;renderer.render(scene,camera);drawCredits(local);
  }else{
    const source=SOURCES.find(x=>x.id===slot.asset),length=slot.end-slot.start;
    const enter=smooth(0,.16,local),leave=1-smooth(length-.16,length,local),alpha=enter*leave;
    // Retire the map's titles before introducing the location title. Keeping
    // both title sets at half opacity creates unreadable ghost text.
    const split=slot.effect==='split';const oldHud=split?1:1-smooth(0,.16,local)*(1-smooth(length-.16,length,local));
    document.querySelector('#hud').style.opacity=oldHud;
    await seekVideo(slot.asset,(slot.from||0)+local);
    mat.uniforms.split.value=slot.effect==='split'?1:0;
    mat.uniforms.image.value=textures.get(slot.asset);mat.uniforms.imageAspect.value=source.width/source.height;
    mat.uniforms.phase.value=local/length;mat.uniforms.direction.value=slot.direction||1;
    mat.uniforms.alpha.value=alpha;mat.uniforms.entry.value=enter;mat.uniforms.wipe.value=slot.transition==='light'?1:0;
    renderer.render(scene,camera);
    g.globalAlpha=alpha;
    const top=g.createLinearGradient(0,0,0,300);top.addColorStop(0,'rgba(2,8,13,.74)');top.addColorStop(1,'rgba(2,8,13,0)');g.fillStyle=top;g.fillRect(split?1220:0,0,split?700:1920,300);
    const bottom=g.createLinearGradient(0,790,0,1080);bottom.addColorStop(0,'rgba(2,8,13,0)');bottom.addColorStop(1,'rgba(2,8,13,.96)');g.fillStyle=bottom;g.fillRect(0,790,1920,290);
    g.globalAlpha=smooth(.05,.18,local)*(1-smooth(length-.18,length-.05,local));
    text(split?'实景 · 景点一瞥':'H A N G Z H O U  /  山水实景',split?1260:74,66,20,'#d0dce2',400);
    g.fillStyle='#e0bc77';g.fillRect(split?1230:76,100,4,53);
    text(slot.label,split?1250:98,139,split?28:41,'#f6efdf',500);
    text(slot.note||'今日实景',split?1250:99,180,18,'#c3d0d5');
    text(`${source.author} · ${source.license} · Wikimedia Commons`,74,1047,15,'#9cafbb');
    text('实拍素材 × Three.js 运镜',1846,1047,15,'#9cafbb',400,'right');
    const cue=window.TL.cues.find(c=>c.start<=sourceTime&&sourceTime<c.end);
    if(cue){
      g.globalAlpha=1;
      g.font='500 31px "Noto Sans SC",sans-serif';const cw=g.measureText(cue.text).width;g.font='300 18px "Noto Sans SC",sans-serif';const ew=g.measureText(cue.en).width;
      const plate=Math.min(1770,Math.max(cw,ew)+52);g.fillStyle='rgba(2,6,10,.86)';g.beginPath();g.roundRect(960-plate/2,941,plate,87,10);g.fill();
      g.shadowColor='rgba(0,0,0,.95)';g.shadowBlur=8;
      text(cue.text,960,978,31,'#f1f2ed',500,'center');text(cue.en,960,1012,18,'#c1cbd3',300,'center');g.shadowBlur=0;
    }
    g.globalAlpha=1;
  }
  window.FRAME_STATE={t,sourceTime,asset:slot.asset,local,original:window.FRAME_STATE};
};
window.DUR=EDIT.duration;await window.render(0);window.READY=true;
