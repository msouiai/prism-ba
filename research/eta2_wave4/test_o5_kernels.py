"""Finite-difference audit of actual GPU weighted prediction and track scoring."""
from pathlib import Path
import fcntl,json,subprocess,tempfile
import numpy as np
from scipy.spatial.transform import Rotation
import attribution as A
P=Path(__file__).resolve().parent
def main():
 rng=np.random.default_rng(91205);cases=[];references=[]
 for i in range(96):
  R=Rotation.from_rotvec(rng.normal(size=3)).as_matrix();t=rng.normal(size=3)
  Y=rng.normal(size=3);Y[2]=(1 if i%2 else -1)*rng.uniform(.4,4)
  X=R.T@(Y-t);intr=np.array([rng.uniform(100,1000),rng.uniform(-.1,.1),0.])
  uv=A.F.S.chart.project_jacobian(Y[None],intr[None])[0][0]+rng.normal(size=2)*rng.uniform(.1,100)
  dc=rng.normal(size=9)*.02;dc[6]*=100;dc[8]=0;dp=rng.normal(size=3)*.02;a2=10**rng.uniform(-2,6)
  cam=A.F.S.CameraState(R[None],t[None],intr[None]);ci=np.array([0])
  def res(h):return A.F.S.residual(cam.retract(dc[None]*h),(X+dp*h)[None],ci,uv[None])[0][0]
  h=1e-5;r=res(0);jd=(res(h)-res(-h))/(2*h)
  for rk in [0,2]:
   def cost(rr):return .5*(a2*np.log1p(rr@rr/a2) if rk else rr@rr)
   w=1/(1+r@r/a2) if rk else 1.
   slope=(cost(res(h))-cost(res(-h)))/(2*h);curv=w*(jd@jd)
   references.append([slope,curv,-slope-.5*curv,cost(r)])
  cases.append(np.r_[a2,R.ravel(),t,X,intr,uv,dc,dp])
 command=['nvcc','-O2','-std=c++17','-arch=sm_89',str(P/'o5_kernel_test.cu'),'-o',str(P/'build/o5-kernel-test')]
 subprocess.run(command,check=True)
 with tempfile.TemporaryDirectory(dir='/dev/shm',prefix='o5-kernel-') as tmp:
  root=Path(tmp);np.asarray(cases).tofile(root/'input')
  with open('/tmp/prism_gpu.lock','w') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX);subprocess.run([command[-1],str(root/'input'),str(root/'output')],check=True)
  output=np.fromfile(root/'output').reshape(-1,4);ref=np.asarray(references)
 error=np.abs(output-ref)/np.maximum(1,np.abs(ref));assert output.shape==(192,4)
 assert np.max(error)<2e-5,(np.unravel_index(error.argmax(),error.shape),error.max())
 result=dict(passed=True,cases=96,kernel_evaluations=192,max_relative_error=error.max(),columns=['slope','IRLS_GN_curvature','prediction','actual_track_cost'],column_max=error.max(axis=0).tolist(),source_sha256=A.F.sha(P/'o5_kernel_test.cu'),binary_sha256=A.F.sha(command[-1]),command=command)
 A.F.write(P/'o5-kernel-validation.json',result);print(result)
if __name__=='__main__':main()
