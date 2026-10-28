"""Research binding only; rejected trials never alter the production detector."""
CONFIG = {'hoop_conf': 0.08, 'margin': 16, 'max_gap': 2.5, 'min_descent': 20, 'dedupe': 0.8, 'sample_fps': 3, 'detector_conf': 0.15}

def propose(records,duration,ranges):
 from engine import propose as research_propose
 return research_propose(records,duration,ranges,CONFIG)
