"""Texture + clothing agreement + independently supported temporal runs.
No jersey OCR, face identity, score ownership or source-specific rules.
"""
from collections import defaultdict
import math
import numpy as np
from attribution_policy import trusted,active,overlap,feature_distance,crop_quality
from person_engine import descriptor,iou
from person_temporal import tracklets
POLICY_VERSION='clothing-texture-reid-v2'
PARAMETERS={'max_distance':.32,'min_margin':.06,'max_part_distance':.45,'max_color_distance':.45,'min_observations':4,'min_span':.8,'max_gap':.71}

def distances(left,right):
 a,b=np.asarray(left),np.asarray(right)
 if a.shape!=(3,384) or b.shape!=(3,384) or not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError('INVALID_APPEARANCE_EMBEDDING')
 if np.any(np.abs(np.linalg.norm(a,axis=1)-1)>.02) or np.any(np.abs(np.linalg.norm(b,axis=1)-1)>.02):raise ValueError('INVALID_APPEARANCE_EMBEDDING')
 parts=np.clip(1-(a*b).sum(axis=1),0,2)
 return float(parts@np.array([.45,.35,.20])),parts.tolist()

def profile_cost(feature,samples,time):
 viable=[s for s in samples if trusted(s) and active(s,time) and s.get('quality',{}).get('usable') and s.get('embedding') is not None]
 if not viable:return None
 costs=[(distances(feature,s['embedding'])[0],s) for s in viable]
 return min(costs,key=lambda x:(x[0],x[1]['sample_id']))

def score_observation(obs,items,features,references,time,params=None):
 p=params or PARAMETERS;reasons=[];feat=features.get(obs['id'])
 evidence={'policy_version':POLICY_VERSION,'eligible':False,'scope':'visible_presence_only','is_probability':False,'distance':None,'reference_ids':[],'profile_margin':None,'person_margin':None,'reasons':[]}
 if feat is None:evidence['reasons']=['appearance_feature_missing'];return None,evidence
 ranked=[]
 for pid,ss in references.items():
  c=profile_cost(feat,ss,time)
  if c:ranked.append((c[0],pid,c[1]))
 if not ranked:evidence['reasons']=['no_trusted_appearance_reference'];return None,evidence
 ranked.sort(key=lambda x:(x[0],x[1]));cost,pid,ref=ranked[0];_,parts=distances(feat,ref['embedding'])
 evidence.update(distance=cost,region_distances=parts,reference_ids=[ref['sample_id']])
 if not obs.get('quality',{}).get('usable'):reasons.append('observation_quality_insufficient')
 if obs.get('person_score',0)<.45:reasons.append('weak_person_detection')
 if cost>p['max_distance']:reasons.append('texture_distance_too_large')
 if any(d>p['max_part_distance'] for d in parts[1:]):reasons.append('texture_region_disagreement')
 try:
  color=feature_distance(obs['descriptor'],ref['descriptor']);evidence['color_distance']=color
  if color>p['max_color_distance']:reasons.append('clothing_disagreement')
 except (ValueError,TypeError,KeyError):reasons.append('clothing_descriptor_missing')
 if len(ranked)>1:
  evidence['profile_margin']=ranked[1][0]-cost
  if evidence['profile_margin']<p['min_margin']:reasons.append('ambiguous_player_profiles')
 rivals=[]
 for other in items:
  if other['id']==obs['id'] or overlap(other['box'],obs['box'])>.65:continue
  if other['id'] not in features:reasons.append('unassessed_competitor');continue
  c=profile_cost(features[other['id']],references[pid],time)
  if c:rivals.append(c[0])
 if rivals:
  evidence['person_margin']=min(rivals)-cost
  if evidence['person_margin']<p['min_margin']:reasons.append('ambiguous_same_frame_person')
 if not rivals and len(ranked)<2:reasons.append('no_independent_uniqueness_evidence')
 evidence['reasons']=sorted(set(reasons));evidence['eligible']=not reasons
 return pid,evidence

def predict_from_features(data,features,references,params=None):
 times=[r['time'] for r in data['records']];ids=[o['id'] for r in data['records'] for o in r['items']]
 if not all(math.isfinite(t) for t in times) or any(b<=a for a,b in zip(times,times[1:])):raise ValueError('INVALID_APPEARANCE_TIMELINE')
 if len(ids)!=len(set(ids)):raise ValueError('DUPLICATE_APPEARANCE_OBSERVATION')
 p=dict(PARAMETERS if params is None else params);rows={r['time']:{'time':r['time'],'accepted':[],'uncertain':[]} for r in data['records']};frames={r['time']:r['items'] for r in data['records']};audit=[];segments=[];summaries=[]
 for tid,track in enumerate(tracklets(data)):
  observations=[]
  for t,obs in track:
   pid,e=score_observation(obs,frames[t],features,references,t,p)
   item={'player_id':pid,'observation_id':obs['id'],'track_id':tid,'box':obs['box'],'person_score':obs['person_score'],'distance':e['distance'],'profile_margin':e['profile_margin'],'person_margin':e['person_margin'],'confidence_evidence':e}
   observations.append((t,item));audit.append({'time':t,'observation_id':obs['id'],'player_id':pid,**e})
  runs=[];current=[]
  for t,item in observations:
   eligible=item['confidence_evidence']['eligible']
   if eligible:
    if current and (item['player_id']!=current[-1][1]['player_id'] or t-current[-1][0]>p['max_gap']):runs.append(current);current=[]
    current.append((t,item))
   elif current:
    # A conflicting lookalike on this very track breaks continuity. Low-quality
    # gaps may remain unknown, never receive propagated identity themselves.
    e=item['confidence_evidence']
    conflict=set(e['reasons'])&{'ambiguous_same_frame_person','ambiguous_player_profiles','clothing_disagreement'}
    if conflict or t-current[-1][0]>p['max_gap']:runs.append(current);current=[]
  if current:runs.append(current)
  supported=set()
  for run in runs:
   if len(run)<p['min_observations'] or run[-1][0]-run[0][0]+1e-6<p['min_span']:continue
   sid='segment-%05d'%len(segments);pid=run[0][1]['player_id']
   segment={'id':sid,'track_id':tid,'player_id':pid,'start':run[0][0],'end':run[-1][0],'support_count':len(run),'observations':[o['observation_id'] for _,o in run],'reference_ids':sorted({ref for _,o in run for ref in o['confidence_evidence']['reference_ids']}),'status':'draft','scope':'visible_presence_only'}
   segments.append(segment)
   for t,o in run:supported.add(o['observation_id']);o['segment_id']=sid
  for t,item in observations:
   if item['observation_id'] in supported:rows[t]['accepted'].append(item)
   else:
    if item['confidence_evidence']['eligible']:
     item['confidence_evidence']={**item['confidence_evidence'],'eligible':False,'reasons':['insufficient_contiguous_texture_support']}
    rows[t]['uncertain'].append(item)
  summaries.append({'track_id':tid,'start':track[0][0],'end':track[-1][0],'count':len(track),'identity_verified':False})
 return {'records':list(rows.values()),'segments':segments,'tracks':summaries,'confidence_audit':audit,'parameters':p,'policy_version':POLICY_VERSION,'is_probability':False,'method':'head-trimmed DINOv2 clothing texture, color agreement, actual competitor margins, independent temporal support runs; presence only'}

def candidate_evidence(result,candidate,player):
 # Presence is existential. A verified run does not assert identity in the rest
 # of the clip; unrelated uncertain frames do not erase that precise time range.
 support=[];usable=[];p=result['parameters']
 for s in result.get('segments',[]):
  if s['player_id']!=player:continue
  hits=[(r['time'],o) for r in result['records'] if candidate['start']<=r['time']<=candidate['end'] for o in r['accepted'] if o.get('segment_id')==s['id'] and o['player_id']==player]
  if len(hits)>=p['min_observations'] and hits[-1][0]-hits[0][0]+1e-6>=p['min_span']:
   usable.append({'id':s['id'],'start':hits[0][0],'end':hits[-1][0],'support_count':len(hits)})
   if len(hits)>len(support):support=hits
 high=bool(support)
 return {'candidate_id':candidate['id'],'target_player_id':player,'presence_player_id':player if high else None,'presence_certainty':'high' if high else 'uncertain','role_certainty':{'visible':'high' if high else 'uncertain','scorer':'uncertain','handler':'uncertain'},'role_reasons':{'scorer':'clothing_presence_does_not_prove_scorer','handler':'clothing_presence_does_not_prove_ball_handler'},'confidence_scope':'visible_presence_only','policy_version':POLICY_VERSION,'is_probability':False,'reason_codes':[] if high else ['insufficient_independent_texture_run'],'support_count':len(support),'support':support,'supported_time_ranges':usable,'never_auto_exclude':True}

def predict(data,calibration,weights,cache):
 from appearance_features import Encoder,observation_features,crop_clothing
 import media_io
 encoder=Encoder(weights);features,meta=observation_features(data,data['video'],weights,cache,encoder)
 refs=defaultdict(list);video_meta=media_io.probe(data['video']);pending=[];samples=[]
 for person in calibration['people']:
  for sample in person['samples']:
   if not trusted(sample):continue
   frame=media_io.frame_bgr(data['video'],sample['time'],video_meta)
   pending.append(crop_clothing(frame,sample['box']));samples.append((person['id'],{**sample,'descriptor':descriptor(frame,sample['box']),'quality':crop_quality(frame,sample['box'])}))
 vecs=encoder.encode(pending)
 for (pid,s),v in zip(samples,vecs):refs[pid].append({**s,'embedding':v})
 bundle=save_bundle(data,calibration,features,refs,cache)
 out=predict_from_features(data,features,refs);out.update(appearance_bundle=bundle,calibration=calibration,appearance_cache=meta,reference_evidence={pid:[{k:v for k,v in s.items() if k!='embedding'} for s in ss] for pid,ss in refs.items()})
 return out


def calibration_hash(calibration):
 import hashlib,json
 def canonical(v):
  if isinstance(v,bool) or v is None:return v
  if isinstance(v,(int,float)):return float(v)
  if isinstance(v,dict):return {k:canonical(x) for k,x in v.items()}
  if isinstance(v,list):return [canonical(x) for x in v]
  return v
 return hashlib.sha256(json.dumps(canonical(calibration),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def save_bundle(data,calibration,features,references,cache):
 """Archive derived features for offline replay, never model weights or labels."""
 import json
 from pathlib import Path
 from person_engine import sha
 from appearance_features import SCHEMA
 path=Path(cache);refpath=path.with_name(path.stem+'-references.npz');meta=path.with_name(path.stem+'-bundle.json')
 specs=[];vectors=[]
 for pid,ss in references.items():
  for s in ss:specs.append({'player_id':pid,**{k:v for k,v in s.items() if k!='embedding'}});vectors.append(s['embedding'])
 np.savez_compressed(refpath,features=np.asarray(vectors,np.float32).reshape(-1,3,384))
 provenance=json.loads(path.with_suffix('.json').read_text())
 payload={'schema':SCHEMA,'source_sha256':data['video_sha256'],'calibration_sha256':calibration_hash(calibration),'features':path.name,'features_sha256':sha(path),'reference_features':refpath.name,'reference_features_sha256':sha(refpath),'references':specs,'feature_cache':provenance,'status':'draft','ground_truth':False,'model_weights':False}
 meta.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');return meta.name


def predict_from_bundle(data,calibration,bundle):
 import json
 from pathlib import Path
 from appearance_features import SCHEMA
 from person_engine import sha
 b=Path(bundle);m=json.loads(b.read_text());provenance=json.loads((Path(__file__).resolve().parents[1]/'assets/dinov2/provenance.json').read_text())
 if m.get('schema')!=SCHEMA or m.get('source_sha256')!=data['video_sha256'] or m.get('calibration_sha256')!=calibration_hash(calibration):raise ValueError('APPEARANCE_BUNDLE_INPUT_MISMATCH')
 if m['feature_cache']['weights_sha256']!=provenance['weights_sha256']:raise ValueError('APPEARANCE_BUNDLE_MODEL_MISMATCH')
 for k in ['features','reference_features']:
  if Path(m[k]).name!=m[k]:raise ValueError('APPEARANCE_BUNDLE_UNSAFE_PATH')
  if sha(b.parent/m[k])!=m[k+'_sha256']:raise ValueError('APPEARANCE_BUNDLE_HASH_MISMATCH')
 with np.load(b.parent/m['features'],allow_pickle=False) as z:ids=z['ids'].tolist();vecs=z['features'].copy()
 expected=[o['id'] for r in data['records'] for o in r['items']]
 if len(ids)!=len(set(ids)) or set(ids)!=set(expected) or vecs.shape!=(len(ids),3,384):raise ValueError('APPEARANCE_BUNDLE_OBSERVATION_MISMATCH')
 # Bind boxes/times too, not just observation names.
 import hashlib
 geometry=[(r['time'],[(o['id'],o['box']) for o in r['items']]) for r in data['records']]
 key=hashlib.sha256(json.dumps({'schema':SCHEMA,'source':data['video_sha256'],'model':provenance['weights_sha256'],'observations':geometry},sort_keys=True).encode()).hexdigest()
 if key!=m['feature_cache']['key']:raise ValueError('APPEARANCE_BUNDLE_GEOMETRY_MISMATCH')
 refs=defaultdict(list)
 with np.load(b.parent/m['reference_features'],allow_pickle=False) as z:rvec=z['features'].copy()
 if rvec.shape!=(len(m['references']),3,384):raise ValueError('APPEARANCE_BUNDLE_REFERENCE_MISMATCH')
 for s,v in zip(m['references'],rvec):refs[s['player_id']].append({**s,'embedding':v})
 out=predict_from_features(data,dict(zip(ids,vecs)),refs)
 out.update(calibration=calibration,appearance_cache={**m['feature_cache'],'cache_hit':True,'mode':'replay_derived_features'},reference_evidence={pid:[{k:v for k,v in s.items() if k not in ('embedding','player_id')} for s in ss] for pid,ss in refs.items()},appearance_bundle=b.name)
 return out
