#!/usr/bin/env python3
"""Invoke the unchanged scorer with real hold-out file access forbidden."""
import runpy,sys
from policy import ROOT,install_holdout_guard
if '--include-holdout' in sys.argv:raise SystemExit('FINAL_EVALUATION_ONLY')
install_holdout_guard(None)
sys.path.insert(0,str(ROOT/'eval'))
runpy.run_path(str(ROOT/'eval/score.py'),run_name='__main__')
