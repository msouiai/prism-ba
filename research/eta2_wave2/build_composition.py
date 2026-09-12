from pathlib import Path
import hashlib,importlib.util,json,os,subprocess
P=Path(__file__).resolve().parent;C=P.parent/'eta2_research_20260912';F=P.parent/'eta2_champion';T=P.parent/'eta2_track_damping'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('w1_base',P/'build.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);s,count=m.derive()
def patch(a,b):
 global s
 assert s.count(a)==1,(a[:100],s.count(a));s=s.replace(a,b)
patch('#include "wave_trace.cuh"','#include "wave_trace.cuh"\n#include "composition_capture.cuh"\n#include "track_factor.cuh"')
anchor='    Diagnostics diag_init = ComputeDiagnostics(p, s);'
patch(anchor,'    if(const char* file=getenv("OCA_W1_STATE"))W1LoadState(file,s,ncam,npt,nobs);\n'+anchor)
anchor='  double attr_R=0,attr_old_R=0,attr_norm=0,attr_next_lambda=0,attr_raw_norm=0;'
patch(anchor,anchor+'\n  if(const char* r=getenv("OCA_W1_RADIUS"))attr_R=atof(r);')
anchor='      else\n        MFPointFactorTau<<<GridSize(npt),256>>>(Cdiag,R0f,tau_eff,npt,Rf,okf);'
patch(anchor,'''      else if(getenv("OCA_W1_STATIC_REPLAY"))
        MFPointFactorTauTrack<<<GridSize(npt),256>>>(Cdiag,R0f,p.point_obs_offsets,tau_eff,npt,Rf,okf);
'''+anchor)
anchor='    if(wave_trace)wave_trace->Observe(wave.row,s,E,xs[0],ncam);'
patch(anchor,anchor+'''
    if(const char* root=getenv("OCA_W1_DIR")){
      if(!wave_trace)throw std::runtime_error("W1 collector requires wave trace");
      std::string q=std::string(root)+"/"+std::to_string(wave_trace->rows.size());std::filesystem::create_directories(q);
      W1Save(q,"R_state.f64",s.R,9ul*ncam);W1Save(q,"t_state.f64",s.t,3ul*ncam);
      W1Save(q,"X_state.f64",s.X,3ul*npt);W1Save(q,"intr_state.f64",s.intr,3ul*ncam);
      W1Save(q,"E.f64",E,n_c);W1Save(q,"Cdiag.f64",Cdiag,n_p);W1Save(q,"eta2_raw_scaled.f64",xs[0],n_c);
      std::ofstream f(q+"/metadata.txt");f<<std::setprecision(17)<<"ncam="<<ncam<<"\\nnpt="<<npt<<"\\nnobs="<<nobs
       <<"\\ncost="<<cost<<"\\nouter="<<k<<"\\nlambda="<<lam_cam<<"\\ntau="<<tau_eff<<"\\nradius="<<attr_R
       <<"\\neta="<<eta<<"\\neta2_cg="<<(cg_broke?cg_it+1:maxck)<<"\\nstatic_replay="<<(getenv("OCA_W1_STATIC_REPLAY")?1:0)<<"\\n";f.close();if(!f)throw std::runtime_error("W1 metadata write failed");
      if(getenv("OCA_W1_STOP"))break;
    }
''')
b=P/'build';src=b/'prism_composition.cu';src.write_text(s)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),'-I'+str(T),'-I'+str(C/'frontload'),'-I'+str(F/'source/headers'),str(src),'-o',str(b/'prism-composition'),'-lcublas','-lcusolver']
env=os.environ.copy();env['TMPDIR']='/dev/shm'
with (b/'composition-build.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
record=dict(command=cmd,source_sha256=sha(src),binary_sha256=sha(b/'prism-composition'),protocol_sha256=sha(P/'COMPOSITION_COMPLETION_PROTOCOL.md'),
 sources={str(p):sha(p) for p in [P/'build_composition.py',P/'composition_capture.cuh',T/'track_factor.cuh',P/'build.py',P/'wave_trace.cuh']})
(P/'composition_manifest.json').write_text(json.dumps(record,indent=2)+'\n');print('BUILT COMPOSITION',flush=True)
