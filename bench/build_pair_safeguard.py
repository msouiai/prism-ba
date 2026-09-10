#!/usr/bin/env python3
import pathlib,shutil,json,subprocess,argparse
from build_tr_candidate import sha,REPO
ROOT=pathlib.Path('/workspace/prism-tr-safeguard/pair')
def main():
 global ROOT
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,default=ROOT);a=ap.parse_args();ROOT=a.output
 base=pathlib.Path('/workspace/prism-tr-reference/rank');m=json.loads((base/'stop-manifest.json').read_text());assert sha(base/'source.cu')==m['source_sha256'];assert all(sha(base/'headers'/k)==v for k,v in m['headers_sha256'].items());ROOT.mkdir();shutil.copytree(base/'headers',ROOT/'headers');shutil.copy2(REPO/'gpu/block_full_model.cuh',ROOT/'headers/block_full_model.cuh');s=(base/'source.cu').read_text();s=s.replace('#include "point_safeguard.cuh"','#include "point_safeguard.cuh"\n#include "block_full_model.cuh"',1)
 marker='    auto ScoreTail=[&]';assert s.count(marker)==1
 s=s.replace(marker,'''    const int pair_mode=getenv("OCA_PAIR_SAFE")?atoi(getenv("OCA_PAIR_SAFE")):0;
    bool pair_active=false;
    // This scratch is allocated only at an actual pair comparison, not every outer.
    struct PairScratch{double*ptr=nullptr;~PairScratch(){if(ptr)cudaFree(ptr);}} pair_raw;
'''+marker)
 marker='      if(backtrack_ready && !have &&';assert s.count(marker)==1
 block='''      if(pair_active && !prepared){
        if(!pair_raw.ptr)CUDA_CHECK(cudaMalloc(&pair_raw.ptr,n*sizeof(Scalar)));
        CUDA_CHECK(cudaMemcpy(pair_raw.ptr,dfull,n*sizeof(Scalar),cudaMemcpyDeviceToDevice));
        const double raw=c;
        const char* capture=getenv("OCA_PAIR_CAPTURE");
        std::string prefix;if(capture){prefix=std::string(capture)+"/o"+std::to_string(k)+"-sh"+std::to_string(sh);prism_cg_save(prefix+".raw",dfull,n*sizeof(Scalar));}
        DoRetract(dfull,s_new);
        auto frozen=point_safeguard->Choose(p,s,s_new,dfull,0);
        DoRetract(dfull,s_new);double safe=ComputeCost(p,s_new,rk,rk_a2);
        auto model=full_model->Evaluate(p,s,dfull,k2mask);double norm=0;cublasDnrm2(blas,n_c,x_scaled,1,&norm);
        bool eligible=std::isfinite(safe)&&model.slope<0&&safe<=cost+1e-4*model.slope&&prism_camera_tr::accept(cost-safe,model.prediction,norm,tr->radius);
        if(capture){prism_cg_save(prefix+".safe",dfull,n*sizeof(Scalar));prism_cg_save(prefix+".R",s.R,9ul*ncam*8);prism_cg_save(prefix+".t",s.t,3ul*ncam*8);prism_cg_save(prefix+".X",s.X,3ul*npt*8);prism_cg_save(prefix+".intr",s.intr,3ul*ncam*8);}
        bool use=pair_mode==2&&eligible&&safe<raw;
        std::printf("PAIR_SAFE o=%d sh=%d depth=%d raw=%.17g safe=%.17g prediction=%.17g slope=%.17g norm=%.17g radius=%.17g frozen=%llu eligible=%d use=%d mode=%d\\n",k,sh,ck,raw,safe,model.prediction,model.slope,norm,tr->radius,frozen,(int)eligible,(int)use,pair_mode);
        if(use)c=safe;else CUDA_CHECK(cudaMemcpy(dfull,pair_raw.ptr,n*sizeof(Scalar),cudaMemcpyDeviceToDevice));
      }
'''
 s=s.replace(marker,block+marker)
 marker='        Score(legacy_tr->best,legacy_tr->best_sh,legacy_tr->best_depth);';s=s.replace(marker,'        pair_active=pair_mode>0 && point_safeguard_mode==1 && tr->best_sh==-2;\n'+marker,1)
 marker='        if(have){tr->best_sh=best_sh;tr->best_depth=best_ck;}';s=s.replace(marker,'        pair_active=false;\n'+marker,1)
 marker='        auto model=full_model->Evaluate(p,s,d_best,k2mask);++full_model_calls;';assert s.count(marker)==1
 s=s.replace(marker,'''        cudaDeviceSynchronize();auto model_start=now();
'''+marker+'''
        if(getenv("OCA_BLOCK_MODEL_AUDIT")){
          cudaDeviceSynchronize();double direct_s=std::chrono::duration<double>(now()-model_start).count();
          PrismBlockModel reused;cudaDeviceSynchronize();auto reused_start=now();auto fast=reused.Evaluate(p,d_best,Hcc,Gp,Bo,bc,bp,blas);cudaDeviceSynchronize();double reused_s=std::chrono::duration<double>(now()-reused_start).count();
          double error=std::abs(fast.prediction-model.prediction)/std::max(1.,std::abs(model.prediction));
          std::printf("BLOCK_MODEL o=%d direct=%.17g reused=%.17g relative_error=%.17g fragment_error_estimate=%.17g direct_s=%.9g reused_s=%.9g\\n",k,model.prediction,fast.prediction,error,fast.fragment_error_estimate,direct_s,reused_s);
        }
''')
 p=ROOT/'source.cu';p.write_text(s);cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(ROOT/'headers'),str(p),'-o',str(ROOT/'prism-tr'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 (ROOT/'stop-manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(p),binary_sha256=sha(ROOT/'prism-tr'),base_source_sha256=m['source_sha256'],headers_sha256={p.name:sha(p) for p in (ROOT/'headers').iterdir()},policy='OCA_PAIR_SAFE=1 diagnostic,2 compare safeguarded raw proposals; each safeguarded proposal checked with direct FP64 full model. Block model is diagnostic only; never used for acceptance.'),indent=2));print(ROOT/'prism-tr')
if __name__=='__main__':main()
