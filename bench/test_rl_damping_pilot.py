"""Verify causal timing integration and leakage-free family splits."""
import unittest
import numpy as np
from rl_damping_pilot import curve_score, fit_predict

class ReturnTests(unittest.TestCase):
    def test_cost_is_not_credited_before_accept(self):
        row={'events':[{'type':'outer','dt':1.,'cost0':100.,'cost':50.},
                       {'type':'outer','dt':1.,'cost0':50.,'cost':25.}]}
        self.assertEqual(curve_score(row,.5),{'auc':1.,'progress':0.})
        self.assertAlmostEqual(curve_score(row,1.5)['auc'],1.25/1.5)
        self.assertAlmostEqual(curve_score(row,1.5)['progress'],.5)
        self.assertAlmostEqual(curve_score(row,2.)['auc'],.75)
        self.assertAlmostEqual(curve_score(row,2.)['progress'],.75)

    def test_rejection_time_counts(self):
        row={'events':[{'type':'outer','dt':2.,'cost0':100.,'cost':100.},
                       {'type':'outer','dt':1.,'cost0':100.,'cost':10.}]}
        self.assertEqual(curve_score(row,2.5),{'auc':1.,'progress':0.})

    def test_heldout_labels_cannot_change_prediction(self):
        X=np.arange(24,dtype=float).reshape(6,4)
        Y=np.arange(18,dtype=float).reshape(6,3)*.001
        groups=['a','a','b','b','c','c']
        p,_=fit_predict(X,Y,groups)
        Y[0:2]+=1000
        q,_=fit_predict(X,Y,groups)
        np.testing.assert_array_equal(p[0:2],q[0:2])

if __name__=='__main__':unittest.main()
