import hashlib,json,math,shutil,subprocess,os
from pathlib import Path
ROOT=Path.cwd();work=ROOT/'work/automatic-fixed-demo';out=ROOT/'outputs/basketball-automatic-fixed';out.mkdir(exist_ok=True);data=json.loads((work/'timing-cues.json').read_text());segments=work/'render';segments.mkdir(exist_ok=True)
def run(cmd):subprocess.run([str(x) for x in cmd],check=True)
def probe(p):return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,sample_rate','-of','json',str(p)]))
def dur(p):return float(probe(p)['format']['duration'])
def stamp(t,ass=False):
 if ass:
  n=round(t*100);return f'{n//360000}:{n//6000%60:02}:{n//100%60:02}.{n%100:02}'
 n=round(t*1000);return f'{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02},{n%1000:03}'
# Each cue uses a real synthesized sentence; measured sample duration controls captions.
srt=[];ass=[]
for i,c in enumerate(data['cues'],1):
 text=c['text'].strip();clean=text.replace('\n',' ')
 if len(clean)>29:
  mid=len(clean)//2;positions=[j+1 for j,ch in enumerate(clean) if ch in '，；']
  split=min(positions,key=lambda j:abs(j-mid)) if positions else mid
  clean=clean[:split]+'\n'+clean[split:]
 end=c['start']+c['speech_duration']+.12
 srt.append(f'{i}\n{stamp(c["start"])} --> {stamp(end)}\n{clean}\n')
 encoded=clean.replace('\n',r'\N')
 ass.append(f'Dialogue: 0,{stamp(c["start"],True)},{stamp(end,True)},Default,,0,0,0,,{encoded}')
(out/'demo.srt').write_text('\n'.join(srt)+'\n')
ass_header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Heiti SC,39,&H00FFFFFF,&H000000FF,&H00141F1B,&H80000000,0,0,0,0,100,100,0,0,1,0.8,0,2,80,80,25,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
(work/'captions.ass').write_text(ass_header+'\n'.join(ass)+'\n')
# Standardize recordings after trimming the actual navigation/setup prefix.
proof=[];cumulative=0.;allocated=0
for s in data['scenes']:
 source=work/'captures'/(s['id']+'.webm');length=dur(source);offset=max(0,length-s['duration']);target=segments/(s['id']+'.mp4');cumulative+=s['duration'];total=round(cumulative*30);frames=total-allocated;allocated=total
 run(['ffmpeg','-v','error','-ss',f'{offset:.3f}','-i',source,'-vf','scale=1920:1080:flags=lanczos,fps=30,setsar=1,tpad=stop_mode=clone:stop_duration=0.2','-frames:v',frames,'-an','-c:v','libx264','-preset','veryfast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart','-y',target])
 proof.append({'scene':s['id'],'raw_recording_seconds':length,'trimmed_setup_seconds':offset,'target_seconds':s['duration'],'output_seconds':dur(target)})
(segments/'video-list.txt').write_text(''.join("file '"+str(segments/(s['id']+'.mp4'))+"'\n" for s in data['scenes']))
run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',segments/'video-list.txt','-c','copy','-y',segments/'picture.mp4'])
# Pad each measured speech sentence to its timeline slot, then concatenate.
for i,c in enumerate(data['cues']):
 target=segments/('voice-%02d.wav'%i)
 run(['ffmpeg','-v','error','-i',ROOT/c['audio'],'-af',f'apad=whole_dur={c["duration"]:.3f},atrim=0:{c["duration"]:.3f}','-ar','48000','-ac','2','-c:a','pcm_s16le','-y',target])
(segments/'audio-list.txt').write_text(''.join("file '"+str(segments/('voice-%02d.wav'%i))+"'\n" for i in range(len(data['cues']))))
run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',segments/'audio-list.txt','-c','copy','-y',segments/'narration.wav'])
result=next(s for s in data['scenes'] if s['id']=='result');delay=round(result['start']*1000);reel=Path(os.environ.get('REEL_PATH',str(ROOT/'examples/fixed-camera-automatic/project/versions/automatic-draft-v2/reel.mp4')))
# Keep the real game sound quiet under the narration only in the export example.
if any(x.get('codec_type')=='audio' for x in probe(reel)['streams']):
 run(['ffmpeg','-v','error','-i',segments/'narration.wav','-i',reel,'-filter_complex',f'[0:a]loudnorm=I=-17:LRA=8:TP=-1.5[voice];[1:a]volume=0.12,adelay={delay}|{delay}[court];[voice][court]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]','-map','[a]','-ar','48000','-c:a','pcm_s16le','-y',segments/'mix.wav'])
else:
 run(['ffmpeg','-v','error','-i',segments/'narration.wav','-af','loudnorm=I=-17:LRA=8:TP=-1.5,alimiter=limit=0.95','-ar','48000','-c:a','pcm_s16le','-y',segments/'mix.wav'])

# Subtitle band is an editorial layer; the product UI itself is unmodified.
run(['ffmpeg','-v','warning','-i',segments/'picture.mp4','-i',segments/'mix.wav','-vf',f"drawbox=x=0:y=ih-130:w=iw:h=130:color=0x182d29@1.0:t=fill,ass={work/'captions.ass'}:fontsdir={work/'fonts'}",'-map','0:v:0','-map','1:a:0','-t',data['duration'],'-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart','-y',out/'fixed-automatic-demo.mp4'])
run(['ffmpeg','-v','error','-i',segments/'mix.wav','-c:a','aac','-b:a','192k','-y',out/'narration.m4a'])
proofdata={'duration':data['duration'],'scenes':proof,'file':probe(out/'fixed-automatic-demo.mp4'),'no_real_human_confirmation_generated':True,'AI_voice':'macOS Tingting','capture_proof':'capture-proof.json'}
(out/'render-proof.json').write_text(json.dumps(proofdata,ensure_ascii=False,indent=2)+'\n');print(json.dumps(proofdata,ensure_ascii=False,indent=2))
