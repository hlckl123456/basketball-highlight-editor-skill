#!/usr/bin/env python3
"""Iteration gates with explicit hold-out deferral, no scoring-logic changes."""
import argparse,json,os,runpy,subprocess,sys,unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from policy import ROOT,install_holdout_guard,verify_prior_slow_evidence
DEFERRED='test_corpus.CorpusSafety.test_all_automatic_real_annotations_are_draft'

def flatten(suite):
 for item in suite:
  if isinstance(item,unittest.TestSuite):yield from flatten(item)
  else:yield item

def evaluation_units():
 install_holdout_guard(None);sys.path.insert(0,str(ROOT))
 suite=unittest.defaultTestLoader.discover(str(ROOT/'eval/tests'))
 selected=[];deferred=[]
 for case in flatten(suite):
  if case.id()==DEFERRED:deferred.append(case.id())
  else:selected.append(case)
 assert len(deferred)==1,'Expected one real-corpus hold-out-reading test'
 print('DEFERRED UNTIL FINAL FREEZE:',json.dumps(deferred),flush=True)
 result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(selected))
 return int(not result.wasSuccessful())

def main():
 p=argparse.ArgumentParser();p.add_argument('--job',choices=['release','eval']);p.add_argument('--write-manifest',action='store_true');p.add_argument('--output',type=Path);p.add_argument('--python',default=sys.executable);a=p.parse_args()
 if a.job=='eval':return evaluation_units()
 if a.job=='release':
  install_holdout_guard(None);sys.argv=['verify_release.py','--development-only']+(['--write-manifest'] if a.write_manifest else [])
  runpy.run_path(str(ROOT/'scripts/verify_release.py'),run_name='__main__');return 0
 slow_evidence=verify_prior_slow_evidence()
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);python=a.python;env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
 def command(name,args):
  log=out/(name+'.log')
  with log.open('w') as stream:
   r=subprocess.run([str(v) for v in args],cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=900)
  return {'name':name,'returncode':r.returncode,'log':str(log.relative_to(ROOT))}
 first=command('manifest',[python,__file__,'--job','release','--write-manifest']);assert first['returncode']==0,'Development release manifest check failed'
 node=os.environ.get('GOAL3_NODE','node')
 jobs=[('release',[python,__file__,'--job','release']),('behavior',[python,'-m','unittest','discover','-s','skills/basketball-highlight-editor/tests','-v']),('evaluation',[python,__file__,'--job','eval']),('robustness',[python,'-m','unittest','discover','-s','robustness/tests','-v']),('research',[python,'-m','unittest','discover','-s','experiments/detection/tests','-v']),('review-form',[node,'scripts/test_review_form.js','examples/indiana/project/review.html']),('replay',[python,'scripts/replay_case.py','--output',out/'replay']),('input-smoke',[python,'robustness/matrix.py','--suite','smoke','--generated',ROOT/'work/goal-3/gate-variants','--output',out/'matrix'])]
 with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(lambda job:command(*job),jobs))
 report={'verified_prior_slow_code':slow_evidence,'scope':'development only; one real-corpus label-reading test deferred until final freeze; optional full matrix and performance covered by unchanged goal-2 code hashes','jobs':[first,*rows],'all_passed':all(r['returncode']==0 for r in rows),'deferred_real_corpus_test':DEFERRED}
 (out/'results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return int(not report['all_passed'])

if __name__=='__main__':sys.exit(main())
