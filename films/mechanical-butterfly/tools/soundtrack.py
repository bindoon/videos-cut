"""Original deterministic stereo synthesis; no samples, speech, or remote API."""
import array
import math
import random
import sys
import wave
from pathlib import Path

RATE=48000
DURATION=26
rng=random.Random(104)
out=Path(sys.argv[1])
out.parent.mkdir(parents=True,exist_ok=True)
data=array.array('h')
frequencies=(146.832,220.0,293.665,349.228,440.0)
events=(0.8,4,8,9.5,12,16,17.6,20,21.8,24)
for i in range(RATE*DURATION):
    t=i/RATE
    envelope=min(1,t/1.5)*min(1,(26-t)/1.6)
    phase=t*2.4*.25*2*math.pi
    motor=.012*math.sin(2*math.pi*72*t)*(0.6+0.4*math.cos(phase)**2)
    flutter=.014*(rng.random()*2-1)*(0.15+0.85*max(0,math.sin(phase))**5)
    pad=sum(.014*math.sin(2*math.pi*f*t+.3*math.sin(t*.5+k)) for k,f in enumerate(frequencies))
    bass=.032*math.sin(2*math.pi*73.416*t)*(0.7+.3*math.sin(t*.4))
    sparkle=0
    for e in events:
        d=t-e
        if 0<=d<1.5:
            sparkle+=.05*math.exp(-d*5)*math.sin(2*math.pi*(880*d+60*d*d))
        if 0<=d<.12:
            sparkle+=.035*math.exp(-d*55)*(rng.random()*2-1)
    left=(pad+bass+motor+flutter+sparkle)*envelope
    right=(pad+bass+motor-flutter*.4+sparkle*.8)*envelope
    data.extend((int(max(-1,min(1,left))*32767),int(max(-1,min(1,right))*32767)))
if sys.byteorder!='little':data.byteswap()
with wave.open(str(out),'wb') as stream:
    stream.setnchannels(2);stream.setsampwidth(2);stream.setframerate(RATE);stream.writeframes(data.tobytes())
print(out)
