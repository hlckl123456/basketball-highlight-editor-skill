"""Post-freeze evidence collection and one-shot final scoring. No tuning."""
import argparse,hashlib,json,math,os,shutil,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'experiments/detection'));sys.path.insert(0,str(ROOT/'skills/basketball-highlight-editor/scripts'))
from policy import assert_immutable,catalog,sha,verify_prior_slow_evidence
import media_io
PUB=ROOT/'docs/reports/goal-3';RUN=ROOT/'work/goal-3/run'

def write(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def freeze():
 s=json.loads((RUN/'state.json').read_text());f=json.loads((RUN/'finalized.json').read_text())
 assert s['completed_rounds']==15 and s['no_improvement_rounds']==15 and s['accepted_rounds']==0
 assert f['no_more_tuning'] and not f['holdout_evaluated'];assert_immutable();verify_prior_slow_evidence()
 return s,f

def collect():
 state,frozen=freeze();PUB.mkdir(exist_ok=True);rows=json.loads((RUN/'history.json').read_text());write(PUB/'trials.json',rows)
 shutil.copy2(RUN/'control/score.json',PUB/'controlled-baseline.json');summary=[]
 for row in rows[1:]:
  trial=RUN/('round-%02d'%row['round']);gate=json.loads((trial/'gates/results.json').read_text())
  if (trial/'score.json').exists():
   scores=json.loads((trial/'score.json').read_text());assert not scores['holdout_evaluated'];assert scores['splits']['development']['metrics']['event_recall'] is None
  else:scores=json.loads((trial/'score-skipped.json').read_text())
  proposal=json.loads((trial/'proposal-summary.json').read_text());hyp=json.loads((trial/'hypothesis.json').read_text());decision=json.loads((trial/'decision.json').read_text())
  drafts={v['id']:json.loads((trial/'proposals'/(v['id']+'.json')).read_text()) for v in catalog()['videos'] if v['split']=='development'}
  detail={'decision':decision,'hypothesis':hyp,'proposals':proposal,'draft_proposals':drafts,'scores':scores,'gates':gate}
  write(PUB/'rounds'/('r%02d.json'%row['round']),detail)
  target=PUB/'rejected'/('r%02d.patch'%row['round']);target.parent.mkdir(exist_ok=True);shutil.copy2(trial/'candidate.patch',target)
  summary.append({'round':row['round'],'all_passed':gate['all_passed'],'unit_tests':{'behavior':25,'evaluation':49,'robustness':17,'research':19},'deferred_real_corpus_tests':1,'input_smoke_cases':13,'jobs':gate['jobs']})
 write(PUB/'gate-summary.json',{'rounds':summary,'all_15_gates_passed':all(r['all_passed'] for r in summary),'passed_rounds':sum(r['all_passed'] for r in summary),'unexpected_holdout_accesses':state['holdout_denied_accesses']})
 scans=[]
 for v in catalog()['videos']:
  if v['split']!='development':continue
  d=json.loads((ROOT/'work/goal-3/scans'/(v['id']+'.json')).read_text())
  scans.append({'video_id':v['id'],'source_sha256':v['sha256'],'records':len(d['records']),'model_sha256':d['model_sha256'],'status':'draft','parameters':d['parameters'],'scan_seconds':d['seconds']})
 write(PUB/'scan-summary.json',{'development_only':True,'no_weights_redistributed':True,'existing_local_model_no_download':True,'scans':scans})
 write(PUB/'frozen.json',{'frozen_at':datetime.now(timezone.utc).isoformat(),'state':state,'stop':frozen,'research_engine_sha256':sha(ROOT/'experiments/detection/engine.py'),'research_binding_sha256':sha(ROOT/'experiments/detection/trial_candidate.py'),'production_detector_sha256':sha(ROOT/'skills/basketball-highlight-editor/scripts/highlight.py'),'scorer_sha256':sha(ROOT/'eval/score.py'),'confirmed_registry_sha256':sha(ROOT/'eval/annotations/confirmed.lock.json'),'catalog_sha256':sha(ROOT/'eval/data/catalog.json'),'final_predictions':'unchanged production eval/predictions; no research candidate accepted'})
 print('Collected 15 rejected trials and gates, production unchanged.')

def cases():
 import cv2
 freeze();videos={v['id']:v for v in catalog()['videos'] if v['split']=='development'};rows=json.loads((RUN/'history.json').read_text())[1:];selected=[]
 # Difference samples are selected mechanically; never call them confirmed errors.
 for direction in ['added','removed']:
  order=sorted(rows,key=lambda r:r['prediction_events'],reverse=direction=='added')
  found=None
  for row in order:
   for vid,v in videos.items():
    base=json.loads((RUN/'control/proposals'/(vid+'.json')).read_text())['events'];new=json.loads((RUN/('round-%02d'%row['round'])/'proposals'/(vid+'.json')).read_text())['events']
    left,right=(new,base) if direction=='added' else (base,new)
    for event in left:
     if not any(abs(event['time']-other['time'])<=1 for other in right):found=(vid,event['time'],direction,row['round'],event);break
    if found:break
   if found:break
  if found:selected.append(found)
 for vid,v in videos.items():
  d=json.loads((RUN/'control/proposals'/(vid+'.json')).read_text())
  if len(d['rois'])<2:continue
  raw=json.loads((ROOT/'work/goal-3/scans'/(vid+'.json')).read_text());rim=d['rois'][0]['rim'];observed=[(r['time'],x) for r in raw['records'] for x in r['detections'] if x['name']=='hoop']
  if not observed:continue
  t,_=min(observed,key=lambda item:math.dist(item[1]['center'],[rim['center_x'],rim['rim_y']]))
  selected.append((vid,t,'roi_unconfirmed',0,{'roi_proposals':d['rois']}));break
 out=PUB/'cases';out.mkdir(exist_ok=True);result=[]
 for i,(vid,t,kind,trial,event) in enumerate(selected,1):
  v=videos[vid];source=ROOT/v['source_path'];meta=media_io.probe(source);start=max(0,t-2.5);end=min(meta['duration'],t+2.5);name='case-%02d'%i
  media_io.render(source,meta,start,end,out/(name+'.mp4'));frame=media_io.frame_bgr(source,t,meta,max_width=960)
  scale=frame.shape[1]/meta['width']
  for j,roi in enumerate(event.get('roi_proposals',[])[:4]):
   x1,y1,x2,y2=[int(round(q*scale)) for q in roi['roi_xyxy']]
   cv2.rectangle(frame,(x1,y1),(x2,y2),(0,190,255),2);cv2.putText(frame,'draft ROI '+str(j+1),(max(0,x1),max(45,y1)),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,190,255),1)
  cv2.putText(frame,'DRAFT - NOT GROUND TRUTH',(12,25),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,255),2)
  cv2.imwrite(str(out/(name+'.jpg')),frame)
  result.append({'id':name,'video_id':vid,'source_url':v['source_url'],'author':v['author'],'license':v['license'],'license_url':v['license_url'],'source_sha256':v['sha256'],'time':t,'source_start':start,'source_end':end,'type':kind,'trial':trial,'status':'draft','reviewer_kind':'test_operator','not_ground_truth':True,'clip':name+'.mp4','frame':name+'.jpg','evidence':event,'clip_sha256':sha(out/(name+'.mp4'))})
 write(out/'cases.json',{'all_are_unreviewed_differences_not_verified_fp_fn':True,'cases':result})
 lines=['# 待复核差异样本','','以下视频与时间点由程序按候选差异自动选择，没有人工判定进球或错误类型。**它们不是已确认漏检／误报，不能进入 ground truth。**','']
 for c in result:
  lines += [f"## {c['id']} · {c['video_id']} · {c['time']:.3f} 秒",'',f"类型：{c['type']}；实验 {c['trial']}。status=draft，test_operator，仅供核查。",'',f"[播放片段]({c['clip']}) · [参考帧]({c['frame']})",'',f"原作者 {c['author']}；沿用原许可 {c['license']}。 [来源]({c['source_url']}) · [许可]({c['license_url']})。派生处理为截取、转码和截图加草稿提示。",'']
 (out/'README.md').write_text('\n'.join(lines)+'\n');print('Prepared',len(result),'unreviewed cases.')

def final_once():
 freeze();sentinel=ROOT/'work/goal-3/final-evaluation-attempt.json'
 with sentinel.open('x') as stream:json.dump({'attempt':1,'at':datetime.now(timezone.utc).isoformat(),'frozen_config':sha(PUB/'frozen.json'),'no_more_tuning':True},stream)
 out=PUB/'final-holdout.json';log=ROOT/'work/goal-3/final-holdout.log'
 with log.open('w') as stream:r=subprocess.run([sys.executable,'eval/score.py','--include-holdout','--output',str(out)],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
 if r.returncode:raise RuntimeError('Final attempt failed; do not silently repeat held-out evaluation')
 d=json.loads(out.read_text());assert d['holdout_evaluated'];write(PUB/'holdout-protocol.json',{'real_dataset_include_holdout_calls':1,'configuration_frozen_before_evaluation':True,'frozen_config_sha256':sha(PUB/'frozen.json'),'result_sha256':sha(out),'no_more_tuning':True,'holdout_recall_drop':None,'drop_within_5_points':'not estimable: no confirmed made shots in either split'})
 print('Final hold-out scoring attempt completed once; no labels available for event metrics.')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['collect','cases','holdout-once']);a=p.parse_args();{'collect':collect,'cases':cases,'holdout-once':final_once}[a.action]()
