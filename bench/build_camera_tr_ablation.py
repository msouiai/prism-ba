#!/usr/bin/env python3
"""Permit one or five shifts in the frozen TR prototype, with no policy edits."""
import pathlib,subprocess,difflib
from expanded_caspar_screen import sha
ROOT=pathlib.Path('/workspace/prism-camera-tr-ablation')
GPU=pathlib.Path(__file__).resolve().parents[1]/'gpu'
def main():
 ROOT.mkdir(exist_ok=True)
 p=pathlib.Path('/workspace/prism-camera-tr/source-tr.cu');s=p.read_text();original=s
 old='L!=5 || demand_mode!=0 || full_model_rho || repair_damping_mode || point_trust_mode ||'
 assert s.count(old)==1
 s=s.replace(old,'(L!=1 && L!=5) || demand_mode!=0 || full_model_rho || repair_damping_mode || point_trust_mode ||')
 s=s.replace('camera TR requires plain FP64 diagonal five-shift mode with point safeguard 1','camera TR requires plain FP64 diagonal one/five-shift mode with point safeguard 1')
 (ROOT/'source-before.cu').write_text(original);(ROOT/'source-tr.cu').write_text(s)
 (ROOT/'width-only.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='source-before.cu',tofile='source-tr.cu')))
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I'+str(GPU),str(ROOT/'source-tr.cu'),'-o',str(ROOT/'prism-tr'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 print('BUILT',sha(ROOT/'prism-tr'),flush=True)
if __name__=='__main__':main()
