"""An original modal score, bells and water-like air, synthesized in code.

No downloaded recording or generative music model is used. Every musical
section and lighting hit shares the film's measured narration timeline.
"""
from __future__ import annotations

from paths import output_directory
import json
import pathlib
import wave
import numpy as np
from scipy.signal import butter, sosfilt

ROOT=pathlib.Path(__file__).resolve().parents[3]
OUT = None
SR=48000


def main():
    tl=json.loads((OUT/"timeline.json").read_text())
    n=round(tl["duration"]*SR)
    music=np.zeros((n,2),np.float32)
    fx=np.zeros_like(music)
    rng=np.random.default_rng(48120)
    cues=[]

    def add(buf,sound,t,gain=1,pan=0):
        start=round(t*SR)
        if start<0:return
        length=min(len(sound),len(buf)-start)
        if length<=0:return
        sound=sound[:length]*gain
        buf[start:start+length,0]+=sound*np.sqrt((1-pan)/2)
        buf[start:start+length,1]+=sound*np.sqrt((1+pan)/2)

    def pluck(midi,length=3,bright=.7):
        t=np.arange(round(length*SR))/SR;f=440*2**((midi-69)/12)
        y=np.zeros_like(t)
        for k in range(1,11):
            y+=np.sin(2*np.pi*f*k*(1+.00012*k*k)*t)*np.exp(-t*(1.2+k*.42))/k**(1.25+.4*(1-bright))
        y*=np.minimum(1,t/.008)*np.exp(-t*.20)
        return y.astype(np.float32)*.35

    def bell(midi,length=4):
        t=np.arange(round(length*SR))/SR;f=440*2**((midi-69)/12)
        y=sum(np.sin(2*np.pi*f*r*t)*a*np.exp(-t*d) for r,a,d in [(1,1,1.4),(2.76,.27,2.4),(5.41,.1,4.5)])
        return (y*np.minimum(1,t/.004)*.3).astype(np.float32)

    def pad(notes,length):
        t=np.arange(round(length*SR))/SR;y=np.zeros_like(t)
        for note in notes:
            f=440*2**((note-69)/12)
            y+=(np.sin(2*np.pi*f*t)+.22*np.sin(2*np.pi*f*2.002*t)+.12*np.sin(2*np.pi*f*3*t))/len(notes)
        env=np.minimum(1,t/1.8)*np.minimum(1,(length-t)/2)
        return (y*env*.22).astype(np.float32)

    # D major pentatonic, with contrasting relative-minor/added-note voicings.
    chords=[[50,57,64],[47,54,62],[43,50,57],[45,52,59]]
    pent=[62,64,66,69,71,74,76,78]
    for i,s in enumerate(tl["scenes"]):
        start,end=s["start"],s["end"]
        chord=chords[i%4]
        add(music,pad(chord,end-start+2),start,.56 if i<6 else .72,-.12)
        # Alternate sparse flowing plucks with a little more forward motion
        # as the city opens to the river; the last chapter resolves to D.
        beat=60/(78 if i<7 else 86)
        step=beat*(1.0 if i<7 else .75)
        for j,at in enumerate(np.arange(start+.7,end-.4,step)):
            if i in [0,3,9] and j%2:continue
            degree=[0,2,4,1,3,5,4,2][j%8]
            note=pent[(degree+i%3)%len(pent)]
            add(music,pluck(note,2.7),float(at),.22 if j%4 else .30,.50*np.sin(j*1.7+i))
        if i>0:
            hit=bell(62+(i%3)*5)
            add(fx,hit,start,.38,-.12)
            cues.append({"time":start,"event":"chapter-light-change","scene":s["id"]})
        if i in [5,7,10]:
            t=np.arange(round(2.7*SR))/SR
            impact=np.sin(2*np.pi*(52*t+22*(1-np.exp(-t*4))))*np.exp(-t*2.7)
            add(fx,impact.astype(np.float32),start,.25)
        # Very quiet band-limited air is a designed room/projector bed.
        length=end-start
        air=rng.normal(0,1,round(length*SR)).astype(np.float32)
        air=sosfilt(butter(2,[380,2100],fs=SR,btype="bandpass",output="sos"),air)
        fade=np.minimum(1,np.arange(len(air))/SR/.6)*np.minimum(1,(len(air)-np.arange(len(air)))/SR/.6)
        add(fx,(air*fade*.012).astype(np.float32),start,.45,0)
    # A final open fifth and ninth, allowed to ring under the end card.
    for at,note in [(tl["scenes"][-1]["start"]+.4,62),(tl["duration"]-6.5,69),(tl["duration"]-5.7,76)]:
        add(music,bell(note,5.6),at,.40)
    with wave.open(str(OUT/"narration.wav"),"rb") as r:
        voice=np.frombuffer(r.readframes(r.getnframes()),dtype='<i2').astype(np.float32)/32768
    voice=np.pad(voice[:n],(0,max(0,n-len(voice))))
    voice=sosfilt(butter(2,65,fs=SR,btype="highpass",output="sos"),voice).astype(np.float32)
    voice=np.tanh(voice*2.1)
    active=np.abs(voice)>.006
    rms=np.sqrt(np.mean(voice[active]**2))
    voice*=.145/max(rms,.001)
    # Envelope uses authored PCM cue intervals; no unrelated ASR gate.
    env=np.zeros(n,np.float32)
    for c in tl["cues"]:
        a=max(0,round((c['start']-.18)*SR));b=min(n,round((c['end']+.28)*SR));env[a:b]=1
    env=sosfilt(butter(1,3,fs=SR,output="sos"),env).astype(np.float32)
    music*=((1-.47*env)*.17)[:,None]
    fx*=.15
    fade=np.minimum(1,np.arange(n)/SR/1.0)*np.minimum(1,(n-np.arange(n))/SR/2.4)
    music*=fade[:,None];fx*=fade[:,None]
    mix=voice[:,None]*np.ones((1,2),np.float32)/np.sqrt(2)+music+fx
    peak=float(np.max(np.abs(mix)))
    if peak>.94:mix*=.94/peak

    def write(name,x):
        with wave.open(str(OUT/name),'wb') as w:
            w.setparams((2,2,SR,0,'NONE','not compressed'));w.writeframes(np.clip(x*32767,-32768,32767).astype('<i2').tobytes())
    write('music.wav',music);write('effects.wav',fx);write('mix.wav',mix)
    (OUT/'audio-score.json').write_text(json.dumps({'sample_rate':SR,'duration':n/SR,'score':'Original D-pentatonic modal synthesis, plucked harmonics, inharmonic bells, low impact and filtered air','seed':48120,'external_music_models':False,'external_recordings':False,'peak_before_final_master':float(np.max(np.abs(mix))),'cues':cues},ensure_ascii=False,indent=2))
    print('AUDIO MIX',n/SR,'seconds, stereo 48kHz PCM16',flush=True)


if __name__ == '__main__':
    OUT = output_directory(protect_delivery=True)
    main()
