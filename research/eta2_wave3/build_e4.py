from pathlib import Path
import hashlib,importlib.util,json,os,subprocess
P=Path(__file__).resolve().parent;W=P.parent/'eta2_wave2';C=P.parent/'eta2_research_20260912';F=P.parent/'eta2_champion'
spec=importlib.util.spec_from_file_location('e4_parent',P/'build.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
s,count=m.derive()
a='if(const char* root=getenv("OCA_E1_CAPTURE"))if(n_accept<3){'
b='if(const char* root=getenv("OCA_E4_CAPTURE")?getenv("OCA_E4_CAPTURE"):getenv("OCA_E1_CAPTURE"))if(n_accept<(getenv("OCA_E4_CAPTURE")?128:3)){'
assert s.count(a)==1;s=s.replace(a,b)
anchor='      DoRetract(d_best,s_new); CopyState(s,s_new,ncam,npt);'
replacement='''      if(const char* root=getenv("OCA_E4_CAPTURE"))if(n_accept<128){
        std::string q=std::string(root)+"/"+std::to_string(wave_trace->rows.size());
        W1Save(q,"accepted.step",d_best,n);
        std::ofstream f(q+"/accept.txt");f<<std::setprecision(17)<<"accept_index="<<n_accept<<"\\ncost_before="<<cost<<"\\ncost_after="<<best_cost<<"\\nrho="<<lm_rho<<"\\n";
        f.close();if(!f)throw std::runtime_error("E4 accepted capture failed");
      }
'''+anchor
assert s.count(anchor)==1;s=s.replace(anchor,replacement)
b=P/'build';src=b/'prism_e4.cu';src.write_text(s)
cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(P),'-I'+str(W),'-I'+str(C/'frontload'),'-I'+str(F/'source/headers'),str(src),'-o',str(b/'prism-e4'),'-lcublas','-lcusolver']
env=os.environ.copy();env['TMPDIR']='/dev/shm'
with (b/'e4-build.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
record=dict(command=cmd,source_sha256=sha(src),binary_sha256=sha(b/'prism-e4'),parent_manifest=json.loads((P/'build_manifest.json').read_text()),protocol_sha256=sha(P/'E4_PROTOCOL.md'),builder_sha256=sha(P/'build_e4.py'))
(P/'e4_build_manifest.json').write_text(json.dumps(record,indent=2)+'\n');print('BUILT E4',record['binary_sha256'])
