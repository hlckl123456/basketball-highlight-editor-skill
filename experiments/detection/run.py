#!/usr/bin/env python3
"""Recall-first, fail-closed development experiments; no ground truth creation.
Unscorable trials cannot win. Each rejection restores the bootstrap Git commit.
"""
import argparse,csv,importlib.util,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
from policy import ROOT,assert_immutable,better,catalog,install_holdout_guard,meets,sha
import trial_candidate
BINDING=ROOT/'experiments/detection/trial_candidate.py'
COLUMNS=['round','name','hypothesis','recall','precision','f1','roi_accuracy','confirmed_made_shots','reviewed_seconds','prediction_events','gates','decision','reason']

def write(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def command(args,log,timeout=1200):
 log.parent.mkdir(parents=True,exist_ok=True)
 with log.open('w') as out:r=subprocess.run([str(x) for x in args],cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=out,stderr=subprocess.STDOUT,timeout=timeout)
 return r.returncode

def ledger(rows):
 path=ROOT/'eval/results.tsv'
 with path.open('w',newline='') as stream:
  w=csv.DictWriter(stream,fieldnames=COLUMNS,delimiter='\t');w.writeheader()
  for row in rows:w.writerow({k:('NA' if row.get(k) is None else row.get(k,'')) for k in COLUMNS})

def history():
 with (ROOT/'eval/results.tsv').open() as stream:return list(csv.DictReader(stream,delimiter='\t'))

def generate(cfg,out,scans):
 import engine
 output=[];total=0
 for v in catalog()['videos']:
  if v['split']!='development':continue
  raw=json.loads((scans/(v['id']+'.json')).read_text());assert raw['video_sha256']==v['sha256']
  proposal=engine.propose(raw['records'],v['duration'],v['evaluation_ranges'],cfg)
  for roi in proposal['rois']:
   w,h=raw['width'],raw['height'];x1,y1,x2,y2=roi['roi_xyxy'];roi['roi_xyxy']=[max(0,min(w,x1)),max(0,min(h,y1)),max(0,min(w,x2)),max(0,min(h,y2))]
  write(out/'proposals'/(v['id']+'.json'),{'video_id':v['id'],'video_sha256':v['sha256'],'not_ground_truth':True,'config':cfg,**proposal})
  pred={'schema_version':1,'document_type':'basketball_predictions','video_id':v['id'],'video_sha256':v['sha256'],
        'provenance':{'method':'unpromoted research candidate; no labels used','parameters':cfg,'status':'draft','model_sha256':raw['model_sha256'],'binding_sha256':sha(BINDING)},
        'events':[{'id':'research%06d'%i,'kind':'detected_event','time':e['time'],'status':'draft','player_assignments':[]} for i,e in enumerate(proposal['events'])]}
  write(out/'predictions'/(v['id']+'.json'),pred);total+=len(pred['events'])
  output.append({'video_id':v['id'],'events':len(pred['events']),'roi_proposals':len(proposal['rois']),'review_windows':len(proposal['review_windows']),'failure':proposal.get('failure')})
 write(out/'proposal-summary.json',{'status':'draft','ground_truth_used':False,'development_only':True,'videos':output,'predictions':total})
 return total

def score(predictions,out):
 code=command([sys.executable,ROOT/'experiments/detection/score_dev.py','--predictions',predictions,'--output',out],out.with_suffix('.log'))
 if code:raise RuntimeError('Development score refused')
 return json.loads(out.read_text())

def safe_reset(base):
 branch=subprocess.check_output(['git','symbolic-ref','--short','HEAD'],cwd=ROOT,text=True).strip()
 changed=set(subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT,text=True).splitlines())
 allowed={'experiments/detection/trial_candidate.py','eval/results.tsv','MANIFEST.sha256'}
 if branch!='goal-3-detection' or not changed<=allowed:raise RuntimeError('UNRELATED_CHANGES: refuse destructive reset')
 assert_immutable()
 subprocess.run(['git','reset','--hard',base],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'work/goal-3/run');p.add_argument('--scans',type=Path,default=ROOT/'work/goal-3/scans');p.add_argument('--base',required=True);a=p.parse_args()
 root=a.output.resolve();root.mkdir(parents=True,exist_ok=True)
 assert subprocess.check_output(['git','symbolic-ref','--short','HEAD'],cwd=ROOT,text=True).strip()=='goal-3-detection'
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==a.base
 assert not (root/'finalized.json').exists(),'Study is frozen: never tune after final evaluation'
 denied=install_holdout_guard(root);assert_immutable();original=BINDING.read_text();base_cfg=dict(trial_candidate.CONFIG)
 plans=json.loads((ROOT/'experiments/detection/plans.json').read_text());baseline=json.loads((ROOT/'docs/reports/goal-3/baseline.json').read_text())['splits']['development']
 best=dict(baseline['metrics']);rows=[{'round':0,'name':'production_baseline','hypothesis':'Frozen production predictions before any experiment','recall':best['event_recall'],'precision':best['event_precision'],'f1':best['event_f1'],'roi_accuracy':None,'confirmed_made_shots':baseline['counts']['confirmed_positive_events'],'reviewed_seconds':baseline['reviewed_seconds'],'prediction_events':sum(len(json.loads((ROOT/'eval/predictions'/(v['id']+'.json')).read_text())['events']) for v in catalog()['videos'] if v['split']=='development'),'gates':'goal-2 already complete','decision':'baseline','reason':'No human-confirmed shot labels or reviewed intervals'}]
 ledger(rows);write(root/'history.json',rows)
 controlled=root/'control';generate(base_cfg,controlled,a.scans);score(controlled/'predictions',controlled/'score.json')
 stale=0
 for plan in plans:
  previous=history();assert len(previous)==len(rows),'History was not read/restored correctly'
  assert_immutable();cfg={**base_cfg,**plan['change']};trial=root/('round-%02d'%plan['id']);trial.mkdir(exist_ok=True)
  write(trial/'hypothesis.json',{'plan':plan,'before_code_sha256':sha(BINDING),'best_metrics_before':best,'roi_accuracy':None,'no_roi_truth':True})
  BINDING.write_text(re.sub(r'^CONFIG = .*$',lambda _: 'CONFIG = '+repr(cfg),original,flags=re.MULTILINE))
  patch=subprocess.check_output(['git','diff','--','experiments/detection/trial_candidate.py'],cwd=ROOT)
  (trial/'candidate.patch').write_bytes(patch);started=time.perf_counter();count=generate(cfg,trial,a.scans)
  gate=command([sys.executable,ROOT/'experiments/detection/gates.py','--output',trial/'gates','--python',sys.executable],trial/'gates-run.log',timeout=1800)
  if gate==0:
   result=score(trial/'predictions',trial/'score.json');dev=result['splits']['development'];assert not result['holdout_evaluated']
  else:
   dev={'metrics':{**best,'event_recall':None,'event_precision':None,'event_f1':None},'counts':baseline['counts'],'reviewed_seconds':baseline['reviewed_seconds']}
   write(trial/'score-skipped.json',{'status':'gate_failed_not_scored','reason':'No metric computed from failed code'})
  m=dev['metrics']
  wins=gate==0 and better(m,best);reason=('No confirmed made-shot truth/reviewed ranges: event metrics unavailable; cannot rank or promote' if m['event_recall'] is None or m['event_precision'] is None else 'Recall-first score did not exceed best')
  if gate!=0:reason='Gate failure; score not run; restore previous code'
  row={'round':plan['id'],'name':plan['name'],'hypothesis':plan['hypothesis'],'recall':m['event_recall'],'precision':m['event_precision'],'f1':m['event_f1'],'roi_accuracy':None,'confirmed_made_shots':dev['counts']['confirmed_positive_events'],'reviewed_seconds':dev['reviewed_seconds'],'prediction_events':count,'gates':'passed' if gate==0 else 'failed','decision':'accepted' if wins else 'rejected','reason':'Improved confirmed-label metrics' if wins else reason}
  write(trial/'decision.json',{**row,'seconds':time.perf_counter()-started,'all_outputs_are_draft':True,'code_patch_sha256':sha(trial/'candidate.patch')})
  assert_immutable()
  if wins:
   rows.append(row);ledger(rows)
   subprocess.run(['git','add','experiments/detection/trial_candidate.py','eval/results.tsv','MANIFEST.sha256'],cwd=ROOT,check=True)
   subprocess.run(['git','commit','-m',f"Detection R={m['event_recall']:.3f} P={m['event_precision']:.3f}: {plan['name']}"],cwd=ROOT,check=True)
   a.base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();best=dict(m);stale=0
  else:
   if subprocess.check_output(['git','symbolic-ref','--short','HEAD'],cwd=ROOT,text=True).strip()!='goal-3-detection':raise RuntimeError('Refuse reset outside experiment branch')
   safe_reset(a.base)
   rows.append(row);ledger(rows);stale+=1
  write(root/'history.json',rows);write(root/'state.json',{'completed_rounds':len(rows)-1,'no_improvement_rounds':stale,'best_metrics':best,'accepted_rounds':sum(r['decision']=='accepted' for r in rows),'holdout_denied_accesses':denied})
  print(f"ROUND {plan['id']:02d} {row['decision']} gates={row['gates']} predictions={count} R={m['event_recall']} P={m['event_precision']} stale={stale}",flush=True)
  if meets(best,None) or stale>=15:break
 write(root/'finalized.json',{'stop_reason':'15 consecutive rounds without a confirmed-label improvement' if stale>=15 else 'criteria met','best_commit':a.base,'best_metrics':best,'roi_accuracy':None,'holdout_evaluated':False,'no_more_tuning':True})
 return 0

if __name__=='__main__':sys.exit(main())
