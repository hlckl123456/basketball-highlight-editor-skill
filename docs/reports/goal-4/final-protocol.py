#!/usr/bin/env python3
"""Goal-4 final availability check, once after code freeze, not an accuracy claim.
Requires completed local validation. Refuses to invent hold-out reference samples
or predictions if confirmed held-out facts become available in a future corpus.
"""
import datetime,hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE='778641c59b0a899c4029c62b5ccd2aa6b265ccbe'
sys.path.insert(0,str(ROOT))
from eval.score import evaluate_repository,empty_counts,ratios,summary

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT).decode().strip()

def main():
 work=ROOT/'work/goal-4';report=ROOT/'docs/reports/goal-4';gates=json.loads((work/'validation-final/results.json').read_text())
 assert gates['all_passed'] and gates['code_unchanged_during_run'],'Final development gates must pass first'
 assert all(sha(ROOT/name)==digest for name,digest in gates['implementation'].items()),'Code changed since gates'
 matrix=json.loads((work/'validation-final/matrix/results.json').read_text());people=json.loads((work/'validation-final/people/results.json').read_text())
 assert len(matrix['cases'])==65 and all(c['status']=='passed' for c in matrix['cases'])
 assert len(people['cases'])==61 and all(c['status']=='passed' for c in people['cases'])
 perf=json.loads((work/'validation-final/performance/results.json').read_text());assert perf['meets_300_seconds'] and perf['meets_2_gib']
 catalog=json.loads((ROOT/'eval/data/catalog.json').read_text());registry=json.loads((ROOT/'eval/annotations/confirmed.lock.json').read_text());held={v['id'] for v in catalog['videos'] if v['split']=='holdout'}
 assert not any(e['video_id'] in held for e in registry['files']),'New held-out facts require a frozen reference-based evaluation protocol; do not guess calibration boxes'
 assert git('symbolic-ref','--short','HEAD')=='goal-4-attribution'
 # Derive protected hashes from the pre-task Git manifest, not new labels.
 manifest=git('show',BASE+':MANIFEST.sha256').splitlines();protected={}
 for line in manifest:
  digest,name=line.split('  ',1)
  if name.startswith(('eval/annotations/','examples/indiana/project/')) or name in ('eval/score.py','eval/schema.py','eval/locking.py','eval/data/catalog.json'):protected[name]=digest
 frozen={'frozen_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'head':git('rev-parse','HEAD'),
  'base':BASE,'main':git('rev-parse','main'),'implementation':gates['implementation'],
  'final_protocol_sha256':sha(Path(__file__)),'protected_count':len(protected),'catalog_sha256':sha(ROOT/'eval/data/catalog.json'),
  'registry_sha256':sha(ROOT/'eval/annotations/confirmed.lock.json'),'holdout_confirmed_files':0,
  'policy':'No algorithm changes after this freeze; only one held-out availability/scoring pass; remaining full QA does not tune algorithms'}
 marker=work/'final-evaluation-attempt.json'
 fd=os.open(marker,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as stream:json.dump({'state':'entered_once','frozen':frozen},stream,ensure_ascii=False,indent=2)
 write(report/'frozen.json',frozen)
 # Real held-out file integrity/semantics are inspected only in this final phase.
 assert all(sha(ROOT/name)==digest for name,digest in protected.items()),'Protected data changed'
 predictions=work/'empty-held-predictions';predictions.mkdir(exist_ok=True)
 result=evaluate_repository(ROOT,ROOT/'eval/data/catalog.json',ROOT/'eval/annotations/confirmed.lock.json',predictions,
                            include_holdout=True,video_ids=sorted(held),role='scorer')
 write(report/'final-holdout.json',result)
 assert result['splits']['holdout']['status']=='no_confirmed_annotations'
 receipt={'state':'completed','scoring_passes':1,'holdout_video_ids':sorted(held),'primary_role':'scorer',
  'secondary_roles':{role:{'status':'not_evaluable_no_confirmed_facts','metrics':ratios(empty_counts())} for role in ['handler','visible']},
  'new_policy_holdout_predictions':0,'reason':'No confirmed held-out event windows, identities or reference samples; no model accuracy can be estimated',
  'protected_files_unchanged':len(protected),'frozen_sha256':sha(report/'frozen.json'),'score_output_sha256':sha(report/'final-holdout.json'),
  'source_of_secondary_metrics':'Original ratios(empty_counts()), not additional held-out evaluations'}
 write(report/'holdout-protocol.json',receipt);write(marker,{'state':'completed','frozen':frozen,'receipt':receipt})
 print(summary(result));print('No confirmed held-out facts; primary and secondary attribution metrics are not estimable.')

if __name__=='__main__':main()
