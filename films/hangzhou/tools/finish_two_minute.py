"""Publish a new 120-second, Three.js-primary film with the cached reference voice."""
from pathlib import Path
import os,sys,json,hashlib,shutil,argparse
root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root));sys.path.insert(0,str(root/'films/hangzhou/tools'))
from videocut.codefilm import verify_manifest
from videocut.ffmpeg_tools import invoke_json
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--render',type=Path);parser.add_argument('--delivery',type=Path);args=parser.parse_args();out=args.output.resolve();delivery=(args.delivery or out/'delivery').resolve();delivery.mkdir(parents=True,exist_ok=True)
manifest=(args.render or out/'render').resolve()/'render-manifest.json';verify_manifest(manifest);m=json.loads(manifest.read_text());assert m['frames']==2880
candidate=delivery/'candidate-before-chapters.mp4';final=delivery/'杭州-城市年轮-钱陈音色-两分钟.mp4';tl=json.loads((out/'timeline.json').read_text())
if final.exists():raise ValueError('Existing delivery; choose a new directory')
p={'output':str(candidate),'clips':[{'src':c['file']} for c in m['chunks']],'transition':{'type':'none'},'audio':{'replace':str(out/'mix.wav'),'stereo':True},'loudness':{'lufs':-14,'tp':-1.8},'export':{'preset':'copy'},'check':{'platform':'youtube','content':True}}
pf=delivery/'post-project.json';pf.write_text(json.dumps(p,ensure_ascii=False,indent=2))
for dry in [True,False]:invoke_json(['render',str(pf),*(['--dry-run'] if dry else []),'--json','--timeout','1800'],report=delivery/('post-plan.json' if dry else 'post-result.json'))
chapters=delivery/'chapters.txt';chapters.write_text('\n'.join(f"{s['start']:.3f} {s['title']}" for s in tl['scenes'])+'\n')
for dry in [True,False]:invoke_json(['metadata',str(candidate),'--chapters',str(chapters),'-o',str(final),*(['--dry-run'] if dry else []),'--json'],report=delivery/('chapters-plan.json' if dry else 'chapters-result.json'))
invoke_json(['check',str(final),'--platform','youtube','--content','--json'],report=delivery/'final-check.json')
for src,dst in [(manifest,delivery/'render-manifest.json'),(out/'timeline.json',delivery/'timeline.json'),(out/'mix.wav',delivery/'mix.wav')]:
 if not dst.exists():os.link(src,dst)
import verify_delivery
verify_delivery.OUT=delivery;verify_delivery.main(final_name=final.name,expected_frames=2880,expected_cues=24,audio_times=(6,20,35,50,65,80,95,110,115))
report=json.loads((delivery/'verification.json').read_text());report['voice']={'provider':'IndexTTS-2.5','name':'钱陈','reference_sha256':json.loads((root/'assets/voices/qianchen/manifest.json').read_text())['sha256'],'narration_timing':json.loads((out/'narration-timing.json').read_text())};report['editorial']={'threejs_primary':True,'unique_media_once_each':True,'target_seconds':120,'auxiliary_windows':12};(delivery/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
invoke_json(['look',str(final),'--tiles','4x3','--width','2560','-o',str(delivery/'画面总览.png'),'--json-brief'],report=delivery/'look.json')
for name in ['captions.srt','editorial-check.json']:
 shutil.copy2(out/name,delivery/name)
shutil.copy2(root/'films/hangzhou/MONTAGE-CREDITS.md',delivery/'素材来源.md')
print(final,flush=True)
