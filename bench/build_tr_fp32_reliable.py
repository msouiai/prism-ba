#!/usr/bin/env python3
"""Add reference-residual checks and an FP64 CG restart to the product prototype."""
import pathlib,shutil,json,subprocess
from build_tr_candidate import sha
ROOT=pathlib.Path('/workspace/prism-tr-fp32-products/reliable')
def main():
 base=ROOT.parent/'build';m=json.loads((base/'stop-manifest.json').read_text());assert sha(base/'source.cu')==m['source_sha256'];assert all(sha(base/'headers'/k)==v for k,v in m['headers_sha256'].items());ROOT.mkdir();shutil.copytree(base/'headers',ROOT/'headers');s=(base/'source.cu').read_text()
 s=s.replace('bool fp32_inner=false;', 'bool fp32_inner=false, fp32_active=fp32_products, fp32_restarted=false;')
 s=s.replace('fp32_inner=fp32_products;', 'fp32_inner=fp32_active;')
 s=s.replace('if(cg_projection)cg_projection->Append', 'if(cg_projection && !fp32_restarted)cg_projection->Append')
 s=s.replace('if(fp32_products && getenv("OCA_FP32_RESIDUAL_AUDIT") && (cg_it+1)%16==0){','if(fp32_products && ((cg_it+1)%16==0 || sqrt(rr_new)<=eta*nb)){')
 # ax remains A*x-b until after the true residual norm is computed; save it in Ap.
 s=s.replace('double true_norm=0,gap=0;cublasDnrm2', 'CUDA_CHECK(cudaMemcpy(Ap_,tr->ax,n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));\n double true_norm=0,gap=0;cublasDnrm2')
 s=s.replace(' std::printf("FP32_RESIDUAL', ' if(getenv("OCA_FP32_RESIDUAL_AUDIT"))std::printf("FP32_RESIDUAL')
 s=s.replace(' if(!std::isfinite(gap)||gap>1e-3*nb)throw std::runtime_error("FP32 residual gap exceeds diagnostic budget");', ''' if(!std::isfinite(gap)||!std::isfinite(true_norm))throw std::runtime_error("nonfinite reference residual");
 const double budget=std::min(1e-3,.1*(double)eta)*nb;
 if(gap>budget || (sqrt(rr_new)<=eta*nb && true_norm>eta*nb)){
  // Reliable residual replacement. Drop conjugacy and the old projected basis.
  CUDA_CHECK(cudaMemcpy(r_,Ap_,n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
  cublasDscal(blas,n_c,&minus,r_,1);
  CUDA_CHECK(cudaMemcpy(pv_,r_,n_c*sizeof(Scalar),cudaMemcpyDeviceToDevice));
  rr=rr_new=true_norm*true_norm;al_prev=1;be_prev=0;
  fp32_active=false;fp32_restarted=true;if(cg_projection)cg_projection->Reset();
  std::printf("FP32_FALLBACK o=%d depth=%d gap_relative=%.17g budget_relative=%.17g\\n",k,cg_it+1,gap/nb,budget/nb);
 }
''')
 h=ROOT/'headers/cg_tr_projection_step.inc';t=h.read_text();t=t.replace('if(cg_projection &&', 'if(cg_projection && !fp32_restarted &&');h.write_text(t)
 p=ROOT/'source.cu';p.write_text(s);cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(ROOT/'headers'),str(p),'-o',str(ROOT/'prism-tr'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 (ROOT/'stop-manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(p),binary_sha256=sha(ROOT/'prism-tr'),base_source_sha256=m['source_sha256'],headers_sha256={p.name:sha(p) for p in (ROOT/'headers').iterdir()},precision=m['precision'],residual_policy='Reference every16 and on estimated convergence; restart CG from true residual and use FP64 products for remainder of this outer solve if gap > min(.001,.1*eta)*norm(b) or convergence is false. Discard projected basis after restart.'),indent=2));print(ROOT/'prism-tr')
if __name__=='__main__':main()
