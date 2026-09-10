"""KKT checks for scalar quadratic minimization and active contraction."""
import math,random
rng=random.Random(241)
for _ in range(1000):
 bd,curvature,norm,radius=[math.exp(rng.uniform(-8,8)) for _ in range(4)]
 scale=min(radius/norm,bd/curvature)
 assert scale*norm<=radius*(1+1e-12)
 if scale<radius/norm*(1-1e-10):assert abs(bd-scale*curvature)<1e-10*bd
 else:assert bd-scale*curvature>=-1e-10*bd
 old=math.exp(rng.uniform(-8,8));length=old*rng.uniform(.001,1)
 new=max(1e-14,min(.25*old,.5*length));assert new<length
print('1000 scalar KKT and strict contraction checks passed')
