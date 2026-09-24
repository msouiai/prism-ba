#!/usr/bin/env python3
"""Instrument a copy of the corrected TR owner, without changing its policy."""
import pathlib,subprocess,difflib,shutil
ROOT=pathlib.Path('/workspace/prism-camera-radius');GPU=pathlib.Path(__file__).resolve().parents[1]/'gpu'
def main():
 ROOT.mkdir(exist_ok=True)
 original=pathlib.Path('/workspace/prism-camera-tr-interior/source-tr.cu').read_text()
 s=original.replace('#include "camera_tr_diagnostic.cuh"','#include "camera_tr_diagnostic.cuh"\n#include "projected_radius.h"')
 s=s.replace('  std::unique_ptr<PrismCameraTR> tr;','  bool radius_captured[7]={false};\n  std::unique_ptr<PrismCameraTR> tr;')
 key='      if(tr->best_prediction>0)Score(tr->best,tr->best_sh,tr->best_depth);'
 assert s.count(key)==1
 s=s.replace(key,'#include "camera_radius_capture.inc"\n'+key)
 (ROOT/'source-before.cu').write_text(original);(ROOT/'source-radius.cu').write_text(s)
 (ROOT/'capture.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True))))
 (ROOT/'tooling').mkdir(exist_ok=True)
 for p in list(GPU.glob('*.h'))+list(GPU.glob('*.cuh'))+list(GPU.glob('*.inc')):shutil.copy2(p,ROOT/'tooling'/p.name)
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I'+str(ROOT/'tooling'),'-I/usr/include/eigen3',str(ROOT/'source-radius.cu'),'-o',str(ROOT/'prism-radius'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
if __name__=='__main__':main()
