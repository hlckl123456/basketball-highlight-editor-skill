#!/usr/bin/env python3
"""Generate ignored real-video derivatives with machine-readable frame clocks.
The underlying footage is the repository's CC0 Indiana video. No files in the
published user project or eval/ are modified. Frame clocks are test instruments.
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'examples/indiana/source/indiana-cc0.webm'
RESOLUTIONS={'480p':(854,480),'720p':(1280,720),'1080p':(1920,1080),'4k':(3840,2160)}


def run(cmd,timeout=600):
    p=subprocess.run([str(x) for x in cmd],capture_output=True,timeout=timeout)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-2500:])


def clock_filter(width,height,offset=0):
    block=max(6,width//32);h=max(16,min(64,height//10))
    filters=[f'drawbox=x=0:y=0:w=iw:h={h+8}:color=black:t=fill']
    bits=[1,0,1,1]+list(range(20))+[0,1,0,1]
    for j in range(28):
        expr=None
        if j<4:enabled=bool(bits[j])
        elif j>=24:enabled=bool(bits[j])
        else:
            enabled=True;expr=f"gte(mod(floor((n+{offset})/{2**(j-4)}),2),1)"
        if enabled:
            f=f'drawbox=x={(j+2)*block}:y=4:w={block}:h={h}:color=white:t=fill'
            if expr:f+=f":enable='{expr}'"
            filters.append(f)
    return ','.join(filters)


def encode(output,width,height,fps,codec,condition=None,audio='none',duration=4,offset=0):
    cmd=['ffmpeg','-v','error','-threads','2','-i',SOURCE]
    if audio!='none':cmd+=['-f','lavfi','-i','sine=frequency=880:sample_rate=48000:duration='+str(duration if audio=='full' else 1)]
    vf=[]
    if width<height:vf += [f'scale={width}:{height}:force_original_aspect_ratio=increase',f'crop={width}:{height}']
    else:vf += [f'scale={width}:{height}', 'setsar=1']
    vf+=['fps='+('60' if fps=='vfr' else str(fps))]
    if fps=='vfr':vf += ["select='if(lt(t,2),1,not(mod(n,3)))'"]
    effects={'shake':"crop=iw-32:ih-32:x='16+14*sin(13*t)':y='16+14*cos(17*t)',scale="+str(width)+':'+str(height),
             'lowlight':'eq=brightness=-0.30:contrast=0.65:saturation=0.55',
             'backlight':'eq=brightness=0.30:contrast=1.8:gamma=1.4',
             'noise':'noise=alls=55:allf=t+u:all_seed=20261028',
             'lowbitrate':'null'}
    if condition:vf.append(effects[condition])
    # The measurement strip must survive the condition being measured.
    # Compress the scene at 90 kb/s first, then add the clock in a second pass.
    if condition!='lowbitrate':vf.append(clock_filter(width,height,offset))
    cmd += ['-map','0:v:0','-vf',','.join(vf),'-filter_threads','1','-t',str(duration),'-fps_mode','vfr' if fps=='vfr' else 'cfr','-pix_fmt','yuv420p','-threads','2']
    if codec=='h264':cmd+=['-c:v','libx264','-preset','ultrafast','-crf','40' if condition=='lowbitrate' else '24','-g',str(60 if fps=='vfr' else fps),'-video_track_timescale','60000']
    elif codec=='hevc':cmd+=['-c:v','libx265','-preset','ultrafast','-crf','28','-x265-params','pools=2:frame-threads=1:wpp=0:log-level=error','-tag:v','hvc1','-video_track_timescale','60000']
    else:cmd+=['-c:v','libvpx-vp9','-deadline','realtime','-cpu-used','8','-row-mt','0','-crf','38','-b:v','0']
    if condition=='lowbitrate':cmd+=['-b:v','90k','-maxrate','90k','-bufsize','180k']
    if audio!='none':cmd+=['-map','1:a:0','-c:a','libopus' if codec=='vp9' else 'aac']
    else:cmd+=['-an']
    encoded=Path(output).with_name(Path(output).stem+'-90kbps.mp4') if condition=='lowbitrate' else output
    cmd+=['-map_metadata','-1','-y',encoded]
    run(cmd)
    if condition=='lowbitrate':
        run(['ffmpeg','-v','error','-threads','2','-i',encoded,'-vf',clock_filter(width,height,offset),'-filter_threads','1','-c:v','libx264','-preset','ultrafast','-crf','20','-threads','2','-an','-y',output])
        Path(encoded).unlink()


def rotate_fixture(source,output,degrees):
    help_text=subprocess.check_output(['ffmpeg','-hide_banner','-h','full'],stderr=subprocess.DEVNULL,text=True)
    if '-display_rotation' in help_text:
        run(['ffmpeg','-v','error','-display_rotation:v:0',degrees,'-i',source,'-c','copy','-y',output])
    else:
        # FFmpeg 6.x uses the legacy output metadata API. The caller verifies
        # the actual display matrix; silently unrotated fixtures are rejected.
        run(['ffmpeg','-v','error','-i',source,'-c','copy','-metadata:s:v:0','rotate='+str(degrees),'-y',output])


def generate(directory,suite='full',include_long=False):
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True);cases=[]
    cores=[]
    if suite=='full':
        cores=[(r,f,c) for r in RESOLUTIONS for f in [24,30,60,'vfr'] for c in ['h264','hevc','vp9']]
    else:cores=[('480p',24,'h264'),('720p',30,'h264'),('1080p','vfr','h264'),('480p',30,'hevc'),('480p',60,'vp9')]
    for resolution,fps,codec in cores:
        width,height=RESOLUTIONS[resolution];name=f'{resolution}-{fps}-{codec}'
        path=directory/(name+({'h264':'.mp4','hevc':'.mov','vp9':'.webm'}[codec]))
        if not path.exists():encode(path,width,height,fps,codec)
        cases.append({'id':name,'path':path.name,'valid':True,'width':width,'height':height,'fps':fps,'codec':codec,'duration':4,'clock':'per-frame-index'})
    extras=[('portrait',360,640,30,'h264',None,'none'),
            ('rotation-90',960,540,30,'h264',None,'none'),
            ('rotation-180',960,540,30,'h264',None,'none'),
            ('audio-full',854,480,30,'h264',None,'full'),
            ('audio-short',854,480,30,'h264',None,'short'),
            ('audio-vfr-short',854,480,'vfr','vp9',None,'short')]
    extras += [(name,854,480,30,'h264',name,'none') for name in ['shake','lowlight','backlight','noise','lowbitrate']]
    if suite=='smoke':extras=[x for x in extras if x[0] in ['portrait','rotation-90','audio-short','lowlight']]
    for name,w,h,fps,codec,effect,audio in extras:
        path=directory/(name+('-clocked' if name=='lowbitrate' else '')+('.webm' if codec=='vp9' else '.mp4'))
        if not path.exists():
            if name.startswith('rotation-'):
                temp=directory/(name+'-coded.mp4');encode(temp,w,h,fps,codec)
                rotate_fixture(temp,path,name.split('-')[1]);temp.unlink()
            else:encode(path,w,h,fps,codec,effect,audio)
        if name.startswith('rotation-'):
            expected=int(name.split('-')[1])
            info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream_side_data=rotation','-of','json',str(path)],text=True))
            actual=next((int(x['rotation'])%360 for x in info['streams'][0].get('side_data_list',[]) if 'rotation' in x),0)
            if actual!=expected:
                repaired=path.with_name(path.stem+'-repair.mp4')
                rotate_fixture(path,repaired,expected);repaired.replace(path)
        cases.append({'id':name,'path':path.name,'valid':True,'width':w,'height':h,'fps':fps,'codec':codec,'duration':4,'audio':audio,'clock':'per-frame-index'})
    base=directory/next(c['path'] for c in cases if c['id']=='480p-24-h264')
    for name in ['truncated','truncated-faststart','zero-duration','audio-only']:
        path=directory/(name+('.m4a' if name=='audio-only' else '.mp4'))
        if not path.exists():
            if name=='truncated':path.write_bytes(base.read_bytes()[:max(100,base.stat().st_size//3)])
            elif name=='truncated-faststart':
                tmp=directory/'faststart.mp4';run(['ffmpeg','-v','error','-i',base,'-c','copy','-movflags','+faststart','-y',tmp]);path.write_bytes(tmp.read_bytes()[:tmp.stat().st_size//2]);tmp.unlink()
            elif name=='zero-duration':run(['ffmpeg','-v','error','-i',base,'-t','0','-c','copy','-y',path])
            else:run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=800:duration=1','-c:a','aac','-y',path])
        cases.append({'id':name,'path':path.name,'valid':False,'expected_error':'MEDIA_'})
    if include_long:
        for duration in [3600,7200]:
            name=f'long-{duration//60}min';path=directory/(name+'.mp4');parts=directory/(name+'-parts');parts.mkdir(exist_ok=True)
            if not path.exists():
                for kind,offset in [('start',0),('middle',duration//2*24),('end',(duration-4)*24)]:
                    encode(parts/(kind+'.mp4'),854,480,24,'h264',duration=4,offset=offset)
                files=['start.mp4']*int((duration/2)/4)+['middle.mp4']+['start.mp4']*int((duration/2-8)/4)+['end.mp4']
                assert len(files)*4==duration
                listing=parts/'concat.txt';listing.write_text(''.join("file '"+x+"'\n" for x in files))
                run(['ffmpeg','-v','error','-f','concat','-safe','1','-i',listing,'-c','copy','-movflags','+faststart','-y',path],timeout=600)
            cases.append({'id':name,'path':path.name,'valid':True,'width':854,'height':480,'fps':24,'codec':'h264','duration':duration,'clock':'sentinels','sentinel_starts':[0,duration/2,duration-4]})
    result={'schema_version':1,'source':SOURCE.relative_to(ROOT).as_posix(),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'license':'CC0 1.0','suite':suite,'cases':cases}
    (directory/'matrix.json').write_text(json.dumps(result,indent=2)+'\n');return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'work/goal-2/variants');p.add_argument('--suite',choices=['smoke','full'],default='smoke');p.add_argument('--include-long',action='store_true');a=p.parse_args()
    d=generate(a.output,a.suite,a.include_long);print('Generated',len(d['cases']),'cases')


if __name__=='__main__':main()
