import json
from pathlib import Path
root=Path(__file__).parent
provenance={'annotator':'Codex visual review of original frames, approximate bounding boxes','kind':'test_operator','human_verified':False,'method':'Raw source frames inspected before matching predictions. Not a human user confirmation.'}
def save(name,cal,rows):
 (root/f'{name}-calibration.json').write_text(json.dumps({'kind':'test_operator','description':'Explicit raw-frame clothing samples; no truth lookup during prediction.','people':cal},indent=2)+'\n')
 (root/f'{name}-truth.json').write_text(json.dumps({'provenance':provenance,'frames':[{'time':t,'people':dict(zip([p['id'] for p in cal],v))} for t,v in rows]},indent=2)+'\n')
save('ljubljana',[
 {'id':'green','description':'Plain green shirt, navy shorts, light shoes; no readable jersey number','samples':[{'time':130,'box':[255,315,295,437]},{'time':165,'box':[333,144,372,232]}]},
 {'id':'mustard','description':'Mustard tee, navy shorts, green shoes; no readable jersey number','samples':[{'time':130,'box':[562,362,602,480]},{'time':165,'box':[449,240,508,341]}]}
],[(130,[[255,315,295,437],[562,362,602,480]]),(135,[None,None]),(140,[[492,120,554,205],[395,106,451,179]]),(145,[[455,121,484,178],[417,90,439,154]]),(150,[[447,181,482,237],[408,141,443,193]]),(155,[[344,319,391,388],[242,368,292,418]]),(160,[[467,120,511,184],[416,144,451,210]]),(165,[[333,144,372,232],[449,240,508,341]]),(170,[[333,87,385,161],[314,233,377,338]]),(175,[[570,277,651,380],[399,311,446,400]]),(180,[[714,178,800,269],[420,425,495,480]]),(185,[[713,178,805,266],[360,280,409,383]])])
save('ukraine',[
 {'id':'yellow_black','description':'Yellow top and black shorts; jersey number status unverified, no OCR used','samples':[{'time':0,'box':[379,348,441,435]},{'time':18,'box':[312,397,356,481]}]},
 {'id':'warm_blue','description':'Warm/orange torso and blue shorts; torso garment uncertain at low resolution','samples':[{'time':6,'box':[269,386,302,437]},{'time':12,'box':[334,388,352,444]}]}
],[(0,[[379,348,441,435],[88,345,115,412]]),(3,[[332,361,364,426],[111,386,161,463]]),(6,[[216,383,244,435],[269,386,302,437]]),(9,[[225,390,255,442],[340,385,364,437]]),(12,[[126,388,157,450],[334,388,352,444]]),(15,[[186,384,232,449],None]),(18,[[312,397,356,481],None]),(20,[None,None])])
