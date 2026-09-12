"""Consistent Cauchy-to-L2 staging overlay; frozen source remains unchanged."""
from pathlib import Path
import hashlib, importlib.util, json, os, subprocess
P=Path(__file__).resolve().parent; W=P.parent/'eta2_wave3'; F=P.parent/'eta2_champion'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def derive():
    spec=importlib.util.spec_from_file_location('o5_parent',W/'build.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    original,n=m.derive();s=original;patches=[]
    def patch(a,b,count=1):
        nonlocal s
        assert s.count(a)==count,(a[:100],s.count(a),count)
        s=s.replace(a,b);patches.append((a,b,count))
    for name in ['full_step_model.cuh','point_safeguard.cuh']:
        patch('#include "'+name+'"','#include "'+str(P/'o5_headers'/name)+'"')
    patch('#include "'+str(P/'o5_headers/full_step_model.cuh')+'"',
          '#include "'+str(P/'o5_headers/robust_stage.cuh')+'"\n#include "'+str(P/'o5_headers/full_step_model.cuh')+'"')
    anchor='  Scalar rk_a2 = rk_scale2;'
    patch(anchor,r'''
  const bool w5_on=getenv("OCA_W5_CAUCHY")&&atoi(getenv("OCA_W5_CAUCHY"));
  if(w5_on&&(!classical_lm||!attr_radius||L!=1||rk!=0||func_tolerance!=0||shared_intr||CD!=9))
    throw std::runtime_error("O5 requires frozen single-shift unshared L2 entry path");
  if(w5_on)for(const char* key:{"OCA_RLD_ACTION","OCA_RLD_POLICY","OCA_RLD_OPENING","OCA_RLD_EPISODE","OCA_RLD_SAVE","OCA_RLD_LOAD","OCA_RLA_POLICY","OCA_RLC_CONTROLLER"})
    if(getenv(key))throw std::runtime_error("O5 permits the fixed forcing factor only; no learned/action/replay policy");
  int w5_stage=w5_on?0:4,w5_stage_accept=0,w5_attempts=0;
  bool w5_force_l2=false;
  double w5_base=0,w5_l2=0;
  Scalar rk_a2 = rk_scale2;
  if(w5_on){
    double* sq=nullptr;CUDA_CHECK(cudaMalloc(&sq,nobs*sizeof(double)));
    KernelResidSq<<<GridSize(nobs),256>>>(p.cam_idx,p.pt_idx,p.uv,s.R,s.t,s.X,
      INTR_F(p,s),INTR_K1(p,s),INTR_K2(p,s),nobs,sq);
    std::vector<double> h(nobs);CUDA_CHECK(cudaMemcpy(h.data(),sq,nobs*sizeof(double),cudaMemcpyDeviceToHost));cudaFree(sq);
    std::nth_element(h.begin(),h.begin()+h.size()/2,h.end());w5_base=std::max(4*h[h.size()/2],1e-12);
    rk=2;rk_a2=w5_base;W5SetRobust(rk,rk_a2);w5_l2=ComputeCost(p,s,0,0);
    std::printf("W5_INIT base=%.17g l2=%.17g\n",w5_base,w5_l2);
  }
''')
    patch('std::printf("  MFCG score_init=%.17g precision=fp64\\n",(double)cost);',
          'std::printf("  MFCG score_init=%.17g precision=fp64\\n",w5_on?w5_l2:(double)cost);')
    patch('RunLog log; log.iters.push_back(0); log.costs.push_back(cost);\n  // OCA_LAM_FLOOR',
          'RunLog log; log.iters.push_back(0); log.costs.push_back(w5_on?w5_l2:cost);\n  // OCA_LAM_FLOOR')
    patch('CsvOpen("mfree_shifted_cg", g_csv_problem.c_str()); CsvRow(0, (double)cost);',
          'CsvOpen("mfree_shifted_cg", g_csv_problem.c_str()); CsvRow(0, w5_on?w5_l2:(double)cost);')
    patch('  if(TargetReached(cost,replay_start)) max_iter=replay_start;',
          '  if(!rk&&TargetReached(cost,replay_start)) max_iter=replay_start;')
    patch('!attr_rescue || L!=1 || CD!=9 || shared_intr || mf_fp32 || rk || block_eq ||',
          '!attr_rescue || L!=1 || CD!=9 || shared_intr || mf_fp32 || (rk&&!w5_on) || block_eq ||')
    anchor='  for(int k=replay_start;k<max_iter;){'
    patch(anchor,anchor+r'''
   if(w5_on&&w5_stage<4){
     const bool capped=w5_attempts>=18;
     if(w5_force_l2||capped||n_accept-w5_stage_accept>=2){
       const int previous=w5_stage;
       w5_stage=(w5_force_l2||capped)?4:w5_stage+1;
       rk=w5_stage<4?2:0;rk_a2=w5_base*std::pow(4.,std::min(w5_stage,3));W5SetRobust(rk,rk_a2);
       cost=ComputeCost(p,s,rk,rk_a2);w5_l2=rk?ComputeCost(p,s,0,0):cost;
       std::printf("W5_STAGE o=%d previous=%d stage=%d accepts=%d attempts=%d capped=%d stop=%d a2=%.17g surrogate=%.17g l2=%.17g lambda=%.17g radius=%.17g\n",
         k,previous,w5_stage,n_accept,w5_attempts,(int)capped,(int)w5_force_l2,(double)rk_a2,(double)cost,w5_l2,(double)lam_cam,attr_R);
       prev_cost=cost;prev_bnorm=-1;ftol_streak=0;stuck=0;converged=false;backtrack_confirm=false;
       need_assembly=true;factor_cached=false;pf_obs_dirty=true;retries=0;
       w5_attempts=0;w5_stage_accept=n_accept;w5_force_l2=false;
       if(!rk){CsvRow(k,cost);if(TargetReached(cost,k))break;}
     }
     ++w5_attempts;
   }
''')
    patch('    retries=0; need_assembly=true;\n    log.iters.push_back(k+1); log.costs.push_back(cost);\n    CsvRow(k+1, (double)cost);',r'''
    retries=0; need_assembly=true;
    w5_l2=(w5_on&&rk)?ComputeCost(p,s,0,0):(double)cost;
    log.iters.push_back(k+1); log.costs.push_back(w5_l2);
    if(!rk)CsvRow(k+1, (double)cost);
    if(w5_on)std::printf("W5_L2 o=%d stage=%d accepts=%d surrogate=%.17g l2=%.17g rho=%.17g\n",k+1,w5_stage,n_accept,(double)cost,w5_l2,lm_rho);
''')
    patch('    if(TargetReached(cost,k+1)) break;', '    if(!rk&&TargetReached(cost,k+1)) break;')
    anchor='    if(converged && backtrack_on && !backtrack_confirm && backtrack_rescues>0){'
    patch(anchor,'''    if(w5_on&&rk&&converged){w5_force_l2=true;converged=false;}
'''+anchor)
    anchor='  int cheir1=CountCheiralityViolations(p,s);'
    patch(anchor,r'''
  if(w5_on){
    w5_l2=ComputeCost(p,s,0,0);cost=w5_l2;log.costs.back()=cost;
    std::printf("W5_FINAL stage=%d l2=%.17g incomplete=%d\n",w5_stage,w5_l2,(int)(w5_stage<4));
    W5SetRobust(0,0);
  }
'''+anchor)
    restored=s
    for a,b,count in reversed(patches):
        assert restored.count(b)==count;restored=restored.replace(b,a)
    assert restored==original
    return s,n+len(patches)

def headers():
    h=P/'o5_headers';h.mkdir(exist_ok=True)
    (h/'robust_stage.cuh').write_text('''#pragma once
__device__ int w5_device_rk=0;
__device__ double w5_device_a2=0;
inline void W5SetRobust(int rk,double a2){
 CUDA_CHECK(cudaMemcpyToSymbol(w5_device_rk,&rk,sizeof(rk)));
 CUDA_CHECK(cudaMemcpyToSymbol(w5_device_a2,&a2,sizeof(a2)));
}
''')
    for name in ['full_step_model.cuh','point_safeguard.cuh']:
        s=(F/'source/headers'/name).read_text()
        if name.startswith('full'):
            a='gd=rx*jx+ry*jy;jj=jx*jx+jy*jy;'
            b=a+'if(w5_device_rk){double w=OcaRobustW(w5_device_rk,w5_device_a2,rx*rx+ry*ry);gd*=w;jj*=w;}'
        else:
            a='double cost=.5*(a*a+b*b);return isfinite(cost)?cost:CUDART_INF;'
            b='double cost=.5*(a*a+b*b);if(w5_device_rk)cost=.5*OcaRho(w5_device_rk,w5_device_a2,a*a+b*b);return isfinite(cost)?cost:CUDART_INF;'
        assert s.count(a)==1;s=s.replace(a,b);(h/name).write_text(s)
    return list(h.glob('*.cuh'))

def main():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    hs=headers();s,n=derive();b=P/'build';b.mkdir(exist_ok=True);src=b/'o5.cu';src.write_text(s)
    parent=json.loads((W/'build_manifest.json').read_text());cmd=parent['command'].copy()
    cmd[cmd.index(str(W/'build/prism_wave3.cu'))]=str(src);cmd[cmd.index('-o')+1]=str(b/'prism-o5')
    with (b/'o5-build.log').open('w') as log:
        subprocess.run(cmd,env=dict(os.environ,TMPDIR='/dev/shm'),stdout=log,stderr=subprocess.STDOUT,check=True)
    r=dict(command=cmd,source_sha256=sha(src),binary_sha256=sha(b/'prism-o5'),
           frozen_source_sha256=sha(F/'source/prism_eta2.cu'),champion_sha256=sha(F/'champion.json'),reversible_patch_count=n,
           sources={**parent['sources'],**{str(p):sha(p) for p in [P/'build_o5.py',*hs]}},protocol_sha256=sha(P/'O5_PROTOCOL.md'))
    (P/'o5_build_manifest.json').write_text(json.dumps(r,indent=2)+'\n');print('BUILT O5',r['binary_sha256'],flush=True)
if __name__=='__main__':main()
