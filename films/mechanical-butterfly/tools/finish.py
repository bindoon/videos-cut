"""Join checked codefilm segments and add the original soundtrack via project tools."""
import json
import subprocess
import sys
from pathlib import Path

out=Path(sys.argv[1]).resolve()
manifest=out/'render-manifest.json'

def run(name,args):
    result=subprocess.run([sys.executable,'-m','videocut.ffmpeg_tools',*args,'--json'],capture_output=True,text=True)
    (out/f'{name}.json').write_text(result.stdout)
    (out/f'{name}.stderr.log').write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f'{name}: {result.stdout}\n{result.stderr}')
    return json.loads(result.stdout)

subprocess.run([sys.executable,'-m','videocut.codefilm','verify',str(manifest),'--report',str(out/'frame-verification.json')],check=True)
doc=json.loads(manifest.read_text())
parts=out/'parts.txt'
parts.write_text(''.join(str(Path(c['file']).resolve())+'\n' for c in doc['chunks']))
join=['join','--list',str(parts),'--transition','none','-o',str(out/'silent-master.mp4')]
run('join-plan',join+['--dry-run'])
run('join-report',join)
audio=['audio',str(out/'silent-master.mp4'),'--replace',str(out/'soundtrack-master.wav'),'-o',str(out/'final.mp4')]
run('mux-plan',audio+['--dry-run'])
run('mux-report',audio)
subprocess.run([sys.executable,'-m','videocut.codefilm','verify',str(manifest),'--video',str(out/'final.mp4'),'--report',str(out/'delivery-verification.json')],check=True)
run('delivery-check',['check',str(out/'final.mp4'),'--platform','custom','--aspect','16:9','--max-duration','30','--lufs','-18','--tp','-2','--content'])
run('contact-sheet-report',['look',str(out/'final.mp4'),'--tiles','4x2','--width','1920','-o',str(out/'contact-sheet.png')])
print(out/'final.mp4')
