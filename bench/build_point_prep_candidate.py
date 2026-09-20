#!/usr/bin/env python3
import pathlib,shutil,subprocess,json,argparse
from build_tr_candidate import sha
ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,required=True);ap.add_argument('--cholesky',action='store_true');a=ap.parse_args();root=a.output;root.mkdir();base=pathlib.Path('/workspace/prism-tr-safeguard/factored');m=json.loads((base/'stop-manifest.json').read_text());assert sha(base/'source.cu')==m['source_sha256'];assert all(sha(base/'headers'/k)==v for k,v in m['headers_sha256'].items());shutil.copytree(base/'headers',root/'headers');shutil.copy2(pathlib.Path(__file__).resolve().parents[1]/'gpu/point_prep_candidate.cuh',root/'headers/point_prep_candidate.cuh');s=(base/'source.cu').read_text();anchor='template <int CD>\n__global__ void MFDiagHcc';assert s.count(anchor)==1;s=s.replace(anchor,'#include "point_prep_candidate.cuh"\n'+anchor)
anchor='    if(rhs_diag_camera){';assert s.count(anchor)==1;s=s.replace(anchor,'''    const bool prep_fused = CD==9 && use_equil && !e_dead && !rhs_diag_camera;
    if(prep_fused){
      CUDA_CHECK(cudaMemset(corr,0,(size_t)n_cf*sizeof(Scalar)));
      CUDA_CHECK(cudaMemset(dk,0,(size_t)n_cf*sizeof(Scalar)));
      MFRhsDiagFused<<<GridSize(nobs),256>>>(mf_fp32?Gp32:Gp,fragment_cams,fragment_points,Rf,uu,nobs,corr,dk);
    } else if(rhs_diag_camera){''')
anchor='      if(!rhs_diag_camera){';assert s.count(anchor)==1;s=s.replace(anchor,'      if(!rhs_diag_camera && !prep_fused){')
if a.cholesky:
 old='else        MFPointFactorObs<Fragment><<<GridSize(npt),256>>>(Bo,p.point_obs_offsets,p.point_obs_list,npt,R0f);';assert s.count(old)==1;s=s.replace(old,'else MFPointFactorGuarded<<<GridSize(npt),256>>>(Bo,p.point_obs_offsets,p.point_obs_list,npt,R0f,nullptr);')
(root/'source.cu').write_text(s);cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(root/'headers'),str(root/'source.cu'),'-o',str(root/'prism-tr'),'-lcublas','-lcusolver']
with (root/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
(root/'stop-manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(root/'source.cu'),binary_sha256=sha(root/'prism-tr'),headers_sha256={p.name:sha(p) for p in (root/'headers').iterdir()},base_source_sha256=m['source_sha256'],policy='Factored guarded TR plus observation-owned FP64 fused RHS/diagonal; guarded Cholesky='+str(a.cholesky)),indent=2))
