#!/usr/bin/env python3
import pathlib,shutil,subprocess,difflib
ROOT=pathlib.Path('/workspace/prism-joint-tr');GPU=pathlib.Path(__file__).resolve().parents[1]/'gpu'
def main():
 ROOT.mkdir(exist_ok=True);(ROOT/'tooling').mkdir(exist_ok=True)
 original=pathlib.Path('/workspace/prism-camera-tr-interior/source-tr.cu').read_text();s=original
 def edit(a,b):
  nonlocal s
  assert s.count(a)==1,a;s=s.replace(a,b)
 edit('#include "camera_tr_diagnostic.cuh"','#include "camera_tr_diagnostic.cuh"\n#include "projected_radius.h"\n#include <tuple>')
 edit('  const bool full_model_rho=[]()', '''  const bool joint_mode=getenv("OCA_JOINT_TR")&&atoi(getenv("OCA_JOINT_TR"));
  if(joint_mode&&!camera_tr)throw std::runtime_error("joint TR requires plain camera TR seed");
  double joint_radius=0;long joint_trials=0,joint_model_calls=0;
  std::unique_ptr<PrismSubspaceModel> joint_model;double* joint_seed=nullptr;
  if(joint_mode){joint_model=std::make_unique<PrismSubspaceModel>();CUDA_CHECK(cudaMalloc(&joint_seed,n*8));}
  const bool full_model_rho=[]()''')
 edit('    double tr_rho=-1,tr_norm=0,tr_prediction=0,tr_old_radius=camera_tr?tr->radius:0;', '#include "joint_subspace_tr.inc"\n    double tr_rho=-1,tr_norm=0,tr_prediction=0,tr_old_radius=camera_tr?tr->radius:0;')
 edit('        have=prism_camera_tr::accept(cost-best_cost,tr_prediction,tr_norm,tr_old_radius);', '''        if(joint_checked){
          have=joint_ok && prism_camera_tr::accept(cost-best_cost,tr_prediction,joint_norm,joint_old_radius);
          // Camera radius now controls seed generation, not joint acceptance.
          tr_old_radius=std::max(tr_old_radius,tr_norm);
        }else have=prism_camera_tr::accept(cost-best_cost,tr_prediction,tr_norm,tr_old_radius);''')
 edit('    // ---- accept / reject (existing rule) ----', r'''    if(joint_mode&&getenv("OCA_JOINT_TRACE"))std::printf("JOINT_ACCEPT o=%d checked=%d accept=%d radius=%.17g norm=%.17g prediction=%.17g rho=%.17g next_radius=%.17g\n",k,(int)joint_checked,(int)have,joint_old_radius,joint_norm,joint_prediction,joint_rho,joint_radius);
    // ---- accept / reject (existing rule) ----''')
 start=s.index('RunLog SolveMFreeShiftedCG');end=s.index('\n}',start);idx=s[start:end].rfind('return log;');assert idx>=0
 s=s[:start+idx]+'''if(joint_mode)std::printf("JOINT_SUMMARY trials=%ld model_calls=%ld\\n",joint_trials,joint_model_calls);
  cudaFree(joint_seed);
  '''+s[start+idx:]
 (ROOT/'source.cu').write_text(s);(ROOT/'source-before.cu').write_text(original);(ROOT/'patch.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True))))
 for p in list(GPU.glob('*.h'))+list(GPU.glob('*.cuh'))+list(GPU.glob('*.inc')):shutil.copy2(p,ROOT/'tooling'/p.name)
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I'+str(ROOT/'tooling'),'-I/usr/include/eigen3',str(ROOT/'source.cu'),'-o',str(ROOT/'prism'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
if __name__=='__main__':main()
