#!/usr/bin/env python3
"""Measured 60-minute cached-candidate pipeline, not an inference benchmark.

120 predeclared six-second review windows, all rough clips, 60 seconds retained.
Generated long source and all outputs stay in work/. Peak RSS sums the owned
process tree, sampled every 20 ms; the source is never loaded whole into RAM.
"""
import argparse
import importlib.util
import importlib.metadata
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace as A
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/basketball-highlight-editor/scripts'))
from generate import encode, RESOLUTIONS
import media_io


def module_at(path):
    spec=importlib.util.spec_from_file_location('performance_target',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def generate_source(root,resolution):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);source=root/('phone-60min-'+resolution+'30-audio.mp4')
    if not source.exists():
        loop=root/('phone-loop-'+resolution+'.mp4')
        if not loop.exists():encode(loop,*RESOLUTIONS[resolution],30,'h264',audio='full',duration=4)
        subprocess.run(['ffmpeg','-v','error','-stream_loop','-1','-i',str(loop),'-t','3600','-map','0:v:0','-map','0:a:0','-c','copy','-movflags','+faststart','-y',str(source)],check=True,timeout=600)
    return source


def worker(args):
    module=module_at(args.script);source=args.source;project=args.project
    rights=project.parent/'rights.json';module.write(rights,dict(source_url='https://commons.wikimedia.org/wiki/File:Indiana_Legends_Versus_Indiana_Lyons,_20240224_183141_(165)_(165).webm',creator='Koavf / Justin Anthony Knapp',license='CC0 1.0',processing_basis='generated format/performance fixture',restrictions='test_operator only; no human annotations'))
    stages={}
    def stage(name,fn):
        begin=time.perf_counter();out=fn();stages[name]=time.perf_counter()-begin;return out
    def invoke(command,fn,flags):
        if args.execution=='in-process':return fn()
        return subprocess.run([sys.executable,str(args.script),command,str(project),*[str(v) for v in flags]],check=True)
    init_flags=['--video',source,'--rights',rights]
    if args.worker!='before':init_flags+=['--reproducible','--epoch','946684800']
    stage('init',lambda:invoke('init',lambda:module.cmd_init(A(project=project,video=source,rights=rights,reproducible=True,epoch=946684800)),init_flags))
    if args.worker=='before':
        stage('cached_candidates',lambda:invoke('import-candidates',lambda:module.cmd_import(A(project=project,file=args.manifest)),['--file',args.manifest]))
    else:
        stage('cached_candidates',lambda:invoke('detect',lambda:module.cmd_detect(A(project=project,backend='manifest',manifest=args.manifest,runtime=None,python=sys.executable,model=None,roi=None,fps=3,before=3,after=3,device='cpu',timeout=300,cache_dir=args.cache,no_cache=False,refresh_cache=False)),['--backend','manifest','--manifest',args.manifest,'--cache-dir',args.cache,'--fps','3','--before','3','--after','3','--timeout','300']))
    stage('features',lambda:invoke('features',lambda:module.cmd_features(A(project=project,interval=2,refresh=False,no_ocr=True)),['--interval','2','--no-ocr']))
    _,p=module.load(project);annotation=project/'annotations.json'
    module.write(annotation,{'reviewer':{'kind':'test_operator','name':'performance fixture; not a human identity claim'},'players':[{'id':'test','description':'mechanical benchmark placeholder','reference':p['candidates'][0]['frames'][0]['path']}],'assignments':[{'candidate_id':c['id'],'player_id':'test','certainty':'uncertain','reason':'Performance coverage fixture, not recognition evidence','evidence':[]} for c in p['candidates']]})
    stage('annotate_select',lambda:(invoke('annotate',lambda:module.cmd_annotate(A(project=project,file=annotation)),['--file',annotation]),invoke('select',lambda:module.cmd_select(A(project=project,player='test',selected_by='test_operator')),['--player','test','--selected-by','test_operator'])))
    stage('rough',lambda:invoke('rough',lambda:module.cmd_rough(A(project=project)),[]))
    _,p=module.load(project);decision=project/'decisions.json';module.write(decision,{'project_revision':p['revision'],'player_id':'test','reviewer_kind':'test_operator','reviewer':'automated performance fixture','decisions':{c['id']:'keep' for c in p['candidates']}})
    stage('confirm',lambda:invoke('confirm',lambda:module.cmd_confirm(A(project=project,file=decision)),['--file',decision]))
    prompt=project/'later-test-prompt.json';module.write(prompt,{'prompt':'test_operator explicit later render prompt','clip_ids':[c['id'] for c in p['candidates']],'max_duration':args.keep_seconds})
    stage('render',lambda:invoke('version',lambda:module.cmd_version(A(project=project,name='test',spec=prompt,render=True)),['--name','test','--spec',prompt,'--render']))
    _,p=module.load(project)
    result={'profile':args.worker,'execution':args.execution,'timings_seconds':stages,'candidate_count':len(p['candidates']),
            'rough_seconds':sum(c['end']-c['start'] for c in p['candidates']),
            'render_seconds':args.keep_seconds,'reviewer_kind':p['confirmation']['reviewer_kind'],
            'output_fps':module.probe(project/'versions/test/reel.mp4')['fps']}
    if args.worker!='before':result['detection_cache_hit']=module.read(project/'detection/cache-status.json')['hit']
    args.worker_result.write_text(json.dumps(result,indent=2)+'\n')


def measure(command,out):
    import psutil
    started=time.perf_counter();peak=0;sample_count=0;denied=[]
    with Path(out).open('w') as log:
        proc=subprocess.Popen([str(v) for v in command],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        parent=psutil.Process(proc.pid)
        try:
            while proc.poll() is None:
                if time.perf_counter()-started>900:
                    raise RuntimeError('Performance worker exceeded 900 seconds; see '+str(out))
                try:
                    owned=[parent]+parent.children(recursive=True);rss=0
                    for child in owned:
                        try:rss+=child.memory_info().rss
                        except psutil.NoSuchProcess:pass
                        except psutil.AccessDenied:denied.append(child.pid)
                    peak=max(peak,rss);sample_count+=1
                except psutil.NoSuchProcess:pass
                except (psutil.AccessDenied,PermissionError) as exc:
                    raise RuntimeError('RSS_PERMISSION_DENIED: allow local process-tree monitoring and rerun the benchmark') from exc
                time.sleep(.02)
            code=proc.wait()
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    if code:raise RuntimeError('Performance worker failed; see '+str(out))
    if denied:raise RuntimeError('Cannot measure owned process RSS: permission denied')
    wall=time.perf_counter()-started
    return {'wall_seconds':wall,'peak_process_tree_rss_bytes':peak,
            'sample_count':sample_count,'sampling_interval_seconds':.02,
            'sampling_interval_kind':'requested minimum delay after each observation',
            'wall_seconds_per_sample':wall/max(1,sample_count)}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'work/goal-2/performance');p.add_argument('--generate-only',action='store_true');p.add_argument('--source',type=Path);p.add_argument('--before-script',type=Path)
    p.add_argument('--execution',choices=['cli','in-process'],default='cli');p.add_argument('--resolution',choices=['480p','720p','1080p'],default='1080p');p.add_argument('--window-seconds',type=float,default=6);p.add_argument('--keep-seconds',type=float,default=60);
    p.add_argument('--worker',choices=['before','after']);p.add_argument('--script',type=Path);p.add_argument('--project',type=Path);p.add_argument('--manifest',type=Path);p.add_argument('--cache',type=Path);p.add_argument('--worker-result',type=Path);a=p.parse_args()
    if a.worker:worker(a);return 0
    root=a.output.resolve();root.mkdir(parents=True,exist_ok=True);source=a.source or generate_source(root,a.resolution)
    if a.generate_only:print(source);return 0
    before=a.before_script or root/'highlight-before.py'
    if not before.exists():before.write_bytes(subprocess.check_output(['git','show','ee0d88e92ca717497306624ef091e267ec42a937:skills/basketball-highlight-editor/scripts/highlight.py'],cwd=ROOT))
    after=ROOT/'skills/basketball-highlight-editor/scripts/highlight.py';h=module_at(after)
    meta=h.probe(source);assert meta['duration']>=3599 and meta['width']==RESOLUTIONS[a.resolution][0]
    manifest=root/'ranges.json';h.write(manifest,{'provenance':'test_operator performance coverage fixture, not detected baskets','candidates':[{'start':15+i*29.7,'end':15+i*29.7+a.window_seconds,'reason':'performance review window'} for i in range(120)]})
    cache=root/'cache';prime=root/'cache-prime'
    if prime.exists():shutil.rmtree(prime)
    rights=root/'prime-rights.json';h.write(rights,dict(source_url='fixture:existing-cc0',creator='test_operator',license='CC0',processing_basis='cache preparation',restrictions='no human confirmation'))
    h.cmd_init(A(project=prime,video=source,rights=rights,reproducible=True,epoch=946684800));h.cmd_detect(A(project=prime,backend='manifest',manifest=manifest,runtime=None,python=sys.executable,model=None,roi=None,fps=3,before=3,after=3,device='cpu',timeout=300,cache_dir=cache,no_cache=False,refresh_cache=False))
    implementation={str(f.relative_to(ROOT)):h.sha(f) for f in [Path(__file__),after,Path(media_io.__file__),ROOT/'robustness/generate.py']}
    packages={}
    for name in ['numpy','opencv-python','opencv-python-headless','psutil','onnxruntime']:
        try:packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:pass
    rows=[]
    for label,script in [('before',before),('after',after)]:
        project=root/label
        if project.exists():shutil.rmtree(project)
        result=root/(label+'-result.json')
        command=[sys.executable,Path(__file__).resolve(),'--worker',label,'--source',source,'--script',script,'--project',project,'--manifest',manifest,'--cache',cache,'--worker-result',result,'--keep-seconds',str(a.keep_seconds),'--execution',a.execution]
        measurement=measure(command,root/(label+'.log'));rows.append({**json.loads(result.read_text()),**measurement});print(label,json.dumps(measurement),flush=True)
    report={'schema_version':1,'machine':{'platform':platform.platform(),'logical_cpus':os.cpu_count()},
       'implementation':implementation,'before_commit':'ee0d88e92ca717497306624ef091e267ec42a937','before_script_sha256':h.sha(before),
       'software':{'python':platform.python_version(),'packages':packages,'ffmpeg':h.ffmpeg_version()},
       'source':{**meta,'sha256':h.sha(source),'bytes':source.stat().st_size,'generator':'4-second CC0 derivative looped to 60 minutes; '+a.resolution+'/30 with audio'},
       'execution':a.execution,'scope':f'No inference cost. 120 cached {a.window_seconds}-second windows, all rough clips, {a.keep_seconds}s retained/rendered. Same 30fps output before/after. Peak RSS includes owned child processes, not unrelated apps.',
       'profiles':rows,'meets_300_seconds':rows[1]['wall_seconds']<300,
       'meets_2_gib':rows[1]['peak_process_tree_rss_bytes']<2*1024**3,
       'speedup':rows[0]['wall_seconds']/rows[1]['wall_seconds']}
    (root/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    assert report['meets_300_seconds'] and report['meets_2_gib'], 'Performance gate not met'
    return 0


if __name__=='__main__':sys.exit(main())
