#!/usr/bin/env python3
"""Separate point regularization from camera menu placement in early-ray arm."""
import pathlib,subprocess,shutil,difflib
ROOT=pathlib.Path('/workspace/prism-separate-tau');OLD=pathlib.Path('/workspace/prism-early-radius')
def main():
 ROOT.mkdir(exist_ok=True);(ROOT/'tooling').mkdir(exist_ok=True)
 for p in (OLD/'tooling').iterdir():shutil.copy2(p,ROOT/'tooling'/p.name)
 original=(OLD/'source.cu').read_text();s=original
 def edit(a,b):
  nonlocal s
  assert s.count(a)==1,a;s=s.replace(a,b)
 edit('  std::unique_ptr<prism_recycle::Basis> radius_basis;', '  double separate_point_tau=0;\n  std::unique_ptr<prism_recycle::Basis> radius_basis;')
 edit('    if(point_trust_tau>0)tau_eff=point_trust_tau;', '''    if(point_trust_tau>0)tau_eff=point_trust_tau;
    if(radius_mode==2){
      if(!(separate_point_tau>0))separate_point_tau=tau_eff;
      tau_eff=separate_point_tau;
    }''')
 edit('      if(camera_tr){\n        const double anchor=', '''      if(radius_mode==2)
        separate_point_tau=std::max(1e-7,(double)tau_eff*(tr_rho>.75?.25:tr_rho>=.25?.5:1.));
      if(camera_tr){
        const double anchor=''')
 (ROOT/'source.cu').write_text(s);(ROOT/'source-before.cu').write_text(original);(ROOT/'patch.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True))))
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I'+str(ROOT/'tooling'),'-I/usr/include/eigen3',str(ROOT/'source.cu'),'-o',str(ROOT/'prism'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
if __name__=='__main__':main()
