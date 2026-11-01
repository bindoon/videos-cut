"""Original, deterministic pentatonic plucks and breath-like ambience. No samples."""
import array
import math
import random
import sys
import wave
from pathlib import Path

RATE = 48000
DURATION = 36
rng = random.Random(20261031)
notes = [(0, 146.832), (3, 220), (6, 293.665), (9, 329.628),
         (12, 440), (14, 146.832), (16, 220), (18, 293.665),
         (20, 164.814), (22.5, 329.628), (25, 220), (27, 440),
         (29, 293.665), (31, 146.832), (33, 220)]
out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
data = array.array('h')
air = 0
for i in range(RATE * DURATION):
    t = i / RATE
    air = air * .985 + (rng.random() * 2 - 1) * .015
    env = min(1, t / 1.5) * min(1, (DURATION - t) / 2.4)
    drone = .021 * math.sin(2 * math.pi * 73.416 * t)
    drone += .012 * math.sin(2 * math.pi * 110 * t + .25 * math.sin(t * .4))
    left = right = drone + .035 * air * (.7 + .3 * math.sin(t * .8))
    for n, (at, freq) in enumerate(notes):
        d = t - at
        if not 0 <= d < 5:
            continue
        pluck = (1 - math.exp(-d * 85)) * math.exp(-d * 1.15)
        tone = sum(math.sin(2 * math.pi * freq * h * d) / h ** 2.1 for h in range(1, 6))
        tone *= .10 * pluck
        pan = .25 * math.sin(n * 1.6)
        left += tone * (.8 + pan)
        right += tone * (.8 - pan)
        # Short, quiet delayed reflection.
        if d > .19:
            echo = .018 * math.exp(-(d - .19) * 1.8) * math.sin(2 * math.pi * freq * (d - .19))
            right += echo
    data.extend((int(max(-1, min(1, left * env)) * 32767),
                 int(max(-1, min(1, right * env)) * 32767)))
if sys.byteorder != 'little':
    data.byteswap()
with wave.open(str(out), 'wb') as stream:
    stream.setnchannels(2)
    stream.setsampwidth(2)
    stream.setframerate(RATE)
    stream.writeframes(data.tobytes())
print(out)
