#!/usr/bin/env python3
"""Fixture-only four independent one-reference runs; never edits archived results."""
import argparse,copy,json,shutil,sys
from pathlib import Path
import numpy as np
CASE=Path(__file__).resolve().parent;ROOT=CASE.parents[1]
sys.path.insert(0,str(ROOT/'skills/basketball-highlight-editor/scripts'))
import highlight as h
from appearance_match import predict_from_bundle,calibration_hash,candidate_evidence
from person_match import predict as legacy_predict
from attribution_policy import candidate_evidence as legacy_candidate

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);a=parser.parse_args();out=Path(a.output).resolve()
 if out.exists():raise ValueError('OUTPUT_EXISTS: use a fresh directory')
 out.mkdir(parents=True);p=CASE/'four-card-project';data=h.read(p/'people/detections.json');data['video']=str(ROOT/'examples/unnumbered/sources/university.webm');assert h.sha(Path(data['video']))==data['video_sha256']
 full=h.read(p/'people/appearance-bundle.json');cal=h.read(p/'people/matches.json')['calibration'];project=h.read(p/'project.json');shutil.copyfile(p/'people'/full['features'],out/'appearance.npz')
 with np.load(p/'people'/full['reference_features'],allow_pickle=False) as z:vectors=z['features'].copy()
 results=[]
 for person in cal['people']:
  pid=person['id'];single={**cal,'people':[copy.deepcopy(person)]};single['people'][0]['samples'][0]['sample_id']='s001';idx=next(i for i,s in enumerate(full['references']) if s['player_id']==pid);ref={**full['references'][idx],'sample_id':'s001'};name=pid+'-references.npz';np.savez_compressed(out/name,features=vectors[idx:idx+1]);bundle={**full,'features':'appearance.npz','calibration_sha256':calibration_hash(single),'reference_features':name,'reference_features_sha256':h.sha(out/name),'references':[ref]};h.write(out/(pid+'-bundle.json'),bundle)
  pred=predict_from_bundle(data,single,out/(pid+'-bundle.json'));old=legacy_predict(data,single);h.write(out/(pid+'-matches.json'),pred)
  results.append({'player_id':pid,'reference_count':1,'other_manual_reference_count':0,'legacy_high_windows':[c['id'] for c in project['candidates'] if legacy_candidate(old,c,pid)['presence_certainty']=='high'],'texture_high_windows':[c['id'] for c in project['candidates'] if candidate_evidence(pred,c,pid)['presence_certainty']=='high'],'accuracy':None})
 payload={'status':'draft','protocol':'Four independent one-reference runs','profiles':results,'manual_clip_assignments':False,'human_ground_truth':False};h.write(out/'comparison.json',payload);print(json.dumps(payload,ensure_ascii=False))
if __name__=='__main__':main()
