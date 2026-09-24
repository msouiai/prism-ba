import sys,pathlib,os,subprocess,re,json
sys.path.insert(0,'/workspace/prism-ba/bench')
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
from audit_prism_state import observations,audit
root=pathlib.Path('/workspace/prism-recycle-cg');out=root/'audit';out.mkdir(exist_ok=True)
base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};base.update(COMMON);base.update(EXEC);base.update(OCA_NSHIFTS='5',OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',OCA_COMPACT_FRAGMENTS='2',OCA_DEMAND_MENU='2',OCA_KRYLOV_REUSE='3')
rows=[]
for scene in ['ladybug-1197','dubrovnik-356']:
 stem=out/scene;env=dict(base,OCA_CAPTURE_AUDIT='1',OCA_MAX_SECONDS='15')
 cmd=['flock','/tmp/prism_gpu.lock','timeout','60',str(root/'prism-frozen'),'--problem','/workspace/bal/'+scene+'.txt','--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','100']
 stem.with_suffix('.manifest.json').write_text(json.dumps(dict(command=cmd,flags={k:v for k,v in env.items() if k.startswith('OCA_')},binary_sha256=sha(root/'prism-frozen')),indent=2)+'\n')
 with stem.with_suffix('.log').open('w') as f:r=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
 assert r.returncode==0
 log=stem.with_suffix('.log').read_text();records=[]
 for match in re.findall(r'CAPTURE_AUDIT rep=(\d+) reuse=(\d+) captured=(\d+) depth=(\d+) matvecs=(\d+) seconds=([\deE.+-]+) residual=([\deE.+-]+|inf) tolerance=([\deE.+-]+) valid=(\d+)',log):
  records.append(dict(scene=scene,**dict(zip(['rep','reuse','captured','depth','matvecs','seconds','residual','tolerance','valid'],map(float,match)))))
 assert len(records)==6
 rows+=records;print(scene,records,flush=True)
(root/'audit-summary.json').write_text(json.dumps(rows,indent=2)+'\n')
# Actual expansion/scoring memory check, separate from any timing runs.
scene='ladybug-49';stem=out/'expansion-sanitizer'
cmd=['flock','/tmp/prism_gpu.lock','timeout','90','compute-sanitizer','--tool','memcheck','--error-exitcode','99',str(root/'prism-frozen'),'--problem','/workspace/bal/'+scene+'.txt','--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','50','--state_out',str(stem.with_suffix('.state'))]
with stem.with_suffix('.log').open('w') as f:r=subprocess.run(cmd,env=base,stdout=f,stderr=subprocess.STDOUT)
assert r.returncode==0
log=stem.with_suffix('.log').read_text();assert 'ERROR SUMMARY: 0 errors' in log
m=re.search(r'RESULT .*?final_cost=([\d.e+-]+)',log);assert m
cost=audit(stem.with_suffix('.state'),*observations('/workspace/bal/'+scene+'.txt'));err=abs(cost-float(m[1]))/max(1,cost);assert err<1e-7
row=dict(cost=cost,audit_relerr=err,expansion_count=log.count('CAPTURE o='));assert row['expansion_count']>0
(root/'expansion-sanitizer.json').write_text(json.dumps(row,indent=2)+'\n');print(row,flush=True)
