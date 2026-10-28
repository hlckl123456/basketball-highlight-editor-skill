#!/usr/bin/env python3
"""Development-only rescan with the existing authorized local ONNX model.
Bounded FFmpeg stream, 12fps observations, low decode floor for controlled trials.
"""
import argparse,json,math,subprocess,sys,tempfile,time
from pathlib import Path
from policy import ROOT,catalog,install_holdout_guard,sha
sys.path.insert(0,str(ROOT/'skills/basketball-highlight-editor/scripts'))
sys.path.insert(0,str(ROOT/'third_party/bhe/src'))
import media_io

def scan(model_path,directory):
 import cv2,numpy as np,onnxruntime as ort
 from basketball_highlight.onnx_detector import OnnxDetector
 denied=install_holdout_guard(directory);directory.mkdir(parents=True,exist_ok=True)
 ort.disable_telemetry_events();cv2.setNumThreads(1)
 options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
 detector=OnnxDetector(model_path,device='cpu',max_batch=1,session_options=options,letterbox_mode='square')
 model_hash=sha(model_path);rows=[]
 for v in catalog()['videos']:
  if v['split']!='development':continue
  path=ROOT/v['source_path'];key={'source':v['sha256'],'model':model_hash,'fps':12,'decode_conf':.03,'ranges':v['evaluation_ranges'],'scanner':sha(__file__),'media_io':sha(media_io.__file__)}
  cache=directory/(v['id']+'.json');digest=__import__('hashlib').sha256(json.dumps(key,sort_keys=True).encode()).hexdigest()
  if cache.exists() and json.loads(cache.read_text()).get('cache_key')==digest:
   print(v['id'],'scan cache hit',flush=True);continue
  assert sha(path)==v['sha256'];meta=media_io.probe(path);w,h=meta['width'],meta['height'];records=[];started=time.perf_counter()
  for start,end in v['evaluation_ranges']:
   cmd=['ffmpeg','-v','error','-threads','2','-seek_timestamp','1','-ss',str(start+meta['presentation_start']),'-i',str(path),'-t',str(end-start),'-an','-vf','fps=12:start_time=0:eof_action=pass','-filter_threads','1','-pix_fmt','bgr24','-f','rawvideo','-']
   with tempfile.TemporaryFile() as error:
    child=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=error);index=0;prev=None
    try:
     while True:
      payload=child.stdout.read(w*h*3)
      if not payload:break
      if len(payload)!=w*h*3:raise ValueError('PARTIAL_SCAN_FRAME')
      t=start+index/12;index+=1
      if t>=end:continue
      frame=np.frombuffer(payload,dtype=np.uint8).reshape(h,w,3);prediction=detector.predict([frame],conf=.03,rect=False,device='cpu')[0]
      detections=[]
      for box in prediction.boxes:
       xyxy=box.xyxy[0].tolist();xyxy=[max(0,min(w,xyxy[0])),max(0,min(h,xyxy[1])),max(0,min(w,xyxy[2])),max(0,min(h,xyxy[3]))]
       if xyxy[2]<=xyxy[0] or xyxy[3]<=xyxy[1]:continue
       detections.append({'name':prediction.names[int(box.cls[0])],'confidence':float(box.conf[0]),'xyxy':xyxy,'center':[(xyxy[0]+xyxy[2])/2,(xyxy[1]+xyxy[3])/2]})
      gray=cv2.resize(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),(160,90)).astype(np.float32)/255;residual=0.
      if prev is not None:
       delta=np.abs(gray-prev);global_motion=float(np.median(delta))
       for d in detections:
        if d['name']!='hoop':continue
        x1,y1,x2,y2=d['xyxy'];rw=max(1,x2-x1);rh=max(1,y2-y1)
        xa=max(0,int((x1-rw)/w*160));xb=min(160,max(xa+1,int((x2+rw)/w*160)));ya=max(0,int((y1-rh)/h*90));yb=min(90,max(ya+1,int((y2+3*rh)/h*90)))
        patch=delta[ya:yb,xa:xb]
        if patch.size:residual=max(residual,max(0,float(patch.mean())-global_motion))
      prev=gray;records.append({'time':round(t,6),'detections':detections,'rim_motion_residual':residual})
     if child.wait(timeout=60):error.seek(0);raise ValueError(error.read().decode(errors='replace')[-1200:])
    finally:
     if child.poll() is None:child.kill();child.wait()
  out={'status':'draft','not_ground_truth':True,'video_id':v['id'],'video_sha256':v['sha256'],'model_sha256':model_hash,'cache_key':digest,'parameters':key,'records':records,'width':w,'height':h,'seconds':time.perf_counter()-started}
  cache.write_text(json.dumps(out,separators=(',',':'))+'\n');print(v['id'],'scan samples',len(records),'seconds',round(out['seconds'],2),flush=True)
  rows.append({'video_id':v['id'],'samples':len(records),'seconds':out['seconds']})
 (directory/'audit.json').write_text(json.dumps({'holdout_denied_accesses':denied,'development_only':True,'model_sha256':model_hash,'scans':rows},indent=2)+'\n')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--output',type=Path,default=ROOT/'work/goal-3/scans');a=p.parse_args();scan(a.model,a.output)
