#!/usr/bin/env python3
"""Sequential development gates. Real hold-out-dependent checks wait for freeze.
No reuse of old slow-test hashes after changing person matching or highlight.py.
"""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def implementation():
 paths=set()
 for folder in ['skills/basketball-highlight-editor/scripts','skills/basketball-highlight-editor/tests','experiments/attribution','robustness']:
  paths.update((ROOT/folder).rglob('*.py'))
 return {str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(paths)}

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'work/goal-4/validation');p.add_argument('--slow',action='store_true');p.add_argument('--node',default='node');a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
 try:a.output.relative_to(ROOT)
 except ValueError:p.error('--output must be inside this repository (normally work/goal-4/)')
 frozen=implementation()
 py=sys.executable
 jobs=[('manifest',[py,'experiments/detection/gates.py','--job','release','--write-manifest']),
 ('behavior',[py,'-m','unittest','discover','-s','skills/basketball-highlight-editor/tests','-v']),
 ('attribution',[py,'-m','unittest','discover','-s','experiments/attribution/tests','-v']),
 ('evaluation-development',[py,'experiments/detection/gates.py','--job','eval']),
 ('robustness',[py,'-m','unittest','discover','-s','robustness/tests','-v']),
 ('detection-research',[py,'-m','unittest','discover','-s','experiments/detection/tests','-v']),
 ('review-form',[a.node,'scripts/test_review_form.js','examples/indiana/project/review.html']),
 ('replay',[py,'scripts/replay_case.py','--output',str(a.output/'replay')])]
 if a.slow:jobs += [
 ('full-matrix',[py,'robustness/matrix.py','--suite','full','--include-long','--generated','work/goal-2/full-variants','--output',str(a.output/'matrix')]),
 ('people-matrix',[py,'robustness/people_matrix.py','--generated','work/goal-2/full-variants','--output',str(a.output/'people')]),
 ('performance',[py,'robustness/performance.py','--source','work/goal-2/performance-1080/phone-60min-1080p30-audio.mp4','--output',str(a.output/'performance')])]
 else:jobs += [('smoke-matrix',[py,'robustness/matrix.py','--suite','smoke','--generated','work/goal-3/gate-variants','--output',str(a.output/'matrix')])]
 rows=[];env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
 for name,cmd in jobs:
  begin=time.monotonic();print('START',name,flush=True)
  with (a.output/(name+'.log')).open('w') as log:
   try:r=subprocess.run(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=3600 if name in ('full-matrix','people-matrix','performance') else 180);code=r.returncode
   except subprocess.TimeoutExpired:code=124
  row={'name':name,'returncode':code,'seconds':round(time.monotonic()-begin,3),'log':str((a.output/(name+'.log')).relative_to(ROOT))};rows.append(row)
  unchanged=implementation()==frozen
  report={'scope':'sequential development gates; one real-corpus holdout-reading unit deferred; full verification after freeze','all_passed':unchanged and all(x['returncode']==0 for x in rows),'code_unchanged_during_run':unchanged,'jobs':rows,'implementation':frozen}
  (a.output/'results.json').write_text(json.dumps(report,indent=2)+'\n');print('END',name,code,row['seconds'],flush=True)
  if code:return code
  if not unchanged:raise RuntimeError('CODE_CHANGED_DURING_VALIDATION: restart in a new output directory')
 return 0
if __name__=='__main__':sys.exit(main())
