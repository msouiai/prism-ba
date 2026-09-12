"""Reversible O1 opening overlay; no edits of frozen code or configuration."""
from pathlib import Path
import hashlib,importlib.util,json,os,subprocess
P=Path(__file__).resolve().parent;W=P.parent/'eta2_wave3';F=P.parent/'eta2_champion'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def derive():
 spec=importlib.util.spec_from_file_location('o1_parent',W/'build.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 old,n=m.derive();s=old;patches=[]
 def patch(a,b):
  nonlocal s
  assert s.count(a)==1,(a[:100],s.count(a));s=s.replace(a,b);patches.append((a,b))
 a='#include "oca_rigfisheye.cuh"'
 patch(a,a+'\n#include <functional>\n#include <map>\n#include <Eigen/Dense>\n#include "'+str(P/'o1.cuh')+'"')
 a='  CsvOpen("mfree_shifted_cg", g_csv_problem.c_str()); CsvRow(0, (double)cost);'
 patch(a,a+'''
  const int o1_sweeps=getenv("OCA_O1_SWEEPS")?atoi(getenv("OCA_O1_SWEEPS")):0;
  if(o1_sweeps){
    if(CD!=9||shared_intr||rk||mf_fp32||!classical_lm||!attr_radius||L!=1||!(o1_sweeps==3||o1_sweeps==5||o1_sweeps==10))
      throw std::runtime_error("O1 requires frozen Eta2 and k=3/5/10");
    O1::opening(p,s,o1_sweeps,BudgetExpired);
    cost=ComputeCost(p,s,0,0);prev_cost=cost;log.costs.back()=cost;CsvRow(0,cost);
  }
''')
 restored=s
 for a,b in reversed(patches):assert restored.count(b)==1;restored=restored.replace(b,a)
 assert restored==old
 return s,n+len(patches)
def main():
 subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
 s,n=derive();b=P/'build';src=b/'o1.cu';src.write_text(s)
 parent=json.loads((W/'build_manifest.json').read_text());cmd=parent['command'].copy()
 cmd[cmd.index(str(W/'build/prism_wave3.cu'))]=str(src);cmd[cmd.index('-o')+1]=str(b/'prism-o1')
 with (b/'o1-build.log').open('w') as f:subprocess.run(cmd,env=dict(os.environ,TMPDIR='/dev/shm'),stdout=f,stderr=subprocess.STDOUT,check=True)
 bm=dict(command=cmd,binary_sha256=sha(b/'prism-o1'),source_sha256=sha(src),reversible_patch_count=n,frozen_source_sha256=sha(F/'source/prism_eta2.cu'),champion_sha256=sha(F/'champion.json'),protocol_sha256=sha(P/'O1_PROTOCOL.md'),sources={**parent['sources'],**{str(p):sha(p) for p in [P/'o1.cuh',P/'build_o1.py']}})
 (P/'o1_build_manifest.json').write_text(json.dumps(bm,indent=2)+'\n');print('BUILT O1',bm['binary_sha256'],flush=True)
if __name__=='__main__':main()
