#!/usr/bin/env python3
"""Isolated TR experiment: compact FP32 fragments, FP64 compute/state/acceptance."""
import pathlib,subprocess,json,re,argparse
from build_tr_candidate import sha,REPO

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,default=pathlib.Path('/workspace/prism-tr-mixed/storage'));ap.add_argument('--point-double',action='store_true');ap.add_argument('--source-only',action='store_true');a=ap.parse_args()
 if (a.output/'source.cu').exists():raise SystemExit('Refusing to overwrite an existing build; choose a fresh --output')
 subprocess.run(['python3',str(REPO/'bench/build_tr_candidate.py'),'--output',str(a.output),'--source-only'],check=True)
 p=a.output/'source.cu';s=p.read_text();start=s.index('  Scalar *Hcc=nullptr,*Cdiag=nullptr,*Gp=nullptr,*Gc=nullptr,*Bo=nullptr,*bc=nullptr,');end=s.index('  cudaFree(Hcc);cudaFree(Cdiag);cudaFree(Gp);',start)
 body=s[start:end]
 body=body.replace('Scalar *Hcc=nullptr,*Cdiag=nullptr,*Gp=nullptr,*Gc=nullptr,*Bo=nullptr,*bc=nullptr,','using Fragment = float;\n  Fragment *Gp=nullptr,*Gc=nullptr,*Bo=nullptr;\n  Scalar *Hcc=nullptr,*Cdiag=nullptr,*bc=nullptr,',1)
 body='  if(!camera_tr || mf_fp32) throw std::runtime_error("mixed storage experiment requires camera TR without --mf-fp32");\n  std::printf("MIXED_STORAGE fragments=fp32 arithmetic=fp64 state=fp64 acceptance=fp64\\n");\n'+body
 for name in ['MFAssemble','MFPointFactor','MFPointFactorObs','MFRhsDiagCamera','MFRhsPrime','MFDiagK','MFBlockSchurCM','MFBlockSchur','MFPass1','MFPass2','MFPass1Stride','MFPass1Multi']:
  body=re.sub(r'('+name+r'<(?:CD,)?)Scalar',r'\1Fragment',body)
 for name in ['Gp','Gc','Bo']:
  body=re.sub(r'(M\(\(void\*\*\)&'+name+r',[^;]*?)sizeof\(Scalar\)',r'\1sizeof(Fragment)',body)
 body=body.replace('storage=fp64 camera_reads=', 'storage=fp32 camera_reads=')
 body=body.replace('3*CD*sizeof(Scalar)-sizeof(int)','3*CD*sizeof(Fragment)-sizeof(int)')
 s=s[:start]+body+s[end:]
 if a.point_double:
  s=s.replace('template <int CD, class HT>\n__global__ void MFAssemble(', 'template <int CD, class HT, class BT=HT>\n__global__ void MFAssemble(',1)
  s=s.replace('HT* __restrict__ Bo,Scalar* __restrict__ bc','BT* __restrict__ Bo,Scalar* __restrict__ bc',1)
  s=s.replace('Bo[6*o+j]=(HT)gx[CD+j]; Bo[6*o+3+j]=(HT)gy[CD+j];','Bo[6*o+j]=(BT)gx[CD+j]; Bo[6*o+3+j]=(BT)gy[CD+j];',1)
  s=s.replace('Fragment *Gp=nullptr,*Gc=nullptr,*Bo=nullptr;', 'Fragment *Gp=nullptr,*Gc=nullptr; Scalar *Bo=nullptr;',1)
  s=s.replace('MFAssemble<CD,Fragment>', 'MFAssemble<CD,Fragment,Scalar>')
  s=s.replace('MFPointFactor<Fragment>', 'MFPointFactor<Scalar>').replace('MFPointFactorObs<Fragment>', 'MFPointFactorObs<Scalar>')
  s=s.replace('&Bo,6ul*nobs*sizeof(Fragment)', '&Bo,6ul*nobs*sizeof(Scalar)')
  s=s.replace('MIXED_STORAGE fragments=fp32', 'MIXED_STORAGE point_jacobian=fp64 fragments=fp32')
 p.write_text(s)
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I'+str(a.output/'headers'),str(p),'-o',str(a.output/'prism-tr'),'-lcublas','-lcusolver']
 if not a.source_only:
  with (a.output/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 (a.output/'mixed-manifest.json').write_text(json.dumps(dict(source_sha256=sha(p),binary_sha256=sha(a.output/'prism-tr') if not a.source_only else None,command=cmd,point_double=a.point_double,precision='float W=A^T B storage; point Jacobian '+('double' if a.point_double else 'float')+'; double assembly, factors, operator arithmetic, reductions, state, objective and full-model acceptance'),indent=2))
 print(p if a.source_only else a.output/'prism-tr')
if __name__=='__main__':main()
