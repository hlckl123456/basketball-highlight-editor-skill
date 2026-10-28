"""Local head-trimmed clothing embeddings; explicit authorized weights, no downloads.
DINOv2-S is a generic Apache-2.0 visual backbone, not a face recognizer.
"""
import hashlib,json,subprocess,sys,time
from pathlib import Path
import cv2
import numpy as np
import media_io
from person_engine import sha
SCHEMA='clothing-dinov2-v1-head22-input112x224-parts'
ASSETS=Path(__file__).resolve().parents[1]/'assets/dinov2'

def crop_clothing(frame,box):
 x,y,x2,y2=map(lambda v:int(round(v)),box);h,w=frame.shape[:2]
 # Discard the top of the person proposal; no face embedding or OCR is run.
 bh=y2-y;bw=x2-x
 x=max(0,x+round(.08*bw));x2=min(w,x2-round(.08*bw));y=max(0,y+round(.22*bh));y2=min(h,y2)
 if x2<=x or y2<=y:raise ValueError('APPEARANCE_EMPTY_CLOTHING_CROP')
 return cv2.cvtColor(cv2.resize(frame[y:y2,x:x2],(112,224),interpolation=cv2.INTER_LINEAR),cv2.COLOR_BGR2RGB)

class Encoder:
 def __init__(self,weights):
  weights=Path(weights)
  if not weights.is_file():raise ValueError('APPEARANCE_MODEL_MISSING: provide an authorized local DINOv2-S checkpoint')
  manifest=json.loads((ASSETS/'provenance.json').read_text());self.model_sha256=sha(weights)
  if self.model_sha256!=manifest['weights_sha256']:raise ValueError('APPEARANCE_MODEL_HASH_MISMATCH: use the documented official DINOv2-S weights')
  vendor=ASSETS
  for item in manifest['files']:
   if sha(vendor/item['path'])!=item['sha256']:raise ValueError('APPEARANCE_SOURCE_CHANGED: restore the pinned upstream source')
  try:import torch
  except ImportError as exc:raise ValueError('APPEARANCE_TORCH_MISSING: run with a PyTorch environment or use --appearance-bundle for archived feature replay') from exc
  torch.set_num_threads(2);torch.manual_seed(0);torch.use_deterministic_algorithms(True)
  sys.path.insert(0,str(vendor))
  from dinov2.models.vision_transformer import vit_small
  self.torch=torch;self.model=vit_small(patch_size=14,img_size=518,init_values=1.,block_chunks=0).eval()
  self.model.load_state_dict(torch.load(weights,map_location='cpu',weights_only=True),strict=True)
 def encode(self,crops):
  if not crops:return np.zeros((0,3,384),dtype=np.float32)
  t=self.torch
  x=t.from_numpy(np.stack(crops).astype(np.float32)/255).permute(0,3,1,2)
  x=(x-t.tensor([.485,.456,.406])[None,:,None,None])/t.tensor([.229,.224,.225])[None,:,None,None]
  with t.inference_mode():
   out=self.model.forward_features(x);patch=out['x_norm_patchtokens'].reshape(len(crops),16,8,384)
   z=t.stack([out['x_norm_clstoken'],patch[:,:8].mean((1,2)),patch[:,8:].mean((1,2))],dim=1)
   z=t.nn.functional.normalize(z,dim=-1)
  return z.numpy().astype(np.float32)

def frame_stream(video,data):
 yield from media_io.sampled_frames(video,data['records'],data['fps'])


def observation_features(data,video,weights,output,encoder=None,batch_size=16):
 """Content-addressed cache independent of reference choices and editorial ranges."""
 started=time.monotonic();out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
 source_hash=sha(video)
 if source_hash!=data['video_sha256']:raise ValueError('APPEARANCE_SOURCE_HASH_MISMATCH')
 geometry=[(r['time'],[(o['id'],o['box']) for o in r['items']]) for r in data['records']]
 key=hashlib.sha256(json.dumps({'schema':SCHEMA,'source':source_hash,'model':sha(weights),'observations':geometry},sort_keys=True).encode()).hexdigest()
 meta_path=out.with_suffix('.json')
 if out.is_file() and meta_path.is_file():
  meta=json.loads(meta_path.read_text())
  if meta.get('key')==key and meta.get('sha256')==sha(out):
   with np.load(out,allow_pickle=False) as z:ids=z['ids'].tolist();features=z['features'].copy()
   if features.shape!=(len(ids),3,384) or not np.isfinite(features).all():raise ValueError('APPEARANCE_CACHE_INVALID')
   return dict(zip(ids,features)),{**meta,'cache_hit':True,'elapsed_seconds':round(time.monotonic()-started,3)}
 encoder=encoder or Encoder(weights);ids=[];vectors=[];pending=[];pending_ids=[]
 def flush():
  if pending:
   vectors.extend(encoder.encode(pending));ids.extend(pending_ids);pending.clear();pending_ids.clear()
 cv2.setNumThreads(1)
 for row,frame in frame_stream(video,data):
  for obs in row['items']:
   pending.append(crop_clothing(frame,obs['box']));pending_ids.append(obs['id'])
   if len(pending)>=batch_size:flush()
 flush();arr=np.asarray(vectors,np.float32).reshape(-1,3,384)
 np.savez_compressed(out,ids=np.asarray(ids,dtype='U64'),features=arr)
 meta={'schema':SCHEMA,'key':key,'source_sha256':source_hash,'weights_sha256':encoder.model_sha256,'sha256':sha(out),'observations':len(ids),'cache_hit':False,'elapsed_seconds':round(time.monotonic()-started,3),'head_fraction_discarded':.22,'weights_stored':False}
 meta_path.write_text(json.dumps(meta,indent=2)+'\n')
 return dict(zip(ids,arr)),meta
