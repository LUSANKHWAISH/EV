"""Verify the cinematic source boundary and save a reproducible asset manifest."""
import argparse
import difflib
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
EVIDENCE=ROOT/'evidence'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir',default='')
    args=parser.parse_args()
    destination=EVIDENCE/args.output_dir
    destination.mkdir(parents=True,exist_ok=True)
    baseline=json.loads((EVIDENCE/'source_baseline.json').read_text())
    changed=[];unchanged=0
    for name,old in baseline['files'].items():
        path=PROJECT/name;new=sha(path) if path.exists() else None
        if new==old:unchanged+=1
        else:changed.append({'path':name,'before':old,'after':new})
    # The default-interface follow-up also extends the GUI launch regression tests.
    allowed={'gui\\app.py','tests\\test_gui_app.py'}
    report={'utc':datetime.now(timezone.utc).isoformat(),'baseline_head':baseline['head'],
            'protected_files':len(baseline['files']),'unchanged':unchanged,'changed':changed,
            'unexpected_changes':[row for row in changed if row['path'] not in allowed]}
    before=(EVIDENCE/'gui_app_before.py.txt').read_text(encoding='utf-8')
    after=(PROJECT/'gui/app.py').read_text(encoding='utf-8')
    patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/gui/app.py',tofile='b/gui/app.py'))
    (destination/'gui_app_overnight.patch').write_text(patch,encoding='utf-8')
    files=[p for p in ROOT.rglob('*') if p.is_file() and 'evidence' not in p.relative_to(ROOT).parts and '__pycache__' not in p.parts]
    files += [PROJECT/'Launch Cinematic Preview.cmd',PROJECT/'Launch Cinematic EV.cmd',PROJECT/'gui/app.py',PROJECT/'docs/plans/2026-09-16-cinematic-nucleus.md',PROJECT/'docs/reports/2026-09-16-cinematic-nucleus.md']
    files += [PROJECT/'Launch EV.cmd',PROJECT/'Launch Classic EV.cmd',PROJECT/'tests/test_gui_app.py',PROJECT/'docs/reports/2026-09-16-fire-gold-refresh.md']
    files += [PROJECT/'docs/plans/2026-09-16-core-flow-and-projection.md',PROJECT/'docs/reports/2026-09-16-core-flow-and-projection.md']
    files += [PROJECT/'docs/plans/2026-09-16-shape-shift.md',PROJECT/'docs/reports/2026-09-16-shape-shift.md']
    files += [PROJECT/'docs/plans/2026-09-16-core-reaction-motion.md',PROJECT/'docs/reports/2026-09-16-core-reaction-motion.md']
    files += [PROJECT/'docs/plans/2026-09-16-fire-energy-restore.md',PROJECT/'docs/reports/2026-09-16-fire-energy-restore.md']
    manifest={str(p.relative_to(PROJECT)):sha(p) for p in sorted(files)}
    (destination/'source_manifest.json').write_text(json.dumps(manifest,indent=2))
    report['source_manifest_sha256']=sha(destination/'source_manifest.json')
    (destination/'source_audit.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    return 1 if report['unexpected_changes'] else 0

if __name__=='__main__':raise SystemExit(main())
