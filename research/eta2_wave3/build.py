"""Reversible local-actuator and opening-window overlay, frozen Eta2 unchanged."""
from pathlib import Path
import hashlib,importlib.util,json,os,subprocess
P=Path(__file__).resolve().parent;W=P.parent/'eta2_wave2';C=P.parent/'eta2_research_20260912';F=P.parent/'eta2_champion'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def derive():
 spec=importlib.util.spec_from_file_location('wave3_parent',W/'build.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 original,n=m.derive();s=original;patches=[]
 def patch(a,b,count=1):
  nonlocal s
  assert s.count(a)==count,(a[:100],s.count(a),count);s=s.replace(a,b);patches.append((a,b,count))
 patch('#include "wave_trace.cuh"','#include "wave_trace.cuh"\n#include "local_actuators.cuh"\n#include "composition_capture.cuh"')
 anchor='  bool wave_jumped=false;'
 patch(anchor,anchor+'''
  const double e3_eta=getenv("OCA_E3_ETA")?atof(getenv("OCA_E3_ETA")):.05;
  const int e3_window=getenv("OCA_E3_WINDOW")?atoi(getenv("OCA_E3_WINDOW")):3;
  const int e3_force_window=getenv("OCA_E3_FORCE_WINDOW")?atoi(getenv("OCA_E3_FORCE_WINDOW")):e3_window;
  const double e2_cap=getenv("OCA_E2_CAP")?atof(getenv("OCA_E2_CAP")):0;
  const bool e3_gate=getenv("OCA_E3_GATE")&&atoi(getenv("OCA_E3_GATE"));
  std::unique_ptr<E3Local> e3local;
  if(e2_cap>0||e3_gate)e3local=std::make_unique<E3Local>(ncam,e3_gate,e2_cap);
  if(e3_eta<=0||e3_eta>.5||e3_window<1||e3_window>3||e3_force_window<1||e3_force_window>e3_window)
    throw std::runtime_error("E3 opening configuration invalid");
''')
 patch('if(front || (wave_force && n_accept<3))eta=.05;',
       'if(front)eta=.05;else if(wave_force && n_accept<e3_force_window)eta=e3_eta;')
 patch('!(wave_unclip && n_accept<3)','!(wave_unclip && n_accept<e3_window)')
 anchor='    cached_tau=tau_eff; cached_floor=selected_floor; cached_pred_pt=pred_pt;'
 # Gate is evaluated outside the factor-cache conditional at every attempt.
 anchor='    } // factor/RHS rebuild'
 patch(anchor,anchor+'''
    if(e3_gate){
      CUDA_CHECK(cudaMemset(e3local->B,0,81ul*ncam*sizeof(double)));
      if(mf_fp32)MFBlockSchurCM<CD,float><<<ncam,32>>>(Gc32,p.mf_cspt,p.mf_coff,Rf,nobs,e3local->B);
      else MFBlockSchurCM<CD,Fragment><<<ncam,32>>>(Gc?Gc:Gp,p.mf_cspt,p.mf_coff,Rf,nobs,e3local->B,fragment_slots);
      MFBlockAddHcc<CD><<<GridSize(ncam),256>>>(Hcc,ncam,e3local->B);
      e3local->SetGate(E,k,retries);e3local->Project(bprime);
    }
''')
 # Project the product output and every preconditioned residual. All starting
 # vectors and search updates stay in the constrained subspace thereafter.
 anchor='    auto KvS='
 # Exact source spelling checked during derivation, no regex mutation.
 if anchor not in s:anchor='    auto KvS ='
 pos=s.index(anchor);end=s.index('\n    };',pos)+len('\n    };')
 body=s[pos:end];assert body.count('auto KvS')==1
 renamed=body.replace('auto KvS','auto E3KvSBase',1)
 patch(body,renamed+'\n    auto KvS=[&](const Scalar* v,Scalar* out){E3KvSBase(v,out);if(e3_gate)e3local->Project(out);};')
 calls=['pcg->Apply(r_)']
 found=0
 for call in calls:
  ct=s.count(call+';')
  if ct:patch(call+';',call+';if(e3_gate)e3local->Project(pcg->z);',ct);found+=ct
 assert found>0
 anchor='        attr_old_R=attr_R;'
 patch(anchor,anchor+'\n        double e2_current_norm=attr_raw_norm;\n        if(e2_cap>0)e2_current_norm=e3local->Cap(xs[0],attr_R,k,retries);')
 patch('&& attr_raw_norm>attr_R){double scale=attr_R/attr_raw_norm;',
       '&& e2_current_norm>attr_R){double scale=attr_R/e2_current_norm;')
 anchor='    if(wave_trace)wave_trace->Observe(wave.row,s,E,xs[0],ncam);'
 patch(anchor,anchor+'''
    if(const char* root=getenv("OCA_E1_CAPTURE"))if(n_accept<3){
      if(!wave_trace)throw std::runtime_error("E1 capture requires trace");
      std::string q=std::string(root)+"/"+std::to_string(wave_trace->rows.size());std::filesystem::create_directories(q);
      W1Save(q,"R_state.f64",s.R,9ul*ncam);W1Save(q,"t_state.f64",s.t,3ul*ncam);
      W1Save(q,"X_state.f64",s.X,3ul*npt);W1Save(q,"intr_state.f64",s.intr,3ul*ncam);
      W1Save(q,"E.f64",E,n_c);W1Save(q,"Cdiag.f64",Cdiag,n_p);W1Save(q,"eta2_raw_scaled.f64",xs[0],n_c);
      std::ofstream f(q+"/metadata.txt");f<<std::setprecision(17)<<"ncam="<<ncam<<"\\nnpt="<<npt<<"\\nnobs="<<nobs
       <<"\\ncost="<<cost<<"\\nouter="<<k<<"\\nlambda="<<lam_cam<<"\\ntau="<<tau_eff<<"\\nradius="<<attr_R
       <<"\\neta="<<eta<<"\\neta2_cg="<<(cg_broke?cg_it+1:maxck)<<"\\nstatic_replay=0\\n";f.close();if(!f)throw std::runtime_error("E1 metadata write failed");
    }
''')
 restored=s
 for a,b,count in reversed(patches):assert restored.count(b)==count;restored=restored.replace(b,a)
 assert restored==original
 return s,n+len(patches)
def main():
 subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
 s,count=derive();b=P/'build';b.mkdir(exist_ok=True);src=b/'prism_wave3.cu';src.write_text(s)
 cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),'-I'+str(W),'-I'+str(C/'frontload'),'-I'+str(F/'source/headers'),str(src),'-o',str(b/'prism-wave3'),'-lcublas','-lcusolver']
 env=os.environ.copy();env['TMPDIR']='/dev/shm'
 with (b/'build.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 record=dict(command=cmd,source_sha256=sha(src),binary_sha256=sha(b/'prism-wave3'),frozen_source_sha256=sha(F/'source/prism_eta2.cu'),champion_sha256=sha(F/'champion.json'),reversible_patch_count=count,
  sources={str(p):sha(p) for p in [P/'build.py',P/'local_actuators.cuh',W/'build.py',W/'wave_trace.cuh',W/'composition_capture.cuh',C/'frontload/build.py',C/'frontload/frontload.cuh',C/'frontload/coherent_rows.cuh',C/'frontload/attempt_trace.h']})
 (P/'build_manifest.json').write_text(json.dumps(record,indent=2)+'\n');print('BUILT',record['binary_sha256'],flush=True)
if __name__=='__main__':main()
