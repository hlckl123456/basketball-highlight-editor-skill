import json,cv2
from pathlib import Path
r=Path(__file__).parent
for n,times in json.loads((r/'holdout-selection.json').read_text())['times'].items():
 video=r/'sources'/('university.webm' if n=='university' else 'ljubljana480.webm');cap=cv2.VideoCapture(str(video))
 for t in times:
  cap.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,im=cap.read()
  if not ok:raise ValueError(t)
  if n=='university':
   im=im[350:550].copy();offset=350;step=50
  else:offset=0;step=100
  for x in range(0,im.shape[1],step):cv2.line(im,(x,0),(x,im.shape[0]),(200,200,200),1);cv2.putText(im,str(x),(x+1,12),cv2.FONT_HERSHEY_SIMPLEX,.35,(0,0,255),1)
  for y in range(0,im.shape[0],step):cv2.line(im,(0,y),(im.shape[1],y),(200,200,200),1);cv2.putText(im,str(y+offset),(1,y+12),cv2.FONT_HERSHEY_SIMPLEX,.35,(0,0,255),1)
  cv2.imwrite(str(r/'groundtruth-frames'/f'holdout-{n}-{t}.jpg'),im)
 cap.release()
