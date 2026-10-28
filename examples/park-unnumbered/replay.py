#!/usr/bin/env python3
"""Replay this public unnumbered case; all choices remain test_operator fixtures."""
import argparse,os,shutil,sys
from pathlib import Path
from types import SimpleNamespace as A
CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]
sys.path.insert(0,str(ROOT/'skills/basketball-highlight-editor/scripts'))
import highlight as h

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--redetect',action='store_true',help='Run fresh person inference, using an already-authorized local model')
    parser.add_argument('--model',help='Required with --redetect; model weights are not redistributed here')
    parser.add_argument('--render',action='store_true',help='Also replay the explicit later editing request')
    a=parser.parse_args()
    if a.redetect and not a.model:parser.error('--redetect requires --model /path/to/authorized/yolox_nano.onnx')
    out=Path(a.output).resolve();video=CASE/'source/park-bodycam.webm'
    h.cmd_init(A(project=out,video=video,rights=CASE/'source/rights.json',reproducible=True,epoch=1793203200))
    h.cmd_import(A(project=out,file=CASE/'review-windows.json'))
    for person in h.read(CASE/'references.json')['people']:
        for s in person['samples']:
            h.cmd_sample(A(project=out,player=person['id'],time=s['time'],bbox=s['box'],description=person['description'],reviewer_kind='test_operator',confirmed_by='Replay of archived operator reference; not human confirmation'))
    if a.redetect:
        h.cmd_people(A(project=out,model=a.model,roi=[108,0,746,480],tile=0,fps=3,start=0,end=391))
    else:
        data=h.read(CASE/'analysis/people/detections.json');data['video']=str(video)
        h.write(out/'people/detections.json',data)
        r,p=h.load(out);p['person_detector']={'method':'Replay of fresh scan archived with this case','model_sha256':data['model_sha256'],'data':'people/detections.json','data_sha256':h.sha(out/'people/detections.json'),'ocr_enabled':False,'replay':True}
        h.save(r,p,'replay_scan','Archived predictions only; no evaluation labels')
    h.cmd_match_people(A(project=out,player='target',role='visible',apply=True))
    h.cmd_select(A(project=out,player='target',role='visible',selected_by='test_operator: archived public case'))
    h.cmd_rough(A(project=out));shutil.copyfile(out/'review.html',out/'review-before-confirm.html')
    r,p=h.load(out);decisions=h.read(CASE/'project/review-decisions.json');decisions['project_revision']=p['revision']
    h.write(out/'review-decisions.json',decisions);h.cmd_confirm(A(project=out,file=out/'review-decisions.json'))
    if a.render:h.cmd_version(A(project=out,name='unnumbered-chronological',spec=CASE/'edit-spec.json',render=True))
    r,p=h.load(out)
    assert p['confirmation']['reviewer_kind']=='test_operator'
    assert p['confirmation']['kept']==['c0001','c0002','c0003','c0004','c0005']
    assert p['selection']['role']=='visible'
    print('PASS: 8 unnumbered review clips, 5 operator-kept plays; no user confirmation or made-shot truth created')

if __name__=='__main__':main()
