#!/usr/bin/env python3
import pathlib,subprocess,shutil,difflib
ROOT=pathlib.Path('/workspace/prism-adaptive-radius');GPU=pathlib.Path(__file__).resolve().parents[1]/'gpu'
def main():
 ROOT.mkdir(exist_ok=True);original=pathlib.Path('/workspace/prism-camera-tr-interior/source-tr.cu').read_text();s=original
 def edit(a,b):
  nonlocal s
  assert s.count(a)==1,a;s=s.replace(a,b)
 edit('#include "camera_tr_diagnostic.cuh"','#include "camera_tr_diagnostic.cuh"\n#include "projected_radius.h"')
 edit('  const bool full_model_rho=[]()', '''  const int radius_mode=getenv("OCA_ADAPT_RADIUS")?atoi(getenv("OCA_ADAPT_RADIUS")):0;
  if(radius_mode && (!camera_tr || radius_mode<1 || radius_mode>2))throw std::runtime_error("adaptive radius requires camera TR and mode 1/2");
  std::unique_ptr<prism_recycle::Basis> radius_basis;
  double *radius_x=nullptr,*radius_ax=nullptr;
  if(radius_mode){CUDA_CHECK(cudaMalloc(&radius_x,n_c*8));CUDA_CHECK(cudaMalloc(&radius_ax,n_c*8));}
  if(radius_mode==1)radius_basis=std::make_unique<prism_recycle::Basis>(n_c,128);
  const bool full_model_rho=[]()''')
 edit('    if(tr_reuse){tr->Reconsider(blas);projected_ok=true;}', '    if(tr_reuse){tr->Reconsider(blas);projected_ok=true;}\n#include "adaptive_radius_solve.inc"')
 edit('      if(tr->best_prediction>0)Score(tr->best,tr->best_sh,tr->best_depth);','''      if(!radius_ready && radius_mode!=2 && tr->best_prediction>0)Score(tr->best,tr->best_sh,tr->best_depth);
#include "adaptive_radius_select.inc"''')
 edit('      if(!have && tr->radius>=tr_old_radius)tr->radius=std::max(1e-14,.25*tr_old_radius);','''      if(!have && tr->radius>=tr_old_radius)tr->radius=std::max(1e-14,.25*tr_old_radius);
      if(radius_mode && !have && tr_norm>0)tr->radius=std::max(1e-14,std::min(tr->radius,.5*tr_norm));''')
 edit('double placement=anchor*std::pow(tr_old_radius/tr->radius,2.);','double placement=(radius_selected_lambda>=0?radius_selected_lambda:anchor)*std::pow(tr_old_radius/tr->radius,2.);')
 # Free at normal function return; allocations are bounded per solve.
 start=s.index('RunLog SolveMFreeShiftedCG');end=s.index('\n}',start)
 # Find final return within this function (not returns in local lambdas).
 part=s[start:end];idx=part.rfind('return log;')
 assert idx>=0
 s=s[:start+idx]+'cudaFree(radius_x);cudaFree(radius_ax);\n  '+s[start+idx:]
 (ROOT/'source.cu').write_text(s);(ROOT/'source-before.cu').write_text(original)
 (ROOT/'patch.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True))))
 (ROOT/'tooling').mkdir(exist_ok=True)
 for p in list(GPU.glob('*.h'))+list(GPU.glob('*.cuh'))+list(GPU.glob('*.inc')):shutil.copy2(p,ROOT/'tooling'/p.name)
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I'+str(ROOT/'tooling'),'-I/usr/include/eigen3',str(ROOT/'source.cu'),'-o',str(ROOT/'prism'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
if __name__=='__main__':main()
