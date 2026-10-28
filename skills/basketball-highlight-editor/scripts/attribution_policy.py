"""Honest attribution policy. Clothing supports presence, never shot ownership.
No faces, body identity, skin classification, ground truth or source-specific rules.
Distances/margins are engineering gates, not calibrated identity probabilities.
"""
import math,statistics
from collections import defaultdict
POLICY_VERSION='honest-attribution-v1'
ROLES=('scorer','handler','visible')

def crop_quality(frame,box):
 import cv2,numpy as np
 x1,y1,x2,y2=[int(round(x)) for x in box];fh,fw=frame.shape[:2];w,h=x2-x1,y2-y1;reasons=[]
 if w<16 or h<64:reasons.append('too_small')
 if h<=0 or not .15<=w/max(1,h)<=1.1:reasons.append('partial_or_merged_geometry')
 if x1<=1 or y1<=1 or x2>=fw-1 or y2>=fh-1:reasons.append('clipped_body')
 crop=frame[max(0,y1):min(fh,y2),max(0,x1):min(fw,x2)];sharpness=0.;exposure=0.
 if crop.size:
  gray=cv2.cvtColor(cv2.resize(crop,(64,128)),cv2.COLOR_BGR2GRAY);sharpness=float(cv2.Laplacian(gray,cv2.CV_32F).var());exposure=float(gray.mean())
  if sharpness<10:reasons.append('blur_or_uninformative_texture')
  if exposure<18 or exposure>245:reasons.append('poor_exposure')
 else:reasons.append('empty_crop')
 return {'usable':not reasons,'reasons':reasons,'width':w,'height':h,'sharpness':round(sharpness,3),'mean_luma':round(exposure,3),'scope':'crop quality only; geometry is not identity evidence'}

def part_distances(left,right):
 import numpy as np
 a,b=np.asarray(left,dtype=float),np.asarray(right,dtype=float)
 if a.shape!=(4,20) or b.shape!=(4,20) or not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError('INVALID_CLOTHING_DESCRIPTOR')
 return np.sqrt(np.sum((a-b)**2,axis=1)/2).tolist()

def feature_distance(left,right):return sum(w*d for w,d in zip([.4,.25,.3,.05],part_distances(left,right)))

def trusted(sample):
 kind=sample.get('reviewer_kind')
 return kind in ('user','test_operator') and sample.get('origin',kind) in ('user','test_operator') and not sample.get('is_automatic') and not sample.get('auto_generated')

def active(sample,time):
 start,end=sample.get('valid_from'),sample.get('valid_until')
 return (start is None or time>=start) and (end is None or time<=end)

def overlap(a,b):
 intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
 return intersection/max(1e-9,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection)

def reference_groups(samples,time):
 groups=defaultdict(list);ignored=[];seen=set()
 for s in samples:
  key=(s.get('time'),tuple(s.get('box',[])))
  if not trusted(s):ignored.append('automatic_or_unverified_reference');continue
  if not active(s,time):ignored.append('outside_reference_validity');continue
  if not (s.get('quality') or {}).get('usable'):ignored.append('reference_quality_insufficient');continue
  if s.get('descriptor') is None:ignored.append('reference_descriptor_missing');continue
  if key in seen:continue
  seen.add(key);groups[s.get('appearance','default')].append(s)
 usable={}
 for name,items in groups.items():
  items=sorted(items,key=lambda s:(s.get('time',0),s.get('sample_id','')))[:3]
  if any(feature_distance(a['descriptor'],b['descriptor'])>.32 for i,a in enumerate(items) for b in items[i+1:]):
   ignored.append('conflicting_reference_appearance');continue
  usable[name]=items
 return usable,sorted(set(ignored))

def group_cost(descriptor,items):
 parts=[statistics.median(v) for v in zip(*(part_distances(descriptor,s['descriptor']) for s in items))]
 return sum(a*b for a,b in zip([.4,.25,.3,.05],parts)),parts

def observation_evidence(observation,frame_items,references,player_id,time):
 reasons=[];groups,ignored=reference_groups(references.get(player_id,[]),time)
 evidence={'policy_version':POLICY_VERSION,'scope':'visible_presence_only','is_probability':False,'eligible':False,'reference_ids':[],
           'appearance_group':None,'distance':None,'region_distances':None,'profile_margin':None,'person_margin':None,'ignored_reference_reasons':ignored}
 if not groups:
  evidence['reasons']=ignored or ['no_trusted_reference'];return evidence
 try:
  ranked=sorted((group_cost(observation['descriptor'],items)[0],name) for name,items in groups.items());cost,name=ranked[0];items=groups[name]
  _,parts=group_cost(observation['descriptor'],items)
 except (ValueError,TypeError,KeyError):evidence['reasons']=['invalid_descriptor'];return evidence
 evidence.update({'distance':cost,'region_distances':parts,'appearance_group':name,'reference_ids':[s.get('sample_id') for s in items]})
 if not (observation.get('quality') or {}).get('usable'):reasons.append('observation_quality_missing_or_insufficient')
 if observation.get('person_score',0)<.45:reasons.append('weak_person_detection')
 if cost>.28:reasons.append('appearance_distance_too_large')
 if any(d>limit for d,limit in zip(parts,[.30,.35,.30,.42])):reasons.append('clothing_region_disagreement')
 rivals=[];unassessed=False
 for other in frame_items:
  if other['id']==observation['id'] or overlap(other['box'],observation['box'])>.65:continue
  try:rivals.append(group_cost(other['descriptor'],items)[0])
  except (ValueError,TypeError,KeyError):unassessed=True
 if rivals:
  evidence['person_margin']=min(rivals)-cost
  if evidence['person_margin']<.05:reasons.append('ambiguous_same_frame_person')
 if unassessed:reasons.append('unassessed_competitor')
 alternatives=[]
 for pid,samples in references.items():
  if pid==player_id:continue
  other_groups,_=reference_groups(samples,time)
  alternatives.extend(group_cost(observation['descriptor'],ss)[0] for ss in other_groups.values())
 if alternatives:
  evidence['profile_margin']=min(alternatives)-cost
  if evidence['profile_margin']<.05:reasons.append('ambiguous_player_profiles')
 # Missing alternatives are unknown, never a fabricated margin of 1.0.
 if not rivals and not alternatives:reasons.append('no_independent_uniqueness_evidence')
 if 'conflicting_reference_appearance' in ignored:reasons.append('conflicting_reference_appearance')
 evidence['reasons']=sorted(set(reasons));evidence['eligible']=not reasons
 return evidence

def filter_matches(data,raw_records,references):
 frames={r['time']:r for r in data['records']};result=[];audit=[]
 for row in raw_records:
  frame=frames[row['time']];byid={o['id']:o for o in frame['items']};accepted=[]
  uncertain=[{**o,'legacy_profile_margin':o.get('profile_margin'),'profile_margin':None,
              'confidence_evidence':{'eligible':False,'scope':'visible_presence_only','is_probability':False,'reasons':['tracklet_hypothesis_unresolved']}} for o in row.get('uncertain',[])]
  for item in row.get('accepted',[]):
   obs=byid.get(item['observation_id'])
   detail=observation_evidence(obs,frame['items'],references,item['player_id'],row['time']) if obs else {'eligible':False,'reasons':['observation_missing'],'distance':None}
   proposed={**item,'legacy_profile_margin':item.get('profile_margin'),'profile_margin':detail.get('profile_margin'),
             'person_margin':detail.get('person_margin'),'confidence_evidence':detail}
   if detail['eligible']:accepted.append(proposed)
   else:uncertain.append(proposed)
   audit.append({'time':row['time'],'player_id':item['player_id'],'observation_id':item['observation_id'],**detail})
  result.append({**row,'accepted':accepted,'uncertain':uncertain})
 return result,audit

def candidate_evidence(result,candidate,player):
 hits=[];reasons=[]
 for r in result['records']:
  if not candidate['start']<=r['time']<=candidate['end']:continue
  for o in r.get('accepted',[]):
   if o.get('player_id')==player and (o.get('confidence_evidence') or {}).get('eligible'):hits.append((r['time'],o))
  for o in r.get('uncertain',[]):
   e=o.get('confidence_evidence') or {}
   if o.get('player_id')==player and e.get('distance') is not None and e['distance']<=.35:
    reasons.extend(x for x in e.get('reasons',[]) if x in ['ambiguous_same_frame_person','ambiguous_player_profiles','clothing_region_disagreement','conflicting_reference_appearance'])
 by_track=defaultdict(list)
 for t,o in hits:by_track[o.get('track_id')].append((t,o))
 support=[]
 for track,items in by_track.items():
  times=sorted({t for t,_ in items})
  if track is not None and len(times)>=3 and times[-1]-times[0]>=.5 and all(b-a<=.71 for a,b in zip(times,times[1:])):
   if len(items)>len(support):support=items
 if not support:reasons.append('insufficient_contiguous_support')
 high=bool(support) and not reasons
 return {'candidate_id':candidate['id'],'target_player_id':player,'presence_player_id':player if high else None,'presence_certainty':'high' if high else 'uncertain',
  'role_certainty':{'visible':'high' if high else 'uncertain','scorer':'uncertain','handler':'uncertain'},
  'role_reasons':{'scorer':'clothing_presence_does_not_prove_scorer','handler':'clothing_presence_does_not_prove_ball_handler'},
  'confidence_scope':'visible_presence_only','policy_version':POLICY_VERSION,'is_probability':False,
  'reason_codes':sorted(set(reasons)),'support_count':len(support),'support':support if high else [],'never_auto_exclude':True}

def route_assignment(assignment,target,role='visible'):
 if role not in ROLES:raise ValueError('INVALID_ATTRIBUTION_ROLE')
 q=assignment or {};kind=(q.get('reviewer') or {}).get('kind')
 if q.get('certainty')=='other' and kind in ('user','test_operator') and q.get('absence_verified') is True and q.get('exclusion_for')==target:
  return 'other','explicit_reviewed_target_absence'
 presence=(q.get('presence_player_id') if q.get('presence_certainty')=='high' else None) if 'presence_certainty' in q else (q.get('player_id') if q.get('certainty')=='high' and kind!='local_model' else None)
 if q.get('needs_review'):return 'uncertain','explicit_review_required'
 if presence!=target:return 'uncertain','other_person_presence_is_not_target_absence' if presence else 'identity_unresolved'
 if role=='visible':return 'high_confidence','supported_target_presence'
 ev=q.get('role_evidence') or {}
 if role in q.get('verified_roles',[]) and kind in ('user','test_operator') and ev.get('role')==role and ev.get('detail') and ev.get('authorization_reference'):
  return 'high_confidence','explicit_reviewed_event_role'
 return 'uncertain','event_role_unverified'

def expansion_proposals(result,data,player,limit=3):
 observations={(r['time'],o['id']):o for r in data['records'] for o in r['items']};items=[]
 for r in result['records']:
  for o in r.get('accepted',[]):
   e=o.get('confidence_evidence') or {}
   if o['player_id']!=player or not e.get('eligible'):continue
   obs=observations.get((r['time'],o['observation_id']))
   if obs:items.append((e['distance'],r['time'],o['observation_id'],obs['box']))
 out=[]
 for cost,t,oid,box in sorted(items):
  if any(abs(t-p['time'])<1 for p in out):continue
  out.append({'time':t,'bbox_xyxy':box,'source_observation_id':oid,'player_id':player,'status':'draft','origin':'local_model','is_automatic':True,'requires_user_review':True,'affects_high_confidence':False,'not_a_confirmed_reference':True})
  if len(out)>=limit:break
 return out
