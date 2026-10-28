#!/usr/bin/env python3
"""Fixed human-fact inputs, no event detector. Do not manufacture scorer labels.
Uses the existing scorer unchanged. Calibration-event exclusions are in-memory
views of immutable facts; no confirmed file or lock is rewritten.
"""
import argparse,copy,hashlib,importlib.util,json,os,shutil,subprocess,sys
from pathlib import Path
from types import SimpleNamespace as A
ROOT=Path(__file__).resolve().parents[2]
BASELINE_REF='778641c59b0a899c4029c62b5ccd2aa6b265ccbe'
sys.path.insert(0,str(ROOT/'experiments/detection'))
from policy import install_holdout_guard,sha
sys.path.insert(0,str(ROOT/'skills/basketball-highlight-editor/scripts'))
sys.path.insert(0,str(ROOT))
from eval.score import score_video,ratios,empty_counts
from eval.schema import validate_annotations
import media_io

def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def development_facts():
 catalog=json.loads((ROOT/'eval/data/catalog.json').read_text());byid={v['id']:v for v in catalog['videos']};registry=json.loads((ROOT/'eval/annotations/confirmed.lock.json').read_text())
 result=[]
 for entry in registry['files']:
  v=byid[entry['video_id']]
  if v['split']!='development':continue
  path=ROOT/entry['path'];assert sha(path)==entry['sha256'];doc=json.loads(path.read_text());validate_annotations(doc,v,allow_legacy=any((e.get('confirmation') or {}).get('source')=='legacy_indiana_user_review' for e in doc['events']))
  result.append((v,doc,entry))
 return result

def reference_candidates(doc):
 # Legacy conversion has one explicit selected target. Resolve its reference
 # through the actual evidence lineage, never a video/player name lookup.
 targets=doc.get('target_player_ids',[]);output={pid:[] for pid in targets}
 if len(targets)!=1:return output
 sources={e.get('confirmation',{}).get('evidence_path') for e in doc['events'] if (e.get('confirmation') or {}).get('source')=='legacy_indiana_user_review'}
 for evidence in sorted(p for p in sources if p):
  project_path=(ROOT/evidence).parent/'project.json'
  if not project_path.exists():continue
  project=json.loads(project_path.read_text());selected=(project.get('selection') or {}).get('player_id')
  if not selected:continue
  for sample in project.get('samples',[]):
   if sample['player_id']!=selected or sample.get('reviewer_kind')!='user' or not sample.get('user_confirmation_reference'):continue
   output[targets[0]].append({'time':sample['time'],'box':sample['bbox_xyxy'],'sample_id':sample['id'],
    'appearance':sample.get('appearance','default'),'reviewer_kind':'test_operator','origin':'test_operator','is_automatic':False,
    'description':sample.get('description',''),'source_sample':str((project_path.parent/sample['reference']).relative_to(ROOT)),
    'lineage':'unique legacy review target and actual user-confirmed source sample; simulation only',
    'source_sample_sha256':sha(project_path.parent/sample['reference'])})
 for pid,samples in output.items():
  distinct=[]
  for s in sorted(samples,key=lambda x:x['time']):
   if all(abs(s['time']-a['time'])>=.5 for a in distinct):distinct.append(s)
  output[pid]=distinct[:3]
 return output

def windows(doc,duration):
 output=[]
 for e in doc['events']:
  if e['status']!='confirmed':continue
  fields=set(e['confirmed_fields'])
  if 'time' in fields:
   start=max(0,e['time']-2);end=min(duration,e['time']+2);basis='human-confirmed event time'
  elif (e.get('confirmation') or {}).get('source')=='legacy_indiana_user_review' and e.get('clip_start') is not None:
   start,end=e['clip_start'],e['clip_end'];basis='legacy confirmed presence clip, NOT a true scoring event'
  else:continue
  output.append({'id':e['id'],'start':start,'end':end,'time':e['time'] if 'time' in fields else (start+end)/2,'timing_basis':basis})
 return output

def prepare(directory):
 import person_engine
 install_holdout_guard(directory);directory.mkdir(parents=True,exist_ok=True);tasks=[]
 # Preserve exact pre-change matching code for later comparisons, no weights.
 frozen=directory/'baseline-code';frozen.mkdir(exist_ok=True)
 for name in ['person_match.py','person_temporal.py','person_engine.py']:
  destination=frozen/name
  if not destination.exists():
   destination.write_bytes(subprocess.check_output(['git','show',BASELINE_REF+':skills/basketball-highlight-editor/scripts/'+name],cwd=ROOT))
 for v,doc,entry in development_facts():
  source=ROOT/v['source_path'];assert sha(source)==v['sha256'];ranges=windows(doc,v['duration']);refs=reference_candidates(doc)
  root=directory/v['id'];root.mkdir(exist_ok=True);data=None;records=[]
  for i,w in enumerate(ranges):
   cache=root/('scan-%03d.json'%i)
   if not cache.exists():person_engine.detect(A(video=source,model=ROOT/'skills/basketball-highlight-editor/assets/yolox/yolox_nano.onnx',roi=None,start=w['start'],end=w['end'],fps=5,tile=640,threshold=.2,output=cache))
   scan=json.loads(cache.read_text())
   for r in scan['records']:
    for o in r['items']:o['id']='window%03d_'%i+o['id']
   if data is None:data=scan
   records+=scan['records']
  if data is None:continue
  data['records']=sorted(records,key=lambda r:r['time']);data['analysis_ranges']=[[w['start'],w['end']] for w in ranges];write(root/'detections.json',data)
  calibration_events={w['id'] for w in ranges for samples in refs.values() for s in samples if w['start']<=s['time']<=w['end']}
  for target in doc.get('target_player_ids',[]):
   task={'video_id':v['id'],'source_sha256':v['sha256'],'confirmed_path':entry['path'],'confirmed_sha256':entry['sha256'],'target_player_id':target,
    'windows':ranges,'evaluation_event_ids':[w['id'] for w in ranges if w['id'] not in calibration_events],
    'calibration_event_ids':sorted(calibration_events),'reference_samples':refs[target],
    'reviewer_kind':'test_operator','uses_event_detector':False,'event_time_policy':'Only confirmed times are event times; legacy windows are presence-only and never invented made shots'}
   tasks.append(task)
  write(root/'references.json',{'status':'test_operator_simulation','people':[{'id':pid,'samples':samples} for pid,samples in refs.items()]})
 write(directory/'tasks.json',{'tasks':tasks,'input_scope':'immutable human facts; true scorer/handler events may be absent','uses_event_detector':False})
 print('Prepared',len(tasks),'target tasks; references',[len(t['reference_samples']) for t in tasks],flush=True)

def score_groups(doc,task,groups):
 selected=copy.copy(doc);selected['events']=[e for e in doc['events'] if e['id'] in task['evaluation_event_ids']];selected['target_player_ids']=[task['target_player_id']]
 out={}
 for role in ['scorer','handler','visible']:
  prediction={'events':[{'id':w['id'],'candidate_id':w['id'],'time':w['time'],'kind':'detected_event','player_assignments':[{'target_player_id':task['target_player_id'],'group':groups[role][w['id']],'assigned_player_id':task['target_player_id'] if groups[role][w['id']]=='high' else None}]} for w in task['windows'] if w['id'] in task['evaluation_event_ids']]}
  raw=score_video(selected,prediction,role=role,tolerance=1.0);out[role]={'counts':raw['counts'],'metrics':ratios(raw['counts']),'details':raw,'evaluation_event_ids':task['evaluation_event_ids'],'calibration_excluded_event_ids':task['calibration_event_ids']}
 return out

def enrich_quality(directory):
 from attribution_policy import crop_quality
 install_holdout_guard(directory)
 for video in sorted({t['video_id'] for t in json.loads((directory/'tasks.json').read_text())['tasks']}):
  root=directory/video;data=json.loads((root/'detections.json').read_text());meta=media_io.probe(data['video'])
  for r in data['records']:
   frame=media_io.frame_bgr(data['video'],r['time'],meta)
   for o in r['items']:o['quality']=crop_quality(frame,o['box'])
  data['quality_only_enrichment_of_sha256']=sha(root/'detections.json')
  write(root/'detections-quality.json',data)
 print('Enriched fixed boxes with crop quality; no rescan or descriptor changes',flush=True)

def run(directory,label):
 if label=='baseline':sys.path.insert(0,str(directory/'baseline-code'))
 import person_match
 denied=install_holdout_guard(directory);tasks=json.loads((directory/'tasks.json').read_text())['tasks'];rows=[]
 for task in tasks:
  path=ROOT/task['confirmed_path'];assert sha(path)==task['confirmed_sha256'];doc=json.loads(path.read_text());root=directory/task['video_id'];data=json.loads((root/('detections.json' if label=='baseline' else 'detections-quality.json')).read_text());cal=json.loads((root/'references.json').read_text())
  result=person_match.predict(data,cal);groups={role:{} for role in ['scorer','handler','visible']};proposals=[]
  for w in task['windows']:
   if label=='baseline':
    hits=[(r['time'],o) for r in result['records'] if w['start']<=r['time']<=w['end'] for o in r['accepted'] if o['player_id']==task['target_player_id']]
    high=len(hits)>=3 and max(t for t,o in hits)-min(t for t,o in hits)>=.5
    proposal={'candidate_id':w['id'],'certainty':'high' if high else 'uncertain','meaning':'legacy shared identity-presence group, not proof of scorer ownership'}
    for role in groups:groups[role][w['id']]='high' if high else 'uncertain'
   else:
    from attribution_policy import candidate_evidence
    proposal=candidate_evidence(result,w,task['target_player_id'])
    groups['visible'][w['id']]='high' if proposal['presence_certainty']=='high' else 'uncertain'
    groups['scorer'][w['id']]='uncertain';groups['handler'][w['id']]='uncertain'
   proposals.append(proposal)
  rows.append({'task':task,'scores':score_groups(doc,task,groups),'groups':groups,'proposals':proposals})
  write(directory/(label+'-'+task['video_id']+'-matches.json'),result)
 output={'label':label,'uses_event_detector':False,'primary_role':'scorer','truth_scope':'legacy clip presence is not scorer, handler or verified event-time truth','holdout_evaluated':False,'denied_holdout_accesses':denied,'tasks':rows}
 write(directory/(label+'.json'),output);print(label,json.dumps([{k:s['metrics'] for k,s in row['scores'].items()} for row in rows]),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','quality','baseline','final']);p.add_argument('--directory',type=Path,default=ROOT/'work/goal-4/benchmark');a=p.parse_args()
 if a.action=='prepare':prepare(a.directory)
 elif a.action=='quality':enrich_quality(a.directory)
 else:run(a.directory,a.action)
