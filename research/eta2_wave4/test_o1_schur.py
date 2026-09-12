"""Repeat independent tiny tests on the preconditioner-only O1 follow-up."""
from pathlib import Path
import fcntl,json,os,subprocess
import test_o1 as T
P=T.P
def main():
 source=(P/'o1_kernel_test.cu').read_text().replace('#include "o1.cuh"','#include "'+str(P/'o1_schur.cuh')+'"')
 src=P/'build/o1-schur-test.cu';src.write_text(source);b=P/'build/o1-schur-test'
 cmd=['nvcc','-O3','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',str(src),'-o',str(b),'-lcublas']
 with (P/'build/o1-schur-test-build.log').open('w') as f:subprocess.run(cmd,env=dict(os.environ,TMPDIR='/dev/shm'),stdout=f,stderr=subprocess.STDOUT,check=True)
 rows=[]
 with open('/tmp/prism_gpu.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  for mode in range(6):
   dest=P/'build'/f'o1-schur-qp-{mode}.json';log=P/'build'/f'o1-schur-qp-{mode}.log'
   with log.open('w') as f:subprocess.run(['compute-sanitizer','--tool','memcheck','--error-exitcode','97',str(b),str(dest),str(mode)],stdout=f,stderr=subprocess.STDOUT,check=True)
   assert 'ERROR SUMMARY: 0 errors' in log.read_text();rows.append(T.check(dest));print(rows[-1],flush=True)
 result=dict(passed=all(r['passed'] for r in rows),rows=rows,binary_sha256=T.sha(b),header_sha256=T.sha(P/'o1_schur.cuh'),command=cmd)
 (P/'o1-schur-kernel-validation.json').write_text(json.dumps(result,indent=2)+'\n');assert result['passed']
if __name__=='__main__':main()
