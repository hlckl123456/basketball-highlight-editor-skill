#!/usr/bin/env python3
"""Two real unnumbered test projects. All choices are test_operator fixtures.
Use --redetect for fresh local YOLOX inference; default reuses archived detections.
"""
import argparse,gzip,json,shutil,sys
from pathlib import Path
from types import SimpleNamespace as A
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/basketball-highlight-editor/scripts'))
import highlight as h


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--scene',choices=['university','ljubljana'],required=True);parser.add_argument('--redetect',action='store_true');a=parser.parse_args()
    case=ROOT/'examples/unnumbered';name=a.scene;root=Path(a.output).resolve()
    video=case/'sources'/('university.webm' if name=='university' else 'ljubljana480.webm')
    rights=case/'rights'/('university.json' if name=='university' else 'ljubljana480.json');h.cmd_init(A(project=root,video=video,rights=rights))
    import os
    _,initial=h.load(root);initial['source']['path']=os.path.relpath(video,root);h.write(root/'project.json',initial)
    ranges=[(0,4),(4,9),(10,14),(19,27),(33,38),(49,60)] if name=='university' else [(129,138),(139,148),(149,158),(159,168),(169,178),(179,189)]
    f=root/'imported-candidates.json';h.write(f,{'provenance':'Predeclared test coverage windows, NOT detected scores','candidates':[{'start':x,'end':y,'reason':'Test coverage window; basket/shooter unverified'} for x,y in ranges]});h.cmd_import(A(project=root,file=f))
    cal=h.read(case/(name+'-calibration.json'))
    for person in cal['people']:
        for s in person['samples']:
            h.cmd_sample(A(project=root,player=person['id'],time=s['time'],bbox=s['box'],description=person['description'],confirmed_by='Test operator fixture based on source visual review; not the human user',reviewer_kind='test_operator'))
    if a.redetect:
        h.cmd_people(A(project=root,model=None,roi=[0,350,478,570] if name=='university' else None,tile=240 if name=='university' else 320,fps=3,start=0 if name=='university' else 129,end=1e9 if name=='university' else 189))
    else:
        with gzip.open(case/(name+'-tiled-v2.json.gz'),'rt') as f:d=json.load(f)
        d.update({'video':h.read(root/'project.json')['source']['path'],'descriptor_version':'clothing-v2','schema_version':1})
        h.write(root/'people/detections.json',d)
        _,p=h.load(root);p['person_detector']={'method':'Archived actual YOLOX-Nano scan + clothing-v2','model_sha256':d['model_sha256'],'data':'people/detections.json','data_sha256':h.sha(root/'people/detections.json'),'ocr_enabled':False,'replay':True};h.invalidate(p);h.save(root,p,'import_archived_person_scan',p['person_detector'])
    h.cmd_match_people(A(project=root,player='green',apply=True));h.cmd_select(A(project=root,player='green',selected_by='test_operator fixture, not a new user answer'));h.cmd_rough(A(project=root))
    _,p=h.load(root);ids=p['selection']['high_confidence']+p['selection']['uncertain'];keep=['c0001','c0002'] if name=='university' else ['c0001','c0002','c0003','c0004','c0005','c0006']
    f=root/'test-decisions.json';h.write(f,{'project_revision':p['revision'],'player_id':'green','reviewer_kind':'test_operator','reviewer':'Public regression test; no fabricated human confirmation','decisions':{cid:'keep' if cid in keep else 'reject' for cid in ids}});h.cmd_confirm(A(project=root,file=f))
    _,p=h.load(root)
    # Portable committed example; source is still checked by hash on load.
    import os
    p['source']['path']=os.path.relpath(video,root)
    d=h.read(root/'people/detections.json');d['video']=p['source']['path'];h.write(root/'people/detections.json',d);p['person_detector']['data_sha256']=h.sha(root/'people/detections.json')
    h.write(root/'project.json',p);h.report(root,p)
    e=h.read(root/'confirmed-edl.json');e['source']=p['source'];h.write(root/'confirmed-edl.json',e)
    matches=h.read(root/'people/matches.json');matches['detections_sha256']=p['person_detector']['data_sha256'];h.write(root/'people/matches.json',matches)
    h.write(root/'replay-receipt.json',{'tool_version':h.VERSION,'source_sha256':h.sha(video),'redetected':a.redetect,'state':p['state'],'revision':p['revision'],'reviewer_kind':p['confirmation']['reviewer_kind'],'kept':p['confirmation']['kept'],'high_confidence':p['selection']['high_confidence'],'uncertain':p['selection']['uncertain'],'versions':p['versions']})
    print(json.dumps(h.read(root/'replay-receipt.json'),indent=2))


if __name__=='__main__':main()
