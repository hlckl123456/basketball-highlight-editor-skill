"""Evaluate clothing-sample matching separately from person-detection recall.
Truth is used ONLY after predictions are fixed; calibration samples are explicit.
"""
import argparse,json
from pathlib import Path
import cv2
import numpy as np
from person_engine import descriptor,distance,iou,sha


def predict(data,calibration,max_distance=.40,profile_margin=.035,person_margin=.025):
    cap=cv2.VideoCapture(data['video']);refs={}
    for person in calibration['people']:
        samples=[]
        for sample in person['samples']:
            cap.set(cv2.CAP_PROP_POS_MSEC,sample['time']*1000);ok,frame=cap.read()
            if not ok:raise ValueError('Missing calibration frame')
            samples.append(descriptor(frame,sample['box']))
        refs[person['id']]=samples
    cap.release()
    from person_temporal import assign
    results,tracks=assign(data,refs,calibration,max_distance,profile_margin,person_margin)
    return {'parameters':{'max_distance':max_distance,'profile_margin':profile_margin,'person_margin':person_margin},
            'calibration':calibration,'records':results,'tracks':tracks,'method':'clothing samples + mutual-nearest short tracklets; no OCR, face embedding or GT lookup'}


def evaluate(data,pred,truth):
    metrics={'tp':0,'fp':0,'fn':0,'visible':0,'detector_found':0,'evaluated_player_frames':0,'unknown_truth':0,'calibration_excluded':0}
    per={p['id']:dict(metrics) for p in pred['calibration']['people']};rows=[]
    for frame in truth['frames']:
        detection=min(data['records'],key=lambda r:abs(r['time']-frame['time']))
        result=min(pred['records'],key=lambda r:abs(r['time']-frame['time']))
        if abs(result['time']-frame['time'])>.05:raise ValueError('Missing evaluation sample')
        for pid,box in frame['people'].items():
            st=per[pid]
            if any(abs(s['time']-frame['time'])<.05 for p in pred['calibration']['people'] if p['id']==pid for s in p['samples']):
                st['calibration_excluded']+=1;continue
            if box=='unknown':st['unknown_truth']+=1;continue
            st['evaluated_player_frames']+=1
            guess=next((r for r in result['accepted'] if r['player_id']==pid),None)
            if box is not None:
                st['visible']+=1
                if any(iou(o['box'],box)>=.35 for o in detection['items']):st['detector_found']+=1
                # A merged/crossing box must overlap its claimed identity most,
                # rather than receiving credit for either nearby person.
                known={k:v for k,v in frame['people'].items() if isinstance(v,list)}
                best_pid=max(known,key=lambda k:iou(guess['box'],known[k])) if guess else None
                if guess and best_pid==pid and iou(guess['box'],box)>=.35:st['tp']+=1;status='tp'
                else:
                    st['fn']+=1;status='fn'
                    if guess:st['fp']+=1;status='wrong_person_or_box'
            elif guess:st['fp']+=1;status='false_presence'
            else:status='correct_absence'
            rows.append({'time':frame['time'],'player_id':pid,'truth':box,'prediction':guess,'status':status})
    for st in per.values():
        for k in metrics:metrics[k]+=st[k]
        st['precision']=st['tp']/max(1,st['tp']+st['fp']);st['recall']=st['tp']/max(1,st['visible'])
        st['detector_recall']=st['detector_found']/max(1,st['visible'])
    metrics['precision']=metrics['tp']/max(1,metrics['tp']+metrics['fp'])
    metrics['recall']=metrics['tp']/max(1,metrics['visible'])
    metrics['detector_recall']=metrics['detector_found']/max(1,metrics['visible'])
    return {'metrics':metrics,'per_player':per,'frames':rows,'iou_threshold':.35,'truth_provenance':truth['provenance']}


def main():
    p=argparse.ArgumentParser();p.add_argument('--detections',required=True);p.add_argument('--calibration',required=True);p.add_argument('--truth',required=True);p.add_argument('--output',required=True)
    p.add_argument('--max-distance',type=float,default=.4);p.add_argument('--profile-margin',type=float,default=.035);p.add_argument('--person-margin',type=float,default=.025)
    a=p.parse_args();data=json.loads(Path(a.detections).read_text());cal=json.loads(Path(a.calibration).read_text());truth=json.loads(Path(a.truth).read_text())
    pred=predict(data,cal,a.max_distance,a.profile_margin,a.person_margin);evaluation=evaluate(data,pred,truth)
    out={'input_sha256':sha(a.detections),'truth_sha256':sha(a.truth),'calibration_sha256':sha(a.calibration),'predictions':pred,'evaluation':evaluation}
    Path(a.output).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(evaluation['metrics']))


if __name__=='__main__':main()
