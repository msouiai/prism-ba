#!/usr/bin/env python3
"""Shared interior-step damping relaxation for both menu widths; isolated revision."""
import pathlib,subprocess,difflib
ROOT=pathlib.Path('/workspace/prism-camera-tr-interior')
GPU=pathlib.Path(__file__).resolve().parents[1]/'gpu'
def main():
 ROOT.mkdir(exist_ok=True)
 original=pathlib.Path('/workspace/prism-camera-tr-ablation/source-tr.cu').read_text()
 old='lam_cam=std::clamp(anchor*std::pow(tr_old_radius/tr->radius,2.),(double)lam_floor,1e8);'
 assert original.count(old)==1
 new='''// A feasible interior step with an adequate model must not leave
        // the menu permanently at a positive damping. Move at least one
        // menu decade downward; this is a placement heuristic, not a KKT solve.
        double placement=anchor*std::pow(tr_old_radius/tr->radius,2.);
        if(tr_norm<.8*tr_old_radius && tr_rho>=.25)
          placement=std::min(placement,.1*(double)lam_cam);
        lam_cam=std::clamp(placement,(double)lam_floor,1e8);'''
 s=original.replace(old,new)
 (ROOT/'source-before.cu').write_text(original);(ROOT/'source-tr.cu').write_text(s)
 (ROOT/'interior-only.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='source-before.cu',tofile='source-tr.cu')))
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I'+str(GPU),str(ROOT/'source-tr.cu'),'-o',str(ROOT/'prism-tr'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
if __name__=='__main__':main()
