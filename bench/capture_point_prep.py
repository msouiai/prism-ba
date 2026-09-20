import pathlib,json,os,subprocess,time
from build_tr_candidate import sha
from cached_benchmark_input import load_input
from audit_prism_state import audit
root=pathlib.Path('/workspace/prism-tr-point-prep/capture-v2');root.mkdir();m=json.loads(pathlib.Path('/workspace/prism-tr-safeguard/recommended_candidate.json').read_text());env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};env.update(m['flags'],PRISM_PREP_CAPTURE=str(root));env.pop('OCA_TARGET_COST');env['OCA_MAX_SECONDS']='60';binary='/workspace/prism-tr-point-prep/capture-build-v2/prism-tr';cmd=['flock','/tmp/prism_gpu.lock','timeout','240',binary,'--problem','/workspace/bal/final-13682.txt','--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','1','--state_out',str(root/'endpoint.state')]
(root/'manifest.json').write_text(json.dumps(dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith(('OCA_','PRISM_PREP'))},binary_sha256=sha(binary)),indent=2))
with (root/'run.log').open('w') as f,(root/'run.stderr').open('w') as e:subprocess.run(cmd,env=env,stdout=f,stderr=e,check=True)
dh,(dims,obs),initial=load_input(pathlib.Path('/workspace/bal/final-13682.txt'),'/workspace/prism-caspar-expanded/cpu-cache');cost=audit(root/'endpoint.state',dims,obs);(root/'result.json').write_text(json.dumps(dict(cost=cost,input_sha256=dh,files={p.name:sha(p) for p in root.iterdir() if p.is_file()}),indent=2));print(cost)
