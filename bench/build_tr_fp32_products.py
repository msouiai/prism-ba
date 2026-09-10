#!/usr/bin/env python3
"""Isolated guarded-TR prototype: FP32 observation products, FP64 sums/model checks."""
import pathlib,shutil,subprocess,json,argparse
from build_tr_candidate import sha

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,default=pathlib.Path('/workspace/prism-tr-fp32-products/build'));a=ap.parse_args()
 base=pathlib.Path('/workspace/prism-tr-cg-stop/guarded');m=json.loads((base/'stop-manifest.json').read_text());assert sha(base/'source.cu')==m['source_sha256'];assert all(sha(base/'headers'/k)==v for k,v in m['headers_sha256'].items())
 a.output.mkdir(parents=True);shutil.copytree(base/'headers',a.output/'headers');s=(base/'source.cu').read_text()
 start=s.index('template <int CD, class HT>\n__global__ void MFPass1(');end=s.index('// GAP-4090 F2',start)
 p1=s[start:end].replace('MFPass1(', 'MFPass1Products32(').replace('Scalar q=0;', 'float q=0;').replace(']*vc[i]',']*(float)vc[i]').replace('],q);','],(double)q);')
 start=s.index('template <int CD, class HT>\n__global__ void MFPass2(');end=s.index('__global__ void MFBackSub',start)
 p2=s[start:end].replace('MFPass2(', 'MFPass2Products32(').replace('Scalar up[3]={u[3*p],u[3*p+1],u[3*p+2]}','float up[3]={(float)u[3*p],(float)u[3*p+1],(float)u[3*p+2]}').replace('for(int i=0;i<CD;++i){ Scalar q=0;', 'for(int i=0;i<CD;++i){ float q=0;')
 # Keep camera block multiplication and all observation accumulation in double.
 s=s[:end]+p1+p2+s[end:]
 marker='    auto Kv=[&](const Scalar* vin,Scalar* vout){'
 assert s.count(marker)==1
 s=s.replace(marker,'''    const bool fp32_products=getenv("OCA_FP32_PRODUCTS")&&atoi(getenv("OCA_FP32_PRODUCTS"));
    bool fp32_inner=false;
    if(fp32_products && (L!=1 || shared_intr || jit_on || mf_fp32 || compact_mode!=2))throw std::runtime_error("FP32 products requires compact unshared L1 TR");
'''+marker)
 marker='      else       { MFPass1<CD,Fragment>'
 assert s.count(marker)==1
 s=s.replace(marker,'''      else if(fp32_inner){
        MFPass1Products32<CD,Fragment><<<GridSize(nobs),256>>>(Gp,fragment_cams,fragment_points,vf,nobs,tacc);
        MFVinvApply<<<GridSize(npt),256>>>(Rf,tacc,npt,uu);
        MFPass2Products32<CD,Fragment><<<ncam,256>>>(Gc?Gc:Gp,p.mf_cspt,p.mf_coff,uu,Hcc,vf,nobs,wf,fragment_slots);
      }
'''+marker)
 marker='      KvS(pv_,Ap_);';assert s.count(marker)==1
 s=s.replace(marker,'      fp32_inner=fp32_products;\n'+marker+'\n      fp32_inner=false;')
 h=a.output/'headers/tr_recurrence_score.inc';txt=h.read_text();txt=txt.replace(' if(tr_fast_audit){',' if(tr_fast_audit || fp32_products){').replace('  if(error>1e-7)throw', '  if(!fp32_products && error>1e-7)throw');txt=txt.replace('  std::printf("TR_RECURRENCE', '  if(tr_fast_audit)std::printf("TR_RECURRENCE');txt=txt.replace('  if(!fp32_products && error>1e-7)', '  if(fp32_products)e.curvature=explicit_c;\n  if(!fp32_products && error>1e-7)');h.write_text(txt)
 # Diagnostic true residual, evaluated against the FP64 reference operator.
 marker='#include "cg_tr_projection_step.inc"';assert s.count(marker)==1
 s=s.replace(marker,'''if(fp32_products && getenv("OCA_FP32_RESIDUAL_AUDIT") && (cg_it+1)%16==0){
 KvS(xs[0],tr->ax);
 double sh=shifts[0],minus=-1,one=1;
 cublasDaxpy(blas,n_c,&sh,xs[0],1,tr->ax,1);
 cublasDaxpy(blas,n_c,&minus,bprime,1,tr->ax,1);
 double true_norm=0,gap=0;cublasDnrm2(blas,n_c,tr->ax,1,&true_norm);
 cublasDaxpy(blas,n_c,&one,r_,1,tr->ax,1);cublasDnrm2(blas,n_c,tr->ax,1,&gap);
 std::printf("FP32_RESIDUAL o=%d depth=%d true_relative=%.17g gap_relative=%.17g\\n",k,cg_it+1,true_norm/std::max(1e-300,(double)nb),gap/std::max(1e-300,(double)nb));
 if(!std::isfinite(gap)||gap>1e-3*nb)throw std::runtime_error("FP32 residual gap exceeds diagnostic budget");
}
'''+marker)
 p=a.output/'source.cu';p.write_text(s)
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(a.output/'headers'),str(p),'-o',str(a.output/'prism-tr'),'-lcublas','-lcusolver']
 with (a.output/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 manifest=dict(command=cmd,source_sha256=sha(p),binary_sha256=sha(a.output/'prism-tr'),base_source_sha256=m['source_sha256'],headers_sha256={p.name:sha(p) for p in (a.output/'headers').iterdir()},precision='FP32 local observation products only during CG; FP64 accumulation, point solve, block product/subtraction, state, reductions, explicit checkpoint curvature and projection verification/full nonlinear acceptance. Opt-in OCA_FP32_PRODUCTS=1.')
 (a.output/'stop-manifest.json').write_text(json.dumps(manifest,indent=2));print(a.output/'prism-tr')
if __name__=='__main__':main()
