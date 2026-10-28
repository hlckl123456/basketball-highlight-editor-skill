"""Identity safety contracts, not detector confidence snapshots."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
try:
 import numpy as np
 from person_engine import descriptor,distance
 from person_temporal import assign,tracklets
 from person_match import evaluate
 AVAILABLE=True
except ImportError:
 AVAILABLE=False


@unittest.skipUnless(AVAILABLE,'People tests require existing NumPy/OpenCV/ONNX Runtime')
class People(unittest.TestCase):
 def setUp(self):
  self.red=descriptor(np.full((100,40,3),(0,0,220),np.uint8),[0,0,40,100])
  self.blue=descriptor(np.full((100,40,3),(220,0,0),np.uint8),[0,0,40,100])
  self.refs={'red':[self.red],'blue':[self.blue]}
  self.cal={'people':[{'id':'red','samples':[]},{'id':'blue','samples':[]}]}
 def obs(self,i,x=0,desc=None):
  return {'id':str(i),'box':[x,0,x+40,100],'descriptor':desc or self.red,'person_score':.8}
 def data(self,rows):return {'records':[{'time':t,'items':o} for t,o in rows]}
 def match(self,data):return assign(data,self.refs,self.cal,.4,.035,.025)[0]
 def test_single_unanchored_glimpse_is_uncertain(self):
  r=self.match(self.data([(0,[self.obs(0)])]))
  self.assertFalse(r[0]['accepted']);self.assertTrue(r[0]['uncertain'])
 def test_repeated_clothing_supports_a_short_track(self):
  r=self.match(self.data([(i/3,[self.obs(i,i)]) for i in range(4)]))
  self.assertTrue(all(f['accepted'][0]['player_id']=='red' for f in r))
 def test_lookalike_profiles_remain_unassigned(self):
  self.refs['blue']=[self.red]
  r=self.match(self.data([(i/3,[self.obs(i,i)]) for i in range(4)]))
  self.assertTrue(all(not f['accepted'] for f in r))
 def test_discontinuous_time_breaks_tracks(self):
  d=self.data([(0,[self.obs(0)]),(3,[self.obs(1)])])
  self.assertEqual(len(tracklets(d)),2)
  self.assertTrue(all(not f['accepted'] for f in self.match(d)))
 def test_incompatible_clothing_breaks_link(self):
  d=self.data([(0,[self.obs(0)]),(.333,[self.obs(1,desc=self.blue)])])
  self.assertEqual(len(tracklets(d)),2)
 def test_conflicting_anchors_cannot_establish_identity(self):
  self.cal['people'][0]['samples']=[{'time':0,'box':[0,0,40,100]}]
  self.cal['people'][1]['samples']=[{'time':1,'box':[3,0,43,100]}]
  r=self.match(self.data([(i/3,[self.obs(i,i)]) for i in range(4)]))
  self.assertTrue(all(not f['accepted'] for f in r))
 def test_crossing_box_is_not_credited_for_wrong_identity(self):
  data=self.data([(0,[self.obs(0)])]);pred={'calibration':self.cal,'records':[{'time':0,'accepted':[{'player_id':'red','box':[10,0,50,100]}]}]}
  truth={'provenance':'synthetic','frames':[{'time':0,'people':{'red':[0,0,40,100],'blue':[10,0,50,100]}}]}
  out=evaluate(data,pred,truth)
  self.assertEqual(out['metrics']['tp'],0);self.assertEqual(out['metrics']['fp'],1)
 def test_finite_color_distance_is_stable_under_small_exposure_change(self):
  darker=descriptor(np.full((100,40,3),(0,0,170),np.uint8),[0,0,40,100])
  self.assertLess(distance(self.red,darker),distance(self.red,self.blue))

if __name__=='__main__':unittest.main()
