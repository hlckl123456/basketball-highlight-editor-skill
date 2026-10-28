#!/usr/bin/env python3
"""Replay automatic no-number presence selection; reference choices only.
Default: one target reference, no manually chosen negative-player references.
"""
import argparse,os,shutil,sys
from pathlib import Path
from types import SimpleNamespace as A
CASE=Path(__file__).resolve().parent;ROOT=CASE.parents[1]
sys.path.insert(0,str(ROOT/'skills/basketball-highlight-editor/scripts'))
import highlight as h

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--all-reference-cards',action='store_true');parser.add_argument('--model',help='Explicit authorized DINOv2-S weights for fresh clothing features');parser.add_argument('--redetect',action='store_true');parser.add_argument('--render',action='store_true',help='Export a machine-selected draft as test_operator, not a human confirmation');a=parser.parse_args()
 out=Path(a.output).resolve();source=ROOT/'examples/unnumbered/sources/university.webm';rights=ROOT/'examples/unnumbered/rights/university.json';h.cmd_init(A(project=out,video=source,rights=rights,reproducible=True,epoch=1793203200));h.cmd_import(A(project=out,file=CASE/'coverage.json'))
 for s in h.read(CASE/'reference-inputs.json')['samples']:
  if not a.all_reference_cards and s['player_id']!='white':continue
  h.cmd_sample(A(project=out,player=s['player_id'],time=s['time'],bbox=s['bbox_xyxy'],description=s['description'],reviewer_kind='test_operator',confirmed_by='Archived reference-choice fixture; no event annotation or user confirmation'))
 if a.redetect:
  h.cmd_people(A(project=out,model=None,roi=[0,320,478,570],tile=240,fps=5,start=0,end=60.6,stream=True))
 else:
  data=h.read(CASE/'project/people/detections.json');data['video']=str(source);h.write(out/'people/detections.json',data)
  r,p=h.load(out);p['person_detector']={'method':'Replay of archived fresh YOLOX scan','data':'people/detections.json','data_sha256':h.sha(out/'people/detections.json'),'model_sha256':data['model_sha256'],'ocr_enabled':False,'replay':True};h.save(r,p,'replay_person_features',p['person_detector'])
 if a.model:h.cmd_match_people(A(project=out,player='white',role='visible',apply=True,appearance_model=a.model))
 else:h.cmd_match_people(A(project=out,player='white',role='visible',apply=True,appearance_bundle=CASE/('four-card-project/people/appearance-bundle.json' if a.all_reference_cards else 'project/people/appearance-bundle.json')))
 h.cmd_select(A(project=out,player='white',role='visible',selected_by='test_operator reference fixture; no manual clip assignments'));h.cmd_rough(A(project=out));shutil.copyfile(out/'review.html',out/'review-before-confirm.html')
 r,p=h.load(out);reference_times=[s['time'] for s in p['samples'] if s['player_id']=='white'];high=set(p['selection']['high_confidence']);ids=[c['id'] for c in p['candidates'] if c['id'] in high and not any(c['start']<=t+3 and c['end']>=t-3 for t in reference_times)]
 if a.render:
  if not ids:raise ValueError('NO_INDEPENDENT_AUTOMATIC_CLIPS: no manual fallback allowed')
  h.write(out/'automatic-export.json',{'status':'draft','project_revision':p['revision'],'player_id':'white','reviewer_kind':'test_operator','reviewer':'Deterministic automatic export fixture, not a human review','decision_basis':'Model high windows minus target-reference +/-3 seconds','decisions':{c['id']:('keep' if c['id'] in ids else 'reject') for c in p['candidates']}});h.cmd_confirm(A(project=out,file=out/'automatic-export.json'))
  h.write(out/'automatic-edit-spec.json',{'prompt':'User-authorized demo export of every automatically supported independent window; draft only, no manual clip choices','clip_ids':ids,'max_duration':60});h.cmd_version(A(project=out,name='automatic-draft-v2',spec=out/'automatic-edit-spec.json',render=True))
 h.write(out/'receipt.json',{'status':'draft','reviewer_kind':'test_operator','reference_count':len(p['samples']),'high_windows':sorted(high),'automatic_exported_windows':ids,'manual_clip_assignment_edits':False,'fresh_person_inference':a.redetect,'fresh_texture_requested':bool(a.model),'torch_imported':'torch' in sys.modules,'human_confirmation':False,'source_sha256':h.sha(source)})
 print(h.read(out/'receipt.json'))

if __name__=='__main__':main()
