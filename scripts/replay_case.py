#!/usr/bin/env python3
"""Replay the recorded public case locally, with explicit test-operator provenance.

Default: replay archived candidate/features/manual evidence, regenerate rough
clips and confirm the test selection. No model download or BHE inference.
--features recomputes clothing proposals locally. --render-test-versions creates
two explicitly test-only versions from separate test editing specifications.
"""
import argparse
import copy
import importlib.util
import shutil
from pathlib import Path
from types import SimpleNamespace as A

REPO=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('highlight',REPO/'skills/basketball-highlight-editor/scripts/highlight.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=REPO/'work/replay')
    p.add_argument('--features',action='store_true')
    p.add_argument('--render-test-versions',action='store_true')
    a=p.parse_args();dest=a.output.resolve();case=REPO/'examples/indiana'
    if dest.exists() and any(dest.iterdir()):p.error('output must be empty')
    if (REPO/'examples') in dest.parents:p.error('do not overwrite published fixtures')
    original=h.read(case/'project/project.json')
    h.cmd_init(A(project=dest,video=case/'source/indiana-cc0.webm',rights=case/'source/rights.json'))
    fixture=dest/'recorded-candidates.json'
    h.write(fixture,{'provenance':'REPLAY of archived BHE v0.1.12 detections; no new BHE inference',
      'candidates':[{k:c[k] for k in ('start','end','event_time','reason')} for c in original['candidates']]})
    h.cmd_import(A(project=dest,file=fixture))
    for name in ('samples','frames','crops'):
        shutil.copytree(case/'project'/name,dest/name,dirs_exist_ok=True)
    if a.features:h.cmd_features(A(project=dest,interval=1.5,refresh=False,no_ocr=True))
    root,q=h.load(dest)
    if not a.features:
        for c,old in zip(q['candidates'],original['candidates']):
            c['observations']=copy.deepcopy(old['observations']);c['frames']=copy.deepcopy(old['frames'])
        q['feature_extractor']={'backend':'recorded-case-fixture','computed_in_this_run':False,
                               'original_extractor':original['feature_extractor']}
    q['samples']=copy.deepcopy(original['samples'])
    for s in q['samples']:
        s['reviewer_kind']='test_operator';s['confirmed_by']='Replay of published reference; no new user confirmation'
        s.pop('user_confirmation_reference',None);s.pop('user_confirmed_at',None)
    h.save(root,q,'replay_feature_evidence','Recorded evidence or explicitly requested local feature recomputation')
    annotations=h.read(case/'project/visual-review-evidence.json')
    annotations['reviewer']={'kind':'test_operator','name':'replay of recorded visual review; not a new human or model decision'}
    annotation_file=dest/'test-annotations.json';h.write(annotation_file,annotations)
    h.cmd_annotate(A(project=dest,file=annotation_file))
    h.cmd_select(A(project=dest,player='purple2',selected_by='TEST REPLAY of recorded user choice'))
    h.cmd_rough(A(project=dest))
    _,q=h.load(dest)
    decisions=dest/'test-decisions.json'
    h.write(decisions,{'project_revision':q['revision'],'player_id':'purple2',
      'reviewer_kind':'test_operator','reviewer':'replay_case.py; not a new user confirmation',
      'decisions':{'c0001':'keep','c0002':'reject','c0003':'keep','c0004':'reject'}})
    h.cmd_confirm(A(project=dest,file=decisions))
    assert h.read(dest/'project.json')['state']=='awaiting_edit_prompt'
    assert not list(dest.rglob('reel.mp4'))
    if a.render_test_versions:
        for name,ids,limit in [('test-short',['c0003','c0001'],6),('test-long',['c0001','c0003'],20)]:
            f=dest/(name+'-spec.json');h.write(f,{'prompt':'TEST ONLY: '+name,'clip_ids':ids,'max_duration':limit})
            h.cmd_version(A(project=dest,name=name,spec=f,render=True))
    print('PASS: recorded candidate -> feature evidence -> selected player -> regenerated rough clips -> test-operator confirmation -> resumable project')
    print('This was a fixture replay, not a fresh detection/identity accuracy evaluation. Output:',dest)


if __name__=='__main__':main()
