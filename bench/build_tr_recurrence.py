#!/usr/bin/env python3
import pathlib,subprocess,shutil,difflib
ROOT=pathlib.Path('/workspace/prism-tr-recurrence');GPU=pathlib.Path(__file__).resolve().parents[1]/'gpu'
def main():
 ROOT.mkdir(exist_ok=True);(ROOT/'tooling').mkdir(exist_ok=True)
 original=pathlib.Path('/workspace/prism-camera-tr-interior/source-tr.cu').read_text();s=original
 def edit(a,b):
  nonlocal s
  assert s.count(a)==1,a;s=s.replace(a,b)
 edit('  const bool full_model_rho=[]()', '''  const bool tr_fast_model=getenv("OCA_TR_RECURRENCE")&&atoi(getenv("OCA_TR_RECURRENCE"));
  const bool tr_fast_audit=getenv("OCA_TR_RECURRENCE_AUDIT")!=nullptr;
  long tr_fast_calls=0;std::vector<double> tr_residual_scales(5,1.),tr_model_shifts(5,0.);
  if(tr_fast_model&&!camera_tr)throw std::runtime_error("TR recurrence requires camera TR");
  const bool full_model_rho=[]()''')
 edit('        for(int l=0;l<L;++l)tr->Add(xs[l],l,depth,bprime,blas,KvS);', '''        for(int l=0;l<L;++l){
#include "tr_recurrence_score.inc"
        }''')
 edit('    for(int l=0;l<L;++l) shifts[l]=lam_cam*std::pow(10.0,(double)(l-grid_down));',
      '    for(int l=0;l<L;++l) shifts[l]=lam_cam*std::pow(10.0,(double)(l-grid_down));\n    for(int l=0;l<L;++l)tr_model_shifts[l]=shifts[l];')
 edit('        for(int l=0;l<L;++l) shifts[l]*=std::pow((Scalar)10.0,(Scalar)kup);',
      '        for(int l=0;l<L;++l) shifts[l]*=std::pow((Scalar)10.0,(Scalar)kup);\n        for(int l=0;l<L;++l)tr_model_shifts[l]=shifts[l];')
 edit('    std::vector<Scalar> zeta(L,1.0),zprev(L,1.0),znext(L,1.0),als(L,0.0),bes(L,0.0);', '    std::fill(tr_residual_scales.begin(),tr_residual_scales.end(),1.);\n    std::vector<Scalar> zeta(L,1.0),zprev(L,1.0),znext(L,1.0),als(L,0.0),bes(L,0.0);')
 # Scope key occurs only in this solver.
 start=s.index('RunLog SolveMFreeShiftedCG');end=s.index('\n}',start)
 part=s[start:end];a='        zprev[l]=zeta[l]; zeta[l]=znext[l];';assert part.count(a)==1
 part=part.replace(a,a+'\n        tr_residual_scales[l]=zeta[l];');s=s[:start]+part+s[end:]
 idx=part.rfind('return log;');assert idx>=0
 s=s[:start+idx]+'''if(tr_fast_model)std::printf("TR_RECURRENCE_SUMMARY candidates=%ld\\n",tr_fast_calls);
  '''+s[start+idx:]
 (ROOT/'source.cu').write_text(s);(ROOT/'source-before.cu').write_text(original);(ROOT/'patch.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True))))
 for p in list(GPU.glob('*.h'))+list(GPU.glob('*.cuh'))+list(GPU.glob('*.inc')):shutil.copy2(p,ROOT/'tooling'/p.name)
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I'+str(ROOT/'tooling'),str(ROOT/'source.cu'),'-o',str(ROOT/'prism'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
if __name__=='__main__':main()
