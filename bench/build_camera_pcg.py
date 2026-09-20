import pathlib,shutil,subprocess,json,argparse
from build_tr_candidate import sha
repo=pathlib.Path(__file__).resolve().parents[1];base=pathlib.Path('/workspace/prism-tr-point-prep/combined');ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,default=pathlib.Path('/workspace/prism-tr-preconditioner/pcg-v3'));a=ap.parse_args();root=a.output;root.mkdir();m=json.loads((base/'stop-manifest.json').read_text());assert sha(base/'source.cu')==m['source_sha256'];assert all(sha(base/'headers'/k)==v for k,v in m['headers_sha256'].items());shutil.copytree(base/'headers',root/'headers');shutil.copy2(repo/'gpu/pcg_camera.cuh',root/'headers/pcg_camera.cuh');s=(base/'source.cu').read_text()
def sub(a,b):
 global s
 assert s.count(a)==1,(a,s.count(a));s=s.replace(a,b)
sub('__global__ void MFMakeEquil(', '#include "pcg_camera.cuh"\n__global__ void MFMakeEquil(')
sub('  std::unique_ptr<PrismCgProjection> cg_projection;', '  std::unique_ptr<PrismPcg> pcg;\n  if(getenv("OCA_PCG"))pcg=std::make_unique<PrismPcg>(ncam);\n  std::unique_ptr<PrismCgProjection> cg_projection;')
sub('    if(cg_projection){cg_projection->Reset();legacy_tr->Reset();}', '''    if(pcg){
      if(L!=1||CD!=9||shared_intr||block_on||!cg_projection)throw std::runtime_error("PCG requires guarded unshared 9DOF single-shift diagonal-coordinate TR");
      pcg->Prepare(Hcc,E,shifts[0],k,retries,Gp,fragment_points,p.mf_coff,Rf,nobs);pcg->Apply(r_);cublasDdot(blas,n_c,r_,1,pcg->z,1,&pcg->rz);CUDA_CHECK(cudaMemcpy(pv_,pcg->z,n_c*8ul,cudaMemcpyDeviceToDevice));
    }
    if(cg_projection){cg_projection->Reset();legacy_tr->Reset();}''')
sub('      if(cg_projection)cg_projection->Append(r_,Ap_,rr,be_prev,shifts[0]);','''      if(cg_projection){double zz=rr;if(pcg)cublasDdot(blas,n_c,pcg->z,1,pcg->z,1,&zz);cg_projection->Append(pcg?pcg->z:r_,Ap_,zz,be_prev,shifts[0]);}''')
sub('      Scalar al=rr/pAp;', '      Scalar al=(pcg?pcg->rz:rr)/pAp;')
sub('      if(rho_mode) preds[0]+=0.5*al*rr;', '      if(rho_mode) preds[0]+=0.5*al*(pcg?pcg->rz:rr);')
sub('      Scalar be=rr_new/rr;', '''      Scalar be=rr_new/rr;
      if(pcg){pcg->Apply(r_);double next;cublasDdot(blas,n_c,r_,1,pcg->z,1,&next);be=next/pcg->rz;pcg->rz=next;pcg->last_depth=cg_it+1;}''')
sub('      { const Scalar one=1.0; cublasDaxpy(blas,n_c,&one,r_,1,pv_,1); }','      { const Scalar one=1.0; cublasDaxpy(blas,n_c,&one,pcg?pcg->z:r_,1,pv_,1); }')
# Certify convergence against the unchanged true shifted operator.
sub('      if(sqrt(rr_new)<=eta*nb){ cg_broke=true; break; }    // s2.7','''      if(sqrt(rr_new)<=eta*nb){
        if(pcg){KvS(xs[0],pcg->tmp);cublasDaxpy(blas,n_c,&shifts[0],xs[0],1,pcg->tmp,1);const double minus=-1;cublasDaxpy(blas,n_c,&minus,bprime,1,pcg->tmp,1);double true_norm;cublasDnrm2(blas,n_c,pcg->tmp,1,&true_norm);if(!std::isfinite(true_norm)||true_norm>eta*nb)throw std::runtime_error("PCG residual estimate failed reference check");}
        cg_broke=true; break;
      }    // s2.7''')
(root/'source.cu').write_text(s);cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(root/'headers'),str(root/'source.cu'),'-o',str(root/'prism-tr'),'-lcublas','-lcusolver']
with (root/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
(root/'stop-manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(root/'source.cu'),binary_sha256=sha(root/'prism-tr'),headers_sha256={p.name:sha(p) for p in (root/'headers').iterdir()},base_source_sha256=m['source_sha256'],policy='Ordinary PCG on unchanged E S E + sigma I. Camera Hcc block preconditioner. Projection basis captures z and Sz with full Gram; original Euclidean TR and full acceptance retained. Optional lagged preconditioner with scale-invariant diagonal-drift and solve-depth refresh.'),indent=2))
