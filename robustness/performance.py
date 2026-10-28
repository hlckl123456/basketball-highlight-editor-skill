#!/usr/bin/env python3
"""Measured 60-minute cached-candidate pipeline, not an inference benchmark.

120 predeclared two-second review windows, all rough clips, 60 seconds retained.
Generated long source and all outputs stay in work/. Peak RSS sums the owned
process tree, sampled every 20 ms; the source is never loaded whole into RAM.
"""
import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace as A
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/basketball-highlight-editor/scripts'))
from generate import encode
import media_io


def module_at(path):
    spec=importlib.util.spec_from_file_location('performance_target',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def generate_source(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);source=root/'phone-60min-480p30-audio.mp4'
    if not source.exists():
        loop=root/'phone-loop.mp4'
        if not loop.exists():encode(loop,854,480,30,'h264',audio='full',duration=4)
        subprocess.run(['ffmpeg','-v','error','-stream_loop','-1','-i',str(loop),'-t','3600','-map','0:v:0','-map','0:a:0','-c','copy','-movflags','+faststart','-y',str(source)],check=True,timeout=600)
    return source


def worker(args):
    module=module_at(args.script);source=args.source;project=args.project
    rights=project.parent/'rights.json';module.write(rights,dict(source_url='https://commons.wikimedia.org/wiki/File:Indiana_Legends_Versus_Indiana_Lyons,_20240224_183141_(165)_(165).webm',creator='Koavf / Justin Anthony Knapp',license='CC0 1.0',processing_basis='generated format/performance fixture',restrictions='test_operator only; no human annotations'))
    stages={}
    def stage(name,fn):
        begin=time.perf_counter();out=fn();stages[name]=time.perf_counter()-begin;return out
    stage('init',lambda:module.cmd_init(A(project=project,video=source,rights=rights,reproducible=True,epoch=946684800)))
    if args.worker=='before':
        stage('cached_candidates',lambda:module.cmd_import(A(project=project,file=args.manifest)))
    else:
        stage('cached_candidates',lambda:module.cmd_detect(A(project=project,backend='manifest',manifest=args.manifest,runtime=None,python=sys.executable,model=None,roi=None,fps=3,before=3,after=3,device='cpu',timeout=300,cache_dir=args.cache,no_cache=False,refresh_cache=False)))
    stage('features',lambda:module.cmd_features(A(project=project,interval=2,refresh=False,no_ocr=True)))
    _,p=module.load(project);annotation=project/'annotations.json'
    module.write(annotation,{'reviewer':{'kind':'test_operator','name':'performance fixture; not a human identity claim'},'players':[{'id':'test','description':'mechanical benchmark placeholder','reference':p['candidates'][0]['frames'][0]['path']}],'assignments':[{'candidate_id':c['id'],'player_id':'test','certainty':'uncertain','reason':'Performance coverage fixture, not recognition evidence','evidence':[]} for c in p['candidates']]})
    stage('annotate_select',lambda:(module.cmd_annotate(A(project=project,file=annotation)),module.cmd_select(A(project=project,player='test',selected_by='test_operator'))))
    stage('rough',lambda:module.cmd_rough(A(project=project)))
    _,p=module.load(project);decision=project/'decisions.json';module.write(decision,{'project_revision':p['revision'],'player_id':'test','reviewer_kind':'test_operator','reviewer':'automated performance fixture','decisions':{c['id']:'keep' for c in p['candidates']}})
    stage('confirm',lambda:module.cmd_confirm(A(project=project,file=decision)))
    prompt=project/'later-test-prompt.json';module.write(prompt,{'prompt':'test_operator explicit later render prompt','clip_ids':[c['id'] for c in p['candidates']],'max_duration':60})
    stage('render',lambda:module.cmd_version(A(project=project,name='test',spec=prompt,render=True)))
    _,p=module.load(project)
    result={'profile':args.worker,'timings_seconds':stages,'candidate_count':len(p['candidates']),
            'rough_seconds':sum(c['end']-c['start'] for c in p['candidates']),
            'render_seconds':60,'reviewer_kind':p['confirmation']['reviewer_kind'],
            'output_fps':module.probe(project/'versions/test/reel.mp4')['fps']}
    if args.worker!='before':result['detection_cache_hit']=module.read(project/'detection/cache-status.json')['hit']
    args.worker_result.write_text(json.dumps(result,indent=2)+'\n')


def measure(command,out):
    import psutil
    started=time.perf_counter();peak=0;sample_count=0;denied=[]
    with Path(out).open('w') as log:
        proc=subprocess.Popen([str(v) for v in command],stdout=log,stderr=subprocess.STDOUT)
        parent=psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                owned=[parent]+parent.children(recursive=True);rss=0
                for child in owned:
                    try:rss+=child.memory_info().rss
                    except psutil.NoSuchProcess:pass
                    except psutil.AccessDenied:denied.append(child.pid)
                peak=max(peak,rss);sample_count+=1
            except psutil.NoSuchProcess:pass
            time.sleep(.02)
        code=proc.wait()
    if code:raise RuntimeError('Performance worker failed; see '+str(out))
    if denied:raise RuntimeError('Cannot measure owned process RSS: permission denied')
    return {'wall_seconds':time.perf_counter()-started,'peak_process_tree_rss_bytes':peak,
            'sample_count':sample_count,'sampling_interval_seconds':.02}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'work/goal-2/performance');p.add_argument('--generate-only',action='store_true');p.add_argument('--source',type=Path);p.add_argument('--before-script',type=Path)
    p.add_argument('--worker',choices=['before','after']);p.add_argument('--script',type=Path);p.add_argument('--project',type=Path);p.add_argument('--manifest',type=Path);p.add_argument('--cache',type=Path);p.add_argument('--worker-result',type=Path);a=p.parse_args()
    if a.worker:worker(a);return 0
    root=a.output.resolve();root.mkdir(parents=True,exist_ok=True);source=a.source or generate_source(root)
    if a.generate_only:print(source);return 0
    before=a.before_script or root/'highlight-before.py'
    if not before.exists():before.write_bytes(subprocess.check_output(['git','show','ee0d88e92ca717497306624ef091e267ec42a937:skills/basketball-highlight-editor/scripts/highlight.py'],cwd=ROOT))
    after=ROOT/'skills/basketball-highlight-editor/scripts/highlight.py';h=module_at(after)
    meta=h.probe(source);assert meta['duration']>=3599 and meta['width']==854
    manifest=root/'ranges.json';h.write(manifest,{'provenance':'test_operator performance coverage fixture, not detected baskets','candidates':[{'start':15+i*29.7,'end':17+i*29.7,'reason':'2-second performance review window'} for i in range(120)]})
    cache=root/'cache';prime=root/'cache-prime'
    if prime.exists():shutil.rmtree(prime)
    rights=root/'prime-rights.json';h.write(rights,dict(source_url='fixture:existing-cc0',creator='test_operator',license='CC0',processing_basis='cache preparation',restrictions='no human confirmation'))
    h.cmd_init(A(project=prime,video=source,rights=rights,reproducible=True,epoch=946684800));h.cmd_detect(A(project=prime,backend='manifest',manifest=manifest,runtime=None,python=sys.executable,model=None,roi=None,fps=3,before=3,after=3,device='cpu',timeout=300,cache_dir=cache,no_cache=False,refresh_cache=False))
    rows=[]
    for label,script in [('before',before),('after',after)]:
        project=root/label
        if project.exists():shutil.rmtree(project)
        result=root/(label+'-result.json')
        command=[sys.executable,Path(__file__).resolve(),'--worker',label,'--source',source,'--script',script,'--project',project,'--manifest',manifest,'--cache',cache,'--worker-result',result]
        measurement=measure(command,root/(label+'.log'));rows.append({**json.loads(result.read_text()),**measurement});print(label,json.dumps(measurement),flush=True)
    report={'schema_version':1,'machine':{'platform':platform.platform(),'logical_cpus':os.cpu_count()},
       'source':{**meta,'sha256':h.sha(source),'bytes':source.stat().st_size,'generator':'4-second CC0 derivative looped to 60 minutes; 480p/30 with audio'},
       'scope':'No inference cost. 120 cached 2-second windows, all rough clips, 60s retained/rendered. Same 30fps output before/after. Peak RSS includes owned child processes, not unrelated apps.',
       'profiles':rows,'meets_300_seconds':rows[1]['wall_seconds']<300,
       'meets_2_gib':rows[1]['peak_process_tree_rss_bytes']<2*1024**3,
       'speedup':rows[0]['wall_seconds']/rows[1]['wall_seconds']}
    (root/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    assert report['meets_300_seconds'] and report['meets_2_gib'], 'Performance gate not met'
    return 0


if __name__=='__main__':sys.exit(main())
