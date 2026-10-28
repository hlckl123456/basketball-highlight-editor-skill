"""Development-only access and immutable-data policy; no label creation."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE='9ab57949dd1346675c60ca28d7ad2a2701de2dc4'

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def catalog():return json.loads((ROOT/'eval/data/catalog.json').read_text())

def forbidden_paths():
 c=catalog();blocked={ROOT/'eval/review.html'}
 for v in c['videos']:
  if v['split']!='holdout':continue
  blocked.update([ROOT/v['source_path'],ROOT/v['review_media_path'],ROOT/'eval/predictions'/(v['id']+'.json')])
  for parent in ['eval/annotations/drafts','eval/annotations/confirmed','eval/annotations/review-state']:
   blocked.add(ROOT/parent/(v['id']+'.json'))
  blocked.update([ROOT/'eval/data/proposals'/v['id'],ROOT/'eval/data/previews'/v['id']])
 return {p.resolve() for p in blocked}

def install_holdout_guard(log):
 blocked=forbidden_paths();access=[]
 def hook(event,args):
  if event!='open' or not args or isinstance(args[0],int):return
  path=Path(os.fsdecode(args[0])).resolve()
  if any(path==b or b in path.parents for b in blocked):
   access.append(str(path.relative_to(ROOT)))
   raise PermissionError('HOLDOUT_ACCESS_DENIED: final evaluation only')
 sys.addaudithook(hook)
 return access

def assert_immutable():
 paths=['eval/annotations','eval/score.py','eval/schema.py','eval/locking.py','eval/data/catalog.json','examples/indiana/project']
 r=subprocess.run(['git','diff','--quiet','--exit-code',BASE,'--',*paths],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if r.returncode:raise RuntimeError('IMMUTABLE_DATA_OR_SCORER_CHANGED: refuse to continue')

def better(candidate,best):
 r,p=candidate.get('event_recall'),candidate.get('event_precision')
 br,bp=best.get('event_recall'),best.get('event_precision')
 if any(v is None for v in [r,p,br,bp]):return False
 return r>=br and (r>br or p>bp)

def meets(metrics,roi_accuracy):
 return (metrics.get('event_recall') is not None and metrics['event_recall']>=.9
         and metrics.get('event_precision') is not None and metrics['event_precision']>=.7
         and roi_accuracy is not None and roi_accuracy>=.9)

def verify_prior_slow_evidence():
 checked={}
 for name in ['goal-2-matrix.json','goal-2-people.json','goal-2-performance.json']:
  d=json.loads((ROOT/'docs/reports'/name).read_text())
  if 'cases' in d:assert all(r['status']=='passed' for r in d['cases'])
  else:assert d['meets_300_seconds'] and d['meets_2_gib']
  for path,digest in d['implementation'].items():
   f=ROOT/path if '/' in path else ROOT/('robustness' if path=='people_matrix.py' else 'skills/basketball-highlight-editor/scripts')/path
   if sha(f)!=digest:raise RuntimeError('PRIOR_SLOW_TEST_IMPLEMENTATION_CHANGED: rerun slow tests: '+path)
   checked[str(f.relative_to(ROOT))]=digest
 return checked
