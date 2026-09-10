#!/usr/bin/env python3
import math
import numpy as np
from rl_actor_study import NF,initial,softmax,samples,progress

def main():
    rng=np.random.default_rng(17);W=rng.normal(size=(3,NF))*.1;x=rng.normal(size=NF);R=np.array([.2,-.4,.7])
    p=softmax(W,x);grad=p[:,None]*(R-p@R)[:,None]*x
    error=0
    for i in range(3):
        for j in range(NF):
            h=1e-6;A=W.copy();B=W.copy();A[i,j]+=h;B[i,j]-=h
            fd=(softmax(A,x)@R-softmax(B,x)@R)/(2*h);error=max(error,abs(fd-grad[i,j]))
    assert error<1e-8
    # Same physical progress and elapsed time, split into one or two outers.
    # Time+potential is invariant; sum of gain rates doubles.
    W=initial(3);x=np.zeros(NF);x[0]=1
    event=dict(type='actor',outer=0,action=0,sampled=True,seconds=0,cost=100,initial_cost=100,
        features=x.tolist(),probabilities=softmax(W,x).tolist())
    task=dict(target=10,cap=2,reference_seconds=1)
    one=dict(target_seconds=1,seconds=1,audit_cost=10,events=[event,dict(type='actor_outer',outer=1,seconds=1,cost=10)])
    two=dict(target_seconds=1,seconds=1,audit_cost=10,events=[event,
        dict(type='actor_outer',outer=1,seconds=.5,cost=math.sqrt(1000)),dict(type='actor_outer',outer=2,seconds=1,cost=10)])
    assert abs(samples(one,task,'time',W)[0]['return_value'])<1e-12
    assert abs(samples(two,task,'time',W)[0]['return_value'])<1e-12
    assert abs(samples(one,task,'rate',W)[0]['return_value']-1)<1e-12
    assert abs(samples(two,task,'rate',W)[0]['return_value']-2)<1e-12
    failed=dict(seconds=2,audit_cost=20,events=[event,dict(type='actor_outer',outer=1,seconds=2,cost=20)])
    assert samples(failed,task,'time',W)[0]['return_value']==-9
    assert progress(1,100,10)==1 and progress(100,100,10)==0
    print('PASS: softmax gradient finite differences, error',error,'potential identity, gain-rate counterexample, failure penalty')
if __name__=='__main__':main()
