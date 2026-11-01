"""Assemble and verify the full fast montage; preserve the original movie."""
from pathlib import Path
import json,os,sys,argparse,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from videocut.codefilm import verify_manifest
from videocut.ffmpeg_tools import invoke_json
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--render',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--base',type=Path,required=True)
parser.add_argument('--reference-mix',type=Path,required=True)
args=parser.parse_args()
delivery=args.output.resolve();delivery.mkdir(parents=True,exist_ok=True)
manifest=args.render.resolve()/'render-manifest.json';verify_manifest(manifest);m=json.loads(manifest.read_text())
assert m['frames']==4100 and m['width']==1920 and m['height']==1080
film=Path(__file__).resolve().parents[1]
base=args.base.resolve();tl=json.loads((film/'data/timeline.json').read_text())
edit=json.loads((film/'montage-edit.json').read_text())
if hashlib.file_digest(base.open('rb'),'sha256').hexdigest()!=edit['base_video_sha256']:raise ValueError('Base movie changed')
final=delivery/'杭州-快节奏实景混剪.mp4'
if final.exists():raise ValueError('Use a new delivery directory')
candidate=delivery/'before-chapters.mp4'
p={'output':str(candidate),'clips':[{'src':c['file']} for c in m['chunks']],'transition':{'type':'none'},'audio':{'replace':str(base),'stereo':True},'export':{'preset':'copy'},'check':{'platform':'youtube','content':True}}
pf=delivery/'post-project.json';pf.write_text(json.dumps(p,ensure_ascii=False,indent=2))
for dry in [True,False]:
 invoke_json(['render',str(pf),*(['--dry-run'] if dry else []),'--json','--timeout','1800'],report=delivery/('post-plan.json' if dry else 'post-result.json'))
chapters=delivery/'chapters.txt'
chapters.write_text('\n'.join(f"{row['start']:.3f} {row['title']}" for row in tl['scenes'])+'\n')
invoke_json(['metadata',str(candidate),'--chapters',str(chapters),'-o',str(final),'--dry-run','--json'],report=delivery/'chapters-plan.json')
invoke_json(['metadata',str(candidate),'--chapters',str(chapters),'-o',str(final),'--json'],report=delivery/'chapters-result.json')
invoke_json(['check',str(final),'--platform','youtube','--content','--json'],report=delivery/'final-check.json')
for src,dst in [(manifest,delivery/'render-manifest.json'),((film/'data/timeline.json'),delivery/'timeline.json'),(args.reference_mix.resolve(),delivery/'mix.wav')]:
 if not dst.exists():os.link(src,dst)
import verify_delivery
verify_delivery.OUT=delivery;verify_delivery.main(final_name=final.name)
invoke_json(['look',str(final),'--tiles','4x3','--width','2560','-o',str(delivery/'混剪总览.png'),'--json-brief'],report=delivery/'look.json')
print(final,flush=True)
