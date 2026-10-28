# Portions of YOLOX pre/postprocessing follow Megvii, Inc. and affiliates, Apache-2.0.
# Modified: local tiled person proposals and clothing descriptors. See ../assets/yolox/LICENSE.
"""Local YOLOX person proposals and clothing-only descriptors, no OCR or faces.
Pre/postprocessing follows the public YOLOX ONNX demo (Megvii, Apache-2.0).
Integrated local person proposals; calibrated samples and temporal matching are separate.
"""
import argparse,hashlib,json,math
from pathlib import Path
import cv2
import numpy as np
import onnxruntime as ort
import media_io


def sha(p):
    digest=hashlib.sha256()
    with Path(p).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def iou(a,b):
    x=max(0,min(a[2],b[2])-max(a[0],b[0]));y=max(0,min(a[3],b[3])-max(a[1],b[1]))
    return x*y/max(1e-6,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-x*y)


def descriptor(frame,box):
    x1,y1,x2,y2=[int(round(x)) for x in box]
    x1=max(0,x1);y1=max(0,y1);x2=min(frame.shape[1],x2);y2=min(frame.shape[0],y2)
    crop=frame[y1:y2,x1:x2]
    if crop.size==0:return None
    # Approximate clothing bands avoid the usual head area; this is not a
    # segmentation mask and cannot guarantee exclusion under arbitrary poses.
    h,w=crop.shape[:2];parts=[]
    for xa,ya,xb,yb in [(.2,.22,.8,.52),(.04,.23,.96,.55),(.18,.55,.82,.82),(.1,.82,.9,.99)]:
        patch=crop[max(0,int(h*ya)):max(1,int(h*yb)),max(0,int(w*xa)):max(1,int(w*xb))]
        hsv=cv2.cvtColor(patch,cv2.COLOR_BGR2HSV)
        hue=hsv[:,:,0].astype(float);sat=hsv[:,:,1].astype(float)/255
        # Soft foreground weighting suppresses neutral court/background pixels.
        # Achromatic clothing remains represented by a separate neutral bin.
        weight=.08+sat**2
        hist=np.zeros(17,dtype=float)
        pos=hue*16/180
        low=np.floor(pos).astype(int)%16;frac=pos-np.floor(pos)
        chroma=np.minimum(1,sat/.35)
        np.add.at(hist,low.ravel(),(weight*chroma*(1-frac)).ravel())
        np.add.at(hist,((low+1)%16).ravel(),(weight*chroma*frac).ravel())
        hist[16]=float((weight*(1-chroma)).sum())
        hist/=max(1e-8,hist.sum())
        # A coarse lightness statistic distinguishes dark/light plain clothes,
        # with low influence so shadows and camera exposure do not dominate.
        val=np.histogram(hsv[:,:,2],bins=[0,85,170,256],weights=weight)[0]
        val=val/max(1e-8,val.sum())
        parts.append(np.concatenate([np.sqrt(hist)*math.sqrt(.92),np.sqrt(val)*math.sqrt(.08)]).tolist())
    return parts


def distance(a,b):
    vals=np.sqrt(np.sum((np.asarray(a)-np.asarray(b))**2,axis=1)/2)
    return float(np.dot(vals,[.4,.25,.3,.05]))



class Detector:
    def __init__(self,path):
        if not Path(path).is_file():raise ValueError("PERSON_MODEL_MISSING")
        ort.disable_telemetry_events()
        opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1;opts.log_severity_level=3
        self.session=ort.InferenceSession(str(path),sess_options=opts,providers=['CPUExecutionProvider'])
        self.name=self.session.get_inputs()[0].name
        shape=self.session.get_inputs()[0].shape
        if shape != [1,3,416,416] or self.session.get_outputs()[0].shape != [1,3549,85]:
            raise ValueError("EXPECTED_RAW_YOLOX_NANO_416")
        self.h,self.w=shape[2:]
        grids=[];strides=[]
        for stride in (8,16,32):
            yy,xx=np.meshgrid(np.arange(self.h//stride),np.arange(self.w//stride),indexing='ij')
            grids.append(np.stack([xx,yy],axis=-1).reshape(-1,2));strides.append(np.full((xx.size,1),stride))
        self.grids=np.concatenate(grids);self.strides=np.concatenate(strides)

    def predict(self,frame,roi,threshold=.2):
        x1,y1,x2,y2=roi;im=frame[y1:y2,x1:x2]
        ratio=min(self.h/im.shape[0],self.w/im.shape[1])
        resized=cv2.resize(im,(int(im.shape[1]*ratio),int(im.shape[0]*ratio)))
        canvas=np.full((self.h,self.w,3),114,dtype=np.uint8);canvas[:resized.shape[0],:resized.shape[1]]=resized
        tensor=np.ascontiguousarray(canvas.transpose(2,0,1)[None],dtype=np.float32)
        out=self.session.run(None,{self.name:tensor})[0][0].copy()
        out[:,:2]=(out[:,:2]+self.grids)*self.strides
        out[:,2:4]=np.exp(out[:,2:4])*self.strides
        scores=out[:,4]*out[:,5]  # COCO class zero: person.
        ids=np.where(scores>=threshold)[0]
        boxes=out[ids,:4];scores=scores[ids]
        boxes=np.concatenate([boxes[:,:2]-boxes[:,2:]/2,boxes[:,:2]+boxes[:,2:]/2],axis=1)/ratio
        boxes+=np.array([x1,y1,x1,y1])
        kept=[]
        for idx in np.argsort(-scores):
            box=boxes[idx].tolist()
            if any(iou(box,k['box'])>.5 for k in kept):continue
            box=[max(0,box[0]),max(0,box[1]),min(frame.shape[1],box[2]),min(frame.shape[0],box[3])]
            if box[3]-box[1]<24 or box[2]-box[0]<7:continue
            from attribution_policy import crop_quality
            kept.append({'box':[round(v,2) for v in box],'person_score':round(float(scores[idx]),4),'descriptor':descriptor(frame,box),'quality':crop_quality(frame,box)})
        return sorted(kept,key=lambda o:o['box'][0])


def detect(a):
    cv2.setNumThreads(1)
    meta=media_io.probe(a.video);w,h=meta['width'],meta['height']
    roi=a.roi or [0,0,w,h]
    if not (0<=roi[0]<roi[2]<=w and 0<=roi[1]<roi[3]<=h):raise ValueError('INVALID_PERSON_ROI')
    if not (0<a.fps<=30 and 0<=a.start<a.end and a.tile>=0 and 0<a.threshold<1):raise ValueError('INVALID_SCAN_PARAMETERS')
    if a.start>=meta['duration']:raise ValueError('INVALID_SCAN_PARAMETERS: start must be inside the video timeline')
    det=Detector(a.model);records=[]
    times=np.arange(a.start,min(a.end,meta['duration']),1/a.fps)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    previews=out.with_suffix('');previews.mkdir(exist_ok=True)
    if getattr(a,'stream',False):
        sampled=media_io.sampled_frames(a.video,[{'time':float(t)} for t in times],a.fps)
    else:sampled=(({'time':float(t)},media_io.frame_bgr(a.video,float(t),meta)) for t in times)
    for k,(sample,frame) in enumerate(sampled):
        t=sample['time']
        regions=[roi]
        if a.tile:
            xs=list(range(roi[0],max(roi[0]+1,roi[2]-a.tile+1),max(1,int(a.tile*.65))))
            ys=list(range(roi[1],max(roi[1]+1,roi[3]-a.tile+1),max(1,int(a.tile*.65))))
            xs=sorted(set(xs+[max(roi[0],roi[2]-a.tile)]))
            ys=sorted(set(ys+[max(roi[1],roi[3]-a.tile)]))
            regions += [[x,y,min(roi[2],x+a.tile),min(roi[3],y+a.tile)] for x in xs for y in ys]
        candidates=[o for r in regions for o in det.predict(frame,r,a.threshold)]
        items=[]
        for o in sorted(candidates,key=lambda o:-o['person_score']):
            if not any(iou(o['box'],q['box'])>.4 for q in items):items.append(o)
        items.sort(key=lambda o:o['box'][0])
        for j,o in enumerate(items):o['id']=f'f{k:05d}_p{j:02d}'
        records.append({'time':round(float(t),3),'items':items})
        if k%max(1,round(a.fps*3))==0:
            view=frame.copy()
            for j,o in enumerate(items):
                x1,y1,x2,y2=map(int,o['box']);cv2.rectangle(view,(x1,y1),(x2,y2),(0,255,0),1)
                cv2.putText(view,str(j),(x1,max(12,y1-3)),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,0,255),1)
            cv2.imwrite(str(previews/f'{k:05d}-{t:.1f}.jpg'),view)
    data={'schema_version':1,'descriptor_version':'clothing-v2','media_io_schema':media_io.RENDER_SCHEMA,'video':str(Path(a.video).resolve()),'video_sha256':sha(a.video),'model_sha256':sha(a.model),
          'fps':a.fps,'roi':roi,'tile':a.tile,'threshold':a.threshold,'duration':meta['duration'],'analysis_range':[a.start,min(a.end,meta['duration'])],'width':w,'height':h,
          'descriptor':'Approximate clothing bands, chromatic foreground weighting, hue+neutral bins and coarse lightness; no OCR or face embedding',
          'records':records}
    out.write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps({'output':str(out),'samples':len(records),'detections':sum(len(r['items']) for r in records)},ensure_ascii=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--video',required=True);p.add_argument('--model',required=True)
    p.add_argument('--stream',action='store_true',help='Decode source once at presentation timestamps');p.add_argument('--roi',nargs=4,type=int);p.add_argument('--start',type=float,default=0);p.add_argument('--end',type=float,default=1e9);p.add_argument('--tile',type=int,default=0);p.add_argument('--fps',type=float,default=5);p.add_argument('--threshold',type=float,default=.2);p.add_argument('--output',required=True)
    detect(p.parse_args())


if __name__=='__main__':main()
