#!/usr/bin/env python3
"""Follow-up fixed after both adaptive and persistent-ray studies lost."""
import pathlib,subprocess,shutil,difflib
ROOT=pathlib.Path('/workspace/prism-early-radius');OLD=pathlib.Path('/workspace/prism-adaptive-radius')
def main():
 ROOT.mkdir(exist_ok=True);(ROOT/'tooling').mkdir(exist_ok=True)
 for p in (OLD/'tooling').iterdir():shutil.copy2(p,ROOT/'tooling'/p.name)
 original=(OLD/'source.cu').read_text();s=original
 a='if(!radius_ready && radius_mode!=2 && tr->best_prediction>0)';b='if(!radius_ready && (radius_mode!=2 || k>0) && tr->best_prediction>0)';assert s.count(a)==1;s=s.replace(a,b)
 a='if(radius_mode && !have && tr_norm>0)';b='if(radius_mode && k==0 && !have && tr_norm>0)';assert s.count(a)==1;s=s.replace(a,b)
 p=ROOT/'tooling/adaptive_radius_select.inc';h=p.read_text();a='if(radius_mode && (radius_ready || radius_mode==2))';assert h.count(a)==1;p.write_text(h.replace(a,'if(radius_mode==2 && k==0)'))
 (ROOT/'source.cu').write_text(s);(ROOT/'source-before.cu').write_text(original);(ROOT/'patch.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True))))
 (ROOT/'selection.patch').write_text(''.join(difflib.unified_diff(h.splitlines(True),p.read_text().splitlines(True))))
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I'+str(ROOT/'tooling'),'-I/usr/include/eigen3',str(ROOT/'source.cu'),'-o',str(ROOT/'prism'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
if __name__=='__main__':main()
