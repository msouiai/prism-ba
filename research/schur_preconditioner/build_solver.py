#!/usr/bin/env python3
"""Opt-in Gram Schur-block PCG; fixed forcing only, no policy/replay compatibility claim."""
import pathlib,hashlib,json,subprocess,shutil
ROOT=pathlib.Path(__file__).resolve().parent;pkg=ROOT.parent/'eta2_champion';out=ROOT/'build'
headers=out/'solver_headers';headers.mkdir(exist_ok=True,parents=True)
for path in (pkg/'source/headers').iterdir():shutil.copy2(path,headers/path.name)
s=(pkg/'source/prism_eta2.cu').read_text()
assert hashlib.sha256(s.encode()).hexdigest()=='22c18359a526526ae0a5b5109187878ab1cef33b453f6bbddc2aa92597a607d8'
manifest=json.loads((pkg/"source_manifest.json").read_text())
assert all(hashlib.sha256((pkg/"source/headers"/name).read_bytes()).hexdigest()==h for name,h in manifest["headers_sha256"].items()), "Frozen header changed"
s=s.replace('!pcg || pcg->reuse || pcg->schur || demand_mode','!pcg || pcg->reuse || (pcg->schur&&!pcg->gram) || demand_mode')
needle='  const char* replay_save=rld.enabled?'
gate='''  if(pcg && pcg->gram_mode){
    if(!rld.enabled || rld.fixed_eta!=2 || rld.actor || rld.collect || rld.controller ||
       rld.policy || rld.episode || compact_mode!=2 || getenv("OCA_RLD_ACTION") ||
       getenv("OCA_RLD_OPENING") || getenv("OCA_RLD_SAVE") || getenv("OCA_RLD_LOAD") ||
       getenv("OCA_REPLAY_SAVE") || getenv("OCA_REPLAY_LOAD"))
      throw std::runtime_error("Gram PCG research gate requires fixed eta2, compact2 and no policy/replay");
    std::printf("PCG_GRAM enabled=1 fresh_schur_blocks=1\\n");
  }
'''
assert s.count(needle)==1;s=s.replace(needle,gate+needle)
p=headers/'pcg_camera.cuh';h=p.read_text().replace('#pragma once','#pragma once\n#include "gram.cuh"').replace('bool reuse,schur;','bool reuse,schur,gram;')
h=h.replace('schur(getenv("OCA_PCG_SCHUR")!=nullptr){','schur(getenv("OCA_PCG_SCHUR")!=nullptr),gram(getenv("OCA_PCG_GRAM")&&atoi(getenv("OCA_PCG_GRAM"))!=0){schur=schur||gram;')
h=h.replace('bool reuse,schur,gram;', 'bool reuse,schur,gram;int gram_mode=0;')
h=h.replace('schur=schur||gram;', 'gram_mode=getenv("OCA_PCG_GRAM")?atoi(getenv("OCA_PCG_GRAM")):0;if(gram_mode<0||gram_mode>2)throw std::runtime_error("Gram PCG mode must be 0,1,2");schur=schur||gram;')
h=h.replace('MFBlockSchurCM<9,float><<<nc,32>>>(W,pt,off,R,no,B);','if(gram)SchurGram<9,float><<<nc,32>>>(W,pt,off,R,no,B);else MFBlockSchurCM<9,float><<<nc,32>>>(W,pt,off,R,no,B);')
assert 'if(gram)SchurGram' in h;p.write_text(h);shutil.copy2(ROOT/'gram.cuh',headers/'gram.cuh')

needle='      pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);'
assert s.count(needle)==1
s=s.replace(needle,'      if(pcg->gram_mode==2){pcg->gram=false;pcg->schur=false;}\n'+needle)
needle='      }    // s2.7\n    }'
upgrade=r'''      }    // s2.7
      // Fixed-matrix PCG restart after eight unsuccessful Hcc iterations.
      // Preserve x, recompute the true residual, replace M and reset p=M^-1 r.
      // All setup and the residual-check matvec are charged; total cap unchanged.
      if(pcg && pcg->gram_mode==2 && cg_it+1==8 && !pcg->gram){
        KvS(xs[0],Ap_);cublasDaxpy(blas,n_c,&shifts[0],xs[0],1,Ap_,1);
        CUDA_CHECK(cudaMemcpy(r_,bprime,n_c*8ul,cudaMemcpyDeviceToDevice));
        const double minus=-1;cublasDaxpy(blas,n_c,&minus,Ap_,1,r_,1);
        cublasDdot(blas,n_c,r_,1,r_,1,&rr);
        if(std::sqrt(rr)<=eta*nb){cg_broke=true;break;}
        pcg->gram=true;pcg->schur=true;
        pcg->Prepare(Hcc,E,shifts[0],k,1,Gp,fragment_points,p.mf_coff,Rf,nobs);
        pcg->Apply(r_);cublasDdot(blas,n_c,r_,1,pcg->z,1,&pcg->rz);
        CUDA_CHECK(cudaMemcpy(pv_,pcg->z,n_c*8ul,cudaMemcpyDeviceToDevice));
        std::printf("PCG_UPGRADE outer=%d after_iterations=8 relative=%.17g tolerance=%.17g\n",k,std::sqrt(rr)/nb,(double)eta);
      }
    }'''
assert s.count(needle)==1;s=s.replace(needle,upgrade)
(out/'solver.cu').write_text(s)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(headers),str(out/'solver.cu'),'-o',str(out/'prism-gram'),'-lcublas','-lcusolver']
with (out/'build-solver.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
(out/'solver_manifest.json').write_text(json.dumps({'command':cmd,'source_sha256':hashlib.sha256(s.encode()).hexdigest(),'pcg_header_sha256':hashlib.sha256(h.encode()).hexdigest(),'gram_sha256':hashlib.sha256((ROOT/'gram.cuh').read_bytes()).hexdigest(),'binary_sha256':hashlib.sha256((out/'prism-gram').read_bytes()).hexdigest()},indent=2))
