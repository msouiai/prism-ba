import subprocess,json,statistics,pathlib,sys
P=pathlib.Path(__file__).resolve().parent
with (P/'memcheck.txt').open('w') as f:
    subprocess.run(['flock','/tmp/prism_gpu.lock','compute-sanitizer','--tool','memcheck','--error-exitcode','9',str(P/'build/check-sweep'),str(P/'evidence/fixed/spd-63.bin'),str(P/'build/memcheck-output.bin')],stdout=f,stderr=subprocess.STDOUT,check=True)
subprocess.run([sys.executable,str(P/'run_study.py'),'parity'],check=True)
r=json.loads((P/'parity.json').read_text());out=[]
for s in sorted({x['scene'] for x in r}):
    a=[x for x in r if x['scene']==s and x['stage']=='original-parity'];b=[x for x in r if x['scene']==s and x['stage']=='new-parity']
    delta=statistics.median(x['final_cost'] for x in b)/statistics.median(x['final_cost'] for x in a)-1
    counts=all(statistics.median(x[k] for x in a)==statistics.median(x[k] for x in b) for k in ['accepted','rejects','matvecs'])
    out.append(dict(scene=s,relative_median_cost=delta,median_counts_equal=counts))
assert all(abs(x['relative_median_cost'])<1e-4 and x['median_counts_equal'] for x in out),out
(P/'off_validation.json').write_text(json.dumps(out,indent=2)+'\n')
subprocess.run([sys.executable,str(P/'run_study.py'),'small'],check=True)
