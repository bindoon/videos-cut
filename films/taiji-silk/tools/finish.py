"""Join the complete 864-frame render, add original audio, verify the actual file."""
import json
import sys
from pathlib import Path

from videocut.codefilm import verify_manifest
from videocut.ffmpeg_tools import invoke_json

out = Path(sys.argv[1]).resolve()
manifest = out / 'render-manifest.json'
verify_manifest(manifest)
doc = json.loads(manifest.read_text())
assert (doc['frames'], doc['width'], doc['height'], doc['fps']) == (864, 1920, 1080, 24)
project = {
    'output': str(out / 'final.mp4'),
    'clips': [{'src': c['file']} for c in doc['chunks']],
    'transition': {'type': 'none'},
    'audio': {'replace': str(out / 'soundtrack.wav'), 'stereo': True},
    'loudness': {'lufs': -20, 'tp': -2},
    'export': {'preset': 'copy'},
    'check': {'platform': 'custom', 'content': True},
}
config = out / 'post-project.json'
config.write_text(json.dumps(project, ensure_ascii=False, indent=2))
invoke_json(['render', str(config), '--dry-run', '--json'], report=out / 'post-plan.json')
invoke_json(['render', str(config), '--work', str(out / 'post-work'), '--json'], report=out / 'post-report.json')
report = verify_manifest(manifest, video=out / 'final.mp4')
(out / 'delivery-verification.json').write_text(json.dumps(report, indent=2))
invoke_json(['probe', str(out / 'final.mp4'), '--json'], report=out / 'final-probe.json')
invoke_json(['check', str(out / 'final.mp4'), '--platform', 'custom', '--aspect', '16:9',
             '--max-duration', '37', '--lufs', '-20', '--tp', '-2', '--content', '--json'],
            report=out / 'delivery-check.json')
invoke_json(['look', str(out / 'final.mp4'), '--tiles', '4x2', '--width', '2560', '--no-timecode',
             '-o', str(out / 'contact-sheet.png'), '--json'], report=out / 'look-report.json')
invoke_json(['look', str(out / 'final.mp4'), '--at', '19', '--width', '1920', '--no-timecode',
             '-o', str(out / 'root-detail.png'), '--json'], report=out / 'detail-report.json')
print(out / 'final.mp4')
