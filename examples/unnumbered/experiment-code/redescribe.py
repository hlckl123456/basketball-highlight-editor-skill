import json,sys,cv2
from pathlib import Path
from person_pilot import descriptor
for arg in sys.argv[1:]:
 p=Path(arg);d=json.loads(p.read_text());cap=cv2.VideoCapture(d['video'])
 for r in d['records']:
  cap.set(cv2.CAP_PROP_POS_MSEC,r['time']*1000);ok,im=cap.read()
  if not ok:raise ValueError(r['time'])
  for o in r['items']:o['descriptor']=descriptor(im,o['box'])
 cap.release();d['descriptor']='Soft chromatic foreground weighting in clothing bands, HSV hue + neutral bin, coarse lightness; v2; approximate bands, no OCR or face embedding'
 p.with_name(p.stem+'-v2.json').write_text(json.dumps(d,indent=2)+'\n')
 print(p.stem)
