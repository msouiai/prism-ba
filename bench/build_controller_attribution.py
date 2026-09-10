"""Matched rescue, point damping, and terminal-direction radius controls."""
import pathlib,json,shutil,subprocess
from build_tr_candidate import sha
base=pathlib.Path('/workspace/prism-lm-point-rescue/build')
root=pathlib.Path('/tmp/prism-controller-attribution/build');root.mkdir(parents=True)
m=json.loads((base/'manifest.json').read_text())
assert sha(base/'source.cu')==m['source_sha256']
assert all(sha(base/'headers'/k)==v for k,v in m['headers_sha256'].items())
shutil.copytree(base/'headers',root/'headers');s=(base/'source.cu').read_text()
def sub(a,b):
 global s
 assert s.count(a)==1,(a,s.count(a));s=s.replace(a,b)
sub('  double lm_nu=2,lm_rho=0,lm_prediction=0;', '''  double lm_nu=2,lm_rho=0,lm_prediction=0;
  const bool attr_rescue=getenv("OCA_ATTR_RESCUE")!=nullptr;
  const bool attr_split=getenv("OCA_ATTR_SPLIT")!=nullptr;
  const bool attr_radius=getenv("OCA_ATTR_RADIUS")!=nullptr;
  const bool attr_strict=getenv("OCA_ATTR_STRICT")!=nullptr;
  if((attr_rescue||attr_split||attr_radius||attr_strict)&&!classical_lm)throw std::runtime_error("attribution switches require LM engine");
  if(attr_radius&&!attr_strict)throw std::runtime_error("radius controls require matched rho .1 threshold");
  double attr_R=0,attr_old_R=0,attr_norm=0,attr_next_lambda=0,attr_raw_norm=0;
''')
sub('camera_tr || point_safeguard_mode || backtrack_on || tr_fast_model', 'camera_tr || (!attr_rescue&&(point_safeguard_mode || backtrack_on)) || tr_fast_model')
sub('  const int recycle_mode=getenv(', '''  if(attr_rescue&&(!backtrack_on||point_safeguard_mode!=1||lm_point_rescue))throw std::runtime_error("matched rescue requires original backtracking and zero/full safeguard, without separate LM rescue");
  const int recycle_mode=getenv(''')
sub('    if(classical_lm)tau_eff=lam_cam;', '    if(classical_lm&&!attr_split)tau_eff=lam_cam;')
sub('    if(classical_lm){Score(xs[0],0,cg_broke?cg_it+1:maxck);}', '''    if(classical_lm){
      if(attr_radius){
        cublasDnrm2(blas,n_c,xs[0],1,&attr_raw_norm);
        if(!(attr_R>0))attr_R=std::isfinite(attr_raw_norm)&&attr_raw_norm>0?attr_raw_norm:1;
        attr_old_R=attr_R;
        if(attr_raw_norm>attr_R){double scale=attr_R/attr_raw_norm;cublasDscal(blas,n_c,&scale,xs[0],1);}
      }
      Score(xs[0],0,cg_broke?cg_it+1:maxck);
    }''')
sub('      have=have&&std::isfinite(lm_rho)&&lm_prediction>0&&lm_rho>0;', '''      have=have&&std::isfinite(lm_rho)&&lm_prediction>0&&lm_rho>(attr_strict?.1:0);
      if(attr_radius){
        MFTRUnscale<<<GridSize(n_c),256>>>(have?d_best:dfull,E,xc_un,n_c);
        cublasDnrm2(blas,n_c,xc_un,1,&attr_norm);
        have=have&&attr_norm<=attr_old_R*(1+1e-8);
        attr_R=prism_camera_tr::radius_after(attr_old_R,attr_norm,lm_rho);
        if(!have&&attr_R>=attr_old_R)attr_R=std::max(1e-14,.25*attr_old_R);
        attr_next_lambda=(double)lam_cam*std::pow(attr_old_R/attr_R,2.);
        if(have&&attr_norm<.8*attr_old_R&&lm_rho>=.25)attr_next_lambda=std::min(attr_next_lambda,.1*(double)lam_cam);
        attr_next_lambda=std::clamp(attr_next_lambda,1e-16,1e16);
        std::printf("ATTR_RADIUS o=%d raw_norm=%.17g norm=%.17g radius=%.17g next_radius=%.17g lambda=%.17g next_lambda=%.17g rho=%.17g accept=%d\\n",k,attr_raw_norm,attr_norm,attr_old_R,attr_R,(double)lam_cam,attr_next_lambda,lm_rho,(int)have);
      }''')
sub('        double f=std::max(1./3.,1.-std::pow(2*lm_rho-1.,3.));lam_cam=std::clamp((double)lam_cam*f,1e-16,1e16);lm_nu=2;', '        double f=std::max(1./3.,1.-std::pow(2*lm_rho-1.,3.));lam_cam=attr_radius?attr_next_lambda:std::clamp((double)lam_cam*f,1e-16,1e16);lm_nu=2;')
sub('if(classical_lm){lam_cam=std::min(1e16,(double)lam_cam*lm_nu);lm_nu=std::min(1e8,lm_nu*2);}', 'if(classical_lm){lam_cam=attr_radius?attr_next_lambda:std::min(1e16,(double)lam_cam*lm_nu);lm_nu=std::min(1e8,lm_nu*2);}')
(root/'source.cu').write_text(s)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(root/'headers'),str(root/'source.cu'),'-o',str(root/'prism-tr'),'-lcublas','-lcusolver']
with (root/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
(root/'manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(root/'source.cu'),binary_sha256=sha(root/'prism-tr'),headers_sha256={p.name:sha(p) for p in (root/'headers').iterdir()},parent=m,scope='Matched original rescue; optional legacy ratcheted point-damping policy; optional terminal-direction Euclidean radius clipping in identical Hcc coordinates, rho>.1 and radius-to-lambda updates. No new Krylov bank or metric.'),indent=2))
