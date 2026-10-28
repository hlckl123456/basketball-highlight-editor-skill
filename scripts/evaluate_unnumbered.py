#!/usr/bin/env python3
"""Recompute the frozen v3 benchmark; requires existing NumPy/OpenCV/ORT.
No downloads, training, or ground-truth access during prediction.
"""
import argparse,gzip,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/basketball-highlight-editor/scripts'))
from person_match import predict,evaluate
from person_engine import sha


def read(path):
    if not path.exists() and path.with_suffix(path.suffix+'.gz').exists():path=path.with_suffix(path.suffix+'.gz')
    if path.suffix=='.gz':
        with gzip.open(path,'rt') as f:return json.load(f)
    return json.loads(path.read_text())


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='work/unnumbered-evaluation');a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True);case=ROOT/'examples/unnumbered';summary=[]
    for name in ('university','ljubljana','ukraine'):
        data=read(case/(name+'-tiled-v2.json'));data['video']=str(case/data['video'])
        assert sha(data['video'])==data['video_sha256']
        cal=read(case/(name+'-calibration.json'));pred=predict(data,cal)
        archived=read(case/(name+'-v3-evaluation.json'))
        assert pred['records']==archived['predictions']['records'],name+' predictions differ from frozen experiment'
        for split in ('development','holdout'):
            truthpath=case/(name+('-holdout' if split=='holdout' else '')+'-truth.json')
            if not truthpath.exists():continue
            truth=read(truthpath);result=evaluate(data,pred,truth)
            file=out/(name+'-'+split+'.json');file.write_text(json.dumps(result,indent=2)+'\n')
            summary.append({'scene':name,'split':split,**result['metrics']})
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
