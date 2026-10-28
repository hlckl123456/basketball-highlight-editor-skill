#!/usr/bin/env python3
"""Optional one-frame real YOLOX I/O scan per valid format; no identity labels."""
import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace as A
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/basketball-highlight-editor/scripts'))
import media_io
import person_engine as engine
from person_match import predict
from generate import generate


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--generated',type=Path,default=ROOT/'work/goal-2/full-variants')
    p.add_argument('--output',type=Path,default=ROOT/'work/goal-2/people-results')
    p.add_argument('--model',type=Path,default=ROOT/'skills/basketball-highlight-editor/assets/yolox/yolox_nano.onnx')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    matrix=generate(a.generated,'full',True);rows=[]
    for c in matrix['cases']:
        if not c['valid']:continue
        source=a.generated/c['path'];out=a.output/(c['id']+'.json');started=time.perf_counter()
        try:
            engine.detect(A(video=source,model=a.model,roi=None,fps=1,start=.5,end=1,tile=0,threshold=.2,output=out))
            data=json.loads(out.read_text());meta=media_io.probe(source)
            assert len(data['records'])==1 and data['records'][0]['time']==.5
            assert (data['width'],data['height'])==(meta['width'],meta['height'])
            assert abs(data['duration']-meta['duration'])<1e-6
            assert all(isinstance(o['quality']['usable'],bool) and o['quality']['scope'].startswith('crop quality') for o in data['records'][0]['items'])
            # A fixed region exercises descriptor extraction, not a claim that
            # a particular person occupies it or has a confirmed identity.
            cal={'kind':'test_operator mechanical calibration, not human truth','people':[{'id':'test_region','samples':[{'time':.5,'box':[0,0,data['width'],data['height']],'reviewer_kind':'test_operator','sample_id':'mechanical-region'}]}]}
            prediction=predict(data,cal)
            assert len(prediction['records'])==1
            assert prediction['is_probability'] is False
            assert all(not o['confidence_evidence']['eligible'] or o['confidence_evidence']['scope']=='visible_presence_only' for o in prediction['records'][0]['accepted'])
            rows.append({'id':c['id'],'status':'passed','seconds':time.perf_counter()-started,'detections':len(data['records'][0]['items'])})
        except Exception as exc:rows.append({'id':c['id'],'status':'failed','error':str(exc)})
        report={'schema_version':1,'scope':'one real YOLOX sample and clothing descriptor/matcher per valid input; no accuracy labels or confirmations',
                'implementation':{f.name:engine.sha(f) for f in [Path(__file__),Path(engine.__file__),ROOT/'skills/basketball-highlight-editor/scripts/person_match.py',ROOT/'skills/basketball-highlight-editor/scripts/attribution_policy.py',Path(media_io.__file__)]},
                'model_sha256':engine.sha(a.model),'cases':rows}
        (a.output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        print(c['id'],rows[-1]['status'],rows[-1].get('error',''),flush=True)
    return int(any(r['status']!='passed' for r in rows))


if __name__=='__main__':sys.exit(main())
