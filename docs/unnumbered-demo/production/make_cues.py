import json,re,subprocess
from pathlib import Path
root=Path.cwd();work=root/'work/unnumbered-demo';rows=json.loads((work/'story.json').read_text());audio=work/'cues';audio.mkdir(exist_ok=True);start=0;allcues=[]
for row in rows:
 parts=re.findall(r'[^，。；！？]+[，。；！？]?',row['text']);chunks=[];chunk=''
 for part in parts:
  if len(chunk+part)>34 and chunk:chunks.append(chunk);chunk=''
  chunk+=part
  if part.endswith(('。','！','？')) and chunk:chunks.append(chunk);chunk=''
 if chunk:chunks.append(chunk)
 scene_start=start;sc=[]
 for j,text in enumerate(chunks):
  path=audio/('%s-%02d.aiff'%(row['id'],j))
  subprocess.run(['say','-v','Tingting','-r','205','-o',str(path),text],check=True)
  d=float(json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)]))['format'].get('duration',0));assert d>.2
  pad=.20 if j<len(chunks)-1 else 1.0
  cue={'id':row['id']+'-%02d'%j,'scene':row['id'],'text':text,'audio':str(path.relative_to(root)),'start':round(start,3),'speech_duration':d,'duration':round(d+pad,3)}
  start+=cue['duration'];allcues.append(cue);sc.append(cue['id'])
 row.update(start=round(scene_start,3),duration=round(start-scene_start,3),cues=sc)
result={'voice':'macOS Tingting / AI narration / not the user voice','duration':round(start,3),'scenes':rows,'cues':allcues};(work/'timing-cues.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('Duration',start,'cues',len(allcues))
