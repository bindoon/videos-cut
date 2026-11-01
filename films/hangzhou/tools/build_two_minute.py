"""Build an exactly two-minute PCM timeline from reviewed reference-voice speech."""
import json,hashlib,wave,shutil,argparse
from pathlib import Path
import numpy as np
import librosa
root=Path(__file__).resolve().parents[3];film=root/'films/hangzhou'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--story',type=Path,default=film/'story-two-minute.json');parser.add_argument('--speech-manifest',type=Path);args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
if (out/'narration.wav').exists():raise ValueError('Narration exists; choose a new output directory')
story=json.loads(args.story.read_text());speech_manifest=args.speech_manifest or out/'speech/index-manifest.json';manifest=json.loads(speech_manifest.read_text());records={r['text']:r for r in manifest['utterances']};lines=[line for s in story['scenes'] for line in s['lines']];assert len(records)==len(lines)==24
sr=48000;target=120*sr;prepared=[];logs=[]
for text,en in lines:
 r=records[text];p=Path(r['path']);assert hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==r['sha256']
 with wave.open(str(p),'rb') as w:
  assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(1,2,sr);y=np.frombuffer(w.readframes(w.getnframes()),'<i2').astype(np.float32)/32768
 # Remove only quiet outer padding, with a generous 120ms guard.
 window=960;power=np.array([np.sqrt(np.mean(y[i:i+window]**2)) for i in range(0,len(y),window)]);active=np.where(power>.003)[0];assert len(active)
 a=max(0,int(active[0]*window-.12*sr));b=min(len(y),int((active[-1]+1)*window+.12*sr));prepared.append(y[a:b]);logs.append({'text':text,'source':str(p),'sha256':r['sha256'],'trim_samples':[a,b]})
# Keep normal cadence unless speech exceeds the available 109 seconds.
rate=max(1.,sum(map(len,prepared))/(109*sr));assert rate<=1.35,rate
if rate>1:prepared=[librosa.effects.time_stretch(y,rate=rate).astype(np.float32) for y in prepared]
intro=round(1.0*sr);tail=round(3.5*sr);between=round(.16*sr);available=target-sum(map(len,prepared))-intro-tail-12*between;assert available>=0
chapter_gaps=[available//11+(i<available%11) for i in range(11)]
segments=[];cues=[];scenes=[];pieces=[np.zeros(intro,np.float32)];cursor=intro
for si,s in enumerate(story['scenes']):
 start=0 if si==0 else cursor/sr
 for li,(text,en) in enumerate(s['lines']):
  idx=si*2+li;y=prepared[idx];a=cursor/sr;pieces.append(y);cursor+=len(y);cues.append({'start':round(a,3),'end':round(cursor/sr,3),'text':text,'en':en,'scene':s['id']});logs[idx].update({'start_sample':round(a*sr),'samples':len(y),'pitch_preserving_speed':rate})
  if li==0:pieces.append(np.zeros(between,np.float32));cursor+=between
 if si<11:pieces.append(np.zeros(chapter_gaps[si],np.float32));cursor+=chapter_gaps[si]
 else:pieces.append(np.zeros(tail,np.float32));cursor+=tail
 scenes.append({**s,'start':start,'end':cursor/sr})
y=np.concatenate(pieces);assert len(y)==target==cursor
with wave.open(str(out/'narration.wav'),'wb') as w:w.setparams((1,2,sr,0,'NONE','not compressed'));w.writeframes(np.clip(y*32767,-32768,32767).astype('<i2').tobytes())
tl={'title':story['title'],'subtitle':story['subtitle'],'fps':24,'frames':2880,'duration':120.,'voice':'qianchen','provider':'IndexTTS-2.5','caption_method':'Authored utterance PCM sample counts after guarded outer-silence trim and optional pitch-preserving time stretch; explicit audio_clip intervals','scenes':scenes,'cues':cues}
for p in [out/'timeline.json',film/'data/timeline.json']:p.write_text(json.dumps(tl,ensure_ascii=False,indent=2)+'\n')
def srt_time(seconds):
 value=round(seconds*1000);hours,value=divmod(value,3600000);minutes,value=divmod(value,60000);seconds,millis=divmod(value,1000);return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"
(out/'captions.srt').write_text('\n\n'.join(f"{i+1}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n{c['text']}" for i,c in enumerate(cues))+'\n')
(out/'narration-timing.json').write_text(json.dumps({'reference_manifest':str(root/'assets/voices/qianchen/manifest.json'),'original_generation_manifest':str(speech_manifest),'time_stretch_rate':rate,'duration':120,'utterances':logs},ensure_ascii=False,indent=2)+'\n')
assets=['extra-12','extra-13','tangxi','extra-19','sudi','scroll','historic','qianjiang','bridge','extra-26','night','extra-16'];labels=['西湖','西湖东岸','京杭大运河 · 塘栖','雷峰塔','苏堤','南宋 · 西湖图卷','近代杭州','钱江新城','钱塘江大桥','良渚古城遗址','钱江新城夜景','杭州山水']
shots=[]
for i,(asset,label) in enumerate(zip(assets,labels)):
 cue=cues[i*2+(0 if i in [2,9,10] else 1)];length=min(1.5,cue['end']-cue['start']-.2);at=round((cue['start']+.35)*24)/24;until=round((at+length)*24)/24
 shots.append({'id':f'aux-{i:02}','at':at,'until':until,'start':at,'end':until,'asset':asset,'label':label,'note':'南宋绘画' if asset=='scroll' else ('20世纪前期 · 资料影像' if asset=='historic' else '今日实景'),'from':4 if asset=='tangxi' else 0,'direction':(-1)**i,'transition':'light' if i%3==0 else 'dissolve','effect':'full' if i in [0,4,5,7] else 'split'})
# A short attribution card follows the last spoken line, preserving the ending city movement.
a=round((cues[-1]['end']+.35)*24)/24;shots.append({'id':'credits','at':a,'until':120.,'start':a,'end':120.,'asset':'credits','label':'素材署名'})
edit={'title':'杭州 · 城市年轮 · 钱陈音色两分钟版','fps':24,'frames':2880,'duration':120.,'source_duration':120.,'mode':'threejs_primary_two_minutes','shots':shots,'scenes':scenes,'primary_visual':'Three.js city and historical light layers','reference_voice':'qianchen'}
(film/'montage-edit.json').write_text(json.dumps(edit,ensure_ascii=False,indent=2)+'\n');(out/'montage-edit.json').write_text(json.dumps(edit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'duration':120,'voice_rate':rate,'auxiliary_seconds':sum(s['until']-s['at'] for s in shots if s['asset']!='credits'),'shots':len(shots)}),flush=True)

media=[s for s in shots if s['asset']!='credits'];credit=shots[-1]['until']-shots[-1]['at'];aux=sum(s['until']-s['at'] for s in media);full_city=120-aux-credit
assert len({s['asset'] for s in media})==len(media)==12
assert all(s['until']-s['at']<=1.6 for s in media)
assert full_city/120>=.8
for a,b in zip(shots,shots[1:]):assert a['until']<=b['at']
(out/'editorial-check.json').write_text(json.dumps({'passed':True,'target_seconds':120,'frames':2880,'full_threejs_seconds':full_city,'full_threejs_fraction':full_city/120,'auxiliary_seconds':aux,'auxiliary_assets':12,'asset_reuse_count':0,'max_auxiliary_shot_seconds':max(s['until']-s['at'] for s in media),'credits_seconds':credit},indent=2)+'\n')
