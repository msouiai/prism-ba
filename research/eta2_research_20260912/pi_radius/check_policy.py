#!/usr/bin/env python3
"""Controller-sequence checks, not optimizer performance evidence."""
import math,json
from pathlib import Path
def update(radius,previous,rho,accepted):
    if not accepted:return max(1e-14,.25*radius),previous
    error=max(1e-6,abs(1-rho));previous=previous or error
    factor=min(2,max(.25,math.exp(.3*math.log(.3/error)+.4*math.log(previous/error))))
    return max(1e-14,radius*factor),error
def main():
    r,e=update(1,0,.7,True);assert abs(r-1)<1e-15
    r2,e2=update(r,e,-1,False);assert abs(r2-.25)<1e-15 and e2==e
    a,_=update(1,.8,.9,True);b,_=update(1,.1,.9,True);assert a>b
    assert update(1,.3,1,True)[0]==2
    assert update(1,.3,3,True)[0]<1
    result=dict(equilibrium_radius=r,rejection_history_preserved=True,improving_error_factor=a,
      constant_error_factor=b,rho1_factor=update(1,.3,1,True)[0],rho3_factor=update(1,.3,3,True)[0])
    Path(__file__).with_name('verification.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
if __name__=='__main__':main()
