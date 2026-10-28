#!/usr/bin/env python3
"""Repeatable format/PTS/state matrix. All confirmations are test_operator.

Run with an existing Python containing NumPy/OpenCV. Generated media and project
outputs live under work/. Reports contain no annotations or personal source paths.
"""
import argparse
import bisect
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace as A

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/basketball-highlight-editor/scripts'))
spec=importlib.util.spec_from_file_location('highlight',ROOT/'skills/basketball-highlight-editor/scripts/highlight.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
import media_io
from generate import generate


def fingerprint(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def flow(project,source,manifest,cache,reproducible=True,interval=1,render_limit=None):
    project=Path(project);timings={}
    def step(name,fn):
        begin=time.perf_counter();value=fn();timings[name]=time.perf_counter()-begin;return value
    rights=Path(manifest).parent/'rights.json'
    h.write(rights,{'source_url':'https://commons.wikimedia.org/wiki/File:Indiana_Legends_Versus_Indiana_Lyons,_20240224_183141_(165)_(165).webm',
       'creator':'Koavf / Justin Anthony Knapp; FFmpeg test derivative','license':'CC0 1.0',
       'processing_basis':'Existing licensed source, user-authorized local format tests','restrictions':'Test fixture; no new human confirmation or basketball identity claims'})
    step('init',lambda:h.cmd_init(A(project=project,video=source,rights=rights,reproducible=reproducible,epoch=946684800)))
    step('detect',lambda:h.cmd_detect(A(project=project,backend='manifest',manifest=manifest,runtime=None,
        python=sys.executable,model=None,roi=None,fps=3,before=3,after=3,device='cpu',timeout=300,
        cache_dir=cache,no_cache=False,refresh_cache=False)))
    step('features',lambda:h.cmd_features(A(project=project,interval=interval,refresh=False,no_ocr=True)))
    _,p=h.load(project)
    annotation=project/'operator-fixture.json'
    h.write(annotation,{'reviewer':{'kind':'test_operator','name':'input-matrix fixture; not a human annotation'},
        'players':[{'id':'test_target','description':'Test routing label only; no claimed basketball identity',
                    'reference':p['candidates'][0]['frames'][0]['path']}],
        'assignments':[{'candidate_id':c['id'],'player_id':'test_target','certainty':'uncertain',
                        'reason':'Mechanical pipeline test; identity/shot ownership unverified',
                        'role':'merely_visible','evidence':[]} for c in p['candidates']]})
    step('annotate',lambda:h.cmd_annotate(A(project=project,file=annotation)))
    step('select',lambda:h.cmd_select(A(project=project,player='test_target',selected_by='test_operator fixture')))
    step('rough',lambda:h.cmd_rough(A(project=project)))
    _,p=h.load(project);decision=project/'operator-decisions.json'
    h.write(decision,{'project_revision':p['revision'],'player_id':'test_target','reviewer_kind':'test_operator',
        'reviewer':'automated format regression; not a user confirmation','decisions':{c['id']:'keep' for c in p['candidates']}})
    step('confirm',lambda:h.cmd_confirm(A(project=project,file=decision)))
    specfile=project/'operator-edit-prompt.json'
    value={'prompt':'TEST OPERATOR: later explicit render prompt for format regression',
           'clip_ids':[c['id'] for c in p['candidates']]}
    if render_limit is not None:value['max_duration']=render_limit
    h.write(specfile,value)
    step('version',lambda:h.cmd_version(A(project=project,name='test-render',spec=specfile,render=True)))
    _,p=h.load(project)
    assert p['confirmation']['reviewer_kind']=='test_operator'
    return p,timings


def ffprobe(path,args):
    return json.loads(subprocess.check_output(['ffprobe','-v','error',*args,'-of','json',str(path)],text=True))


def pts(path):
    data=ffprobe(path,['-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time'])
    values=[float(f['best_effort_timestamp_time']) for f in data['frames'] if 'best_effort_timestamp_time' in f]
    origin=values[0];return [v-origin for v in values]


def edge_pictures(path):
    import numpy as np
    d=ffprobe(path,['-select_streams','v:0','-count_frames','-show_entries','stream=nb_read_frames,duration,r_frame_rate,start_time'])
    stream=d['streams'][0];n=int(stream['nb_read_frames'])
    raw=media_io.command(['ffmpeg','-v','error','-threads','2','-i',path,'-an','-vf',
         f"select='eq(n,0)+eq(n,{n-1})',scale=640:360",'-filter_threads','1','-fps_mode','vfr','-pix_fmt','rgb24','-f','rawvideo','-'],binary=True)
    frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,360,640,3)
    return frames[0],frames[-1],n,float(stream['duration'])


def decode_clock(frame,meta):
    import numpy as np
    H,W=frame.shape[:2];scale=min(W/meta['width'],H/meta['height'])
    cw,ch=int(round(meta['width']*scale)),int(round(meta['height']*scale))
    x,y=(W-cw)//2,(H-ch)//2;content=frame[y:y+ch,x:x+cw]
    original_w,original_h=meta['coded_width'],meta['coded_height']
    block=max(6,original_w//32);bar=max(16,min(64,original_h//10));matches=[]
    for turns in range(4):
        im=np.rot90(content,turns);hh,ww=im.shape[:2]
        if abs(ww/hh-original_w/original_h)>.03:continue
        vals=[]
        for j in range(28):
            xx=(j+2.5)*block/original_w*ww;yy=(4+bar/2)/original_h*hh
            rx=max(1,int(block/original_w*ww*.2));ry=max(1,int(bar/original_h*hh*.2))
            patch=im[max(0,int(yy)-ry):min(hh,int(yy)+ry+1),max(0,int(xx)-rx):min(ww,int(xx)+rx+1)]
            v=float(np.median(patch))
            if 70<v<180:break
            vals.append(int(v>=128))
        if len(vals)==28 and vals[:4]==[1,0,1,1] and vals[24:]==[0,1,0,1]:
            matches.append(sum(b<<i for i,b in enumerate(vals[4:24])))
    if not matches:raise AssertionError('Frame-clock test instrument could not be decoded')
    if len(set(matches))!=1:raise AssertionError('Ambiguous frame-clock instrument')
    return matches[0]


def audit_clip(path,c,meta,source_pts,case):
    first,last,n,duration=edge_pictures(path);first_id=decode_clock(first,meta);last_id=decode_clock(last,meta)
    if case['clock']=='sentinels':
        expected_first=int(math.floor(c['start']*24+1e-6));expected_last=int(math.ceil(c['end']*24-1e-6))-1
        frame_seconds=1/24
        start_error=abs(first_id/24-c['start']);end_error=abs((last_id+1)/24-c['end'])
    else:
        expected_first=max(0,bisect.bisect_right(source_pts,c['start']+1e-8)-1)
        expected_last=max(0,bisect.bisect_left(source_pts,c['end']-1e-8)-1)
        local=[source_pts[j+1]-source_pts[j] for j in range(max(0,expected_first-1),min(len(source_pts)-1,expected_last+1))]
        frame_seconds=max(local) if local else 1/float(media_io.output_rate(meta))
        start_error=abs(source_pts[min(first_id,len(source_pts)-1)]-c['start'])
        next_pts=source_pts[last_id+1] if last_id+1<len(source_pts) else case['duration']
        end_error=abs(next_pts-c['end'])
    start_frames=abs(first_id-expected_first);end_frames=abs(last_id-expected_last)
    fps=media_io.output_rate(meta);duration_error=abs(duration-(c['end']-c['start']))
    assert start_frames<=1,(path.name,'start',first_id,expected_first)
    assert end_frames<=1,(path.name,'end',last_id,expected_last)
    assert duration_error<=float(1/fps)+1e-5,(path.name,'duration',duration_error,float(1/fps))
    # VFR one-frame precision means its true local presentation interval,
    # not an invented constant frame period. Report seconds as well as indices.
    assert start_error<=frame_seconds+1e-5,(path.name,'start seconds',start_error,frame_seconds)
    assert end_error<=frame_seconds+1e-5,(path.name,'end seconds',end_error,frame_seconds)
    return {'first_clock':first_id,'last_clock':last_id,'expected_first':expected_first,'expected_last':expected_last,
        'start_error_frames':start_frames,'end_error_frames':end_frames,'start_error_seconds':start_error,
        'end_error_seconds':end_error,'source_frame_tolerance_seconds':frame_seconds,
        'duration_error_seconds':duration_error,'output_frames':n,'output_fps':str(fps)}


def audit_audio(path,source,video_duration):
    data=ffprobe(path,['-show_streams'])
    audio=[s for s in data['streams'] if s.get('codec_type')=='audio']
    assert bool(audio)==source['has_audio'],(path.name,'audio topology changed')
    if not audio:return {'present':False}
    stream=audio[0];duration=float(stream['duration'])
    assert abs(duration-video_duration)<=float(1/media_io.output_rate(source))+1e-4,(path.name,'audio duration',duration,video_duration)
    assert int(stream['sample_rate'])==48000 and stream['channels']==2
    return {'present':True,'duration':duration,'sample_rate':48000,'channels':2}


def run_case(case,directory,results):
    path=directory/case['path'];root=results/case['id'];root.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    if not case['valid']:
        try:
            rights=root/'rights.json';h.write(rights,dict(source_url='fixture:invalid',creator='test_operator',license='CC0 derivative',processing_basis='format negative test',restrictions='synthetic damage fixture'))
            h.cmd_init(A(project=root/'invalid-project',video=path,rights=rights,reproducible=True,epoch=946684800))
        except (ValueError,OSError) as exc:
            assert case['expected_error'] in str(exc),(case['id'],str(exc))
            return {'id':case['id'],'status':'passed','negative':True,'error':str(exc).split('\n')[0],'seconds':time.perf_counter()-started}
        raise AssertionError('Malformed input was accepted: '+case['id'])
    meta=h.probe(path)
    if case['id'].startswith('rotation-'):
        expected_rotation=int(case['id'].split('-')[1])
        assert meta['rotation']==expected_rotation, 'Rotation fixture lacks real display-matrix metadata'
        if expected_rotation in (90,270):assert (meta['width'],meta['height'])==(case['height'],case['width'])
    if case['clock']=='sentinels':
        candidates=[{'start':t+.413,'end':t+1.887,'reason':'test-operator time sentinel'} for t in case['sentinel_starts']]
        source_pts=None
    else:
        candidates=[{'start':.413,'end':1.887,'reason':'test coverage, not detected score'},
                    {'start':2.017,'end':3.651,'reason':'test coverage, not detected score'}]
        source_pts=pts(path)
        if case['fps']=='vfr':
            diffs=[b-a for a,b in zip(source_pts,source_pts[1:])]
            assert max(diffs)/min(diffs)>1.8,'VFR fixture became CFR'
    manifest=root/'manifest.json';h.write(manifest,{'provenance':'test_operator coverage fixture, not detector accuracy evidence','candidates':candidates})
    p,first=flow(root/'first',path,manifest,results/'.cache')
    q,second=flow(root/'second',path,manifest,results/'.cache')
    files=['project.json','confirmed-edl.json','versions/test-render/edl.json']
    equal={f:(root/'first'/f).read_bytes()==(root/'second'/f).read_bytes() for f in files}
    assert all(equal.values()),(case['id'],'non-deterministic project/EDL',[k for k,v in equal.items() if not v])
    cold=h.read(root/'first/detection/cache-status.json');hot=h.read(root/'second/detection/cache-status.json')
    assert hot['hit'] is True,'second detection did not use cache'
    audits=[];audio_audits=[]
    for c in p['candidates']:
        audits.append({'candidate_id':c['id'],'stage':'rough',**audit_clip(root/'first'/c['preview'],c,meta,source_pts,case)})
        audio_audits.append(audit_audio(root/'first'/c['preview'],meta,float(audits[-1]['output_frames']/media_io.output_rate(meta))))
    edl=h.read(root/'first/versions/test-render/edl.json')
    for i,c in enumerate(edl['clips']):
        audits.append({'candidate_id':c['id'],'stage':'render',**audit_clip(root/'first/versions/test-render'/('part%03d.mp4'%i),c,meta,source_pts,case)})
    _,_,total,reel_duration=edge_pictures(root/'first/versions/test-render/reel.mp4')
    intended=sum(c['end']-c['start'] for c in edl['clips']);tolerance=float(1/media_io.output_rate(meta))
    assert abs(reel_duration-intended)<=tolerance+1e-5,('reel boundary',reel_duration,intended)
    return {'id':case['id'],'status':'passed','fixture_sha256':h.sha(path),'source':{'codec':meta['codec'],'fps':meta['fps'],'width':meta['width'],'height':meta['height'],'rotation':meta['rotation'],'duration':meta['duration']},
        'project_and_edl_byte_equal':equal,'cache_first_hit':cold['hit'],'cache_second_hit':hot['hit'],'audio_audits':audio_audits,'source_frame_timing_audits':audits,
        'reel_duration_error_seconds':abs(reel_duration-intended),'reel_output_frames':total,
        'cold_timings':first,'warm_timings':second,'seconds':time.perf_counter()-started}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--suite',choices=['smoke','full'],default='smoke');parser.add_argument('--include-long',action='store_true');parser.add_argument('--generated',type=Path,default=ROOT/'work/goal-2/variants');parser.add_argument('--output',type=Path,default=ROOT/'work/goal-2/results');parser.add_argument('--only',action='append');parser.add_argument('--resume',action='store_true');a=parser.parse_args()
    matrix=generate(a.generated,a.suite,a.include_long);a.output.mkdir(parents=True,exist_ok=True);reportfile=a.output/'results.json'
    implementation={str(f.relative_to(ROOT)):fingerprint(f) for f in [Path(__file__),ROOT/'robustness/generate.py',ROOT/'skills/basketball-highlight-editor/scripts/highlight.py',ROOT/'skills/basketball-highlight-editor/scripts/media_io.py',ROOT/'skills/basketball-highlight-editor/scripts/result_cache.py']}
    metadata={'schema_version':1,'suite':a.suite,'include_long':a.include_long,'implementation':implementation,'ffmpeg_version':h.ffmpeg_version(),'reviewer_kind':'test_operator','source_sha256':matrix['source_sha256']}
    old=json.loads(reportfile.read_text()) if a.resume and reportfile.exists() else {}
    if old and old.get('implementation')!=implementation:raise ValueError('RESUME_IMPLEMENTATION_CHANGED: use a fresh output directory after code changes')
    previous=old.get('cases',[])
    completed={r['id']:r for r in previous};rows=[]
    for case in matrix['cases']:
        if a.only and case['id'] not in a.only:continue
        if a.resume and completed.get(case['id'],{}).get('status')=='passed':rows.append(completed[case['id']]);continue
        case_root=a.output/case['id']
        if case_root.exists():shutil.rmtree(case_root)
        try:
            row=run_case(case,a.generated.resolve(),a.output.resolve())
        except Exception as exc:
            row={'id':case['id'],'status':'failed','error':str(exc),'error_type':type(exc).__name__}
        rows.append(row);reportfile.write_text(json.dumps({**metadata,'cases':rows},indent=2)+'\n');print(case['id'],row['status'],row.get('error',''),flush=True)
    if any(r['status']!='passed' for r in rows):return 1
    return 0


if __name__=='__main__':sys.exit(main())
