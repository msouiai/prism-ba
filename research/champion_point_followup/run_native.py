#!/usr/bin/env python3
import os,pathlib,json,subprocess,re,time,hashlib,statistics,fcntl,argparse,math
P=pathlib.Path(__file__).resolve().parent
CONF=json.loads((P.parent/'eta2_champion/champion.json').read_text())
ORIGINAL=pathlib.Path('/tmp/prism-rl-actor/build/prism-tr')
BINARY=P/'build/prism-followup'
ARMS={'champion':{},'polish':{'OCA_FOLLOW_POINT':'1'},'selective':{'OCA_FOLLOW_POINT':'2'},'virtual':{'OCA_FOLLOW_POINT':'3'},'loose':{'OCA_FOLLOW_LOOSE':'1'},'polish_loose':{'OCA_FOLLOW_POINT':'1','OCA_FOLLOW_LOOSE':'1'},'selective_loose':{'OCA_FOLLOW_POINT':'2','OCA_FOLLOW_LOOSE':'1'},'virtual_loose':{'OCA_FOLLOW_POINT':'3','OCA_FOLLOW_LOOSE':'1'}}
SCENES=['ladybug-49','dubrovnik-88','venice-52']
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(scene,arm,rep,stage,target=None,cap=12.,binary=BINARY,maxiter=600):
    out=P/'evidence'/stage/f'{scene}-{arm}-{rep}';out.mkdir(parents=True,exist_ok=True)
    rp=out/'result.json'
    if rp.exists():return json.loads(rp.read_text())
    flags={**CONF['flags'],**ARMS[arm],'OCA_MAX_SECONDS':str(cap)}
    if target:flags['OCA_TARGET_COST']=str(target)
    env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))};env.update(flags)
    env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    problem=pathlib.Path('/workspace/bal')/(scene+'.txt')
    cli=CONF['cli'].copy();cli[cli.index('--max_iter')+1]=str(maxiter)
    cmd=[str(binary),'--problem',str(problem),*cli,'--csv',str(out/'curve.csv')]
    write(out/'manifest.json',dict(command=cmd,flags=flags,binary_sha256=sha(binary),problem_sha256=sha(problem),target=target,cap=cap))
    with open('/tmp/prism_gpu.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        with (out/'stdout.log').open('w') as f:
            start=time.perf_counter();p=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=cap+60);wall=time.perf_counter()-start
    text=(out/'stdout.log').read_text();assert p.returncode==0,(out,p.returncode,text[-1000:])
    m=re.search(r'RESULT algo=\S+ iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)',text);assert m,out
    hit=re.search(r'TARGET reached outer=(\d+) seconds=(\S+) cost=(\S+)',text)
    ac=re.findall(r'CLASSICAL_LM o=(\d+).*?accept=(\d+)',text)
    extra=re.search(r'FOLLOW_POINT summary calls=(\d+) wins=(\d+) changed=(\d+) seconds=(\S+)',text)
    row=dict(scene=scene,arm=arm,rep=rep,stage=stage,target=target,hit=bool(hit),target_seconds=float(hit[2]) if hit else None,final_cost=float(m[2]),native_seconds=float(m[3]),process_seconds=wall,outers=int(m[1]),accepted=sum(int(v) for _,v in ac),rejects=sum(1-int(v) for _,v in ac),cap_hit='BUDGET stop=' in text,source=str(out.relative_to(P)))
    total=re.search(r'MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',text)
    if total:row.update(accepted=int(total[1]),rejects=int(total[2]),matvecs=int(total[3]))
    diagnostics=re.search(r'DIAGNOSTICS median_reproj_err_px (\S+) -> (\S+) \| cheirality_violations\(obs\) (\d+) -> (\d+)',text)
    if diagnostics:row.update(median_reproj_px=float(diagnostics[2]),cheirality_obs=int(diagnostics[4]))
    if extra:row.update(overlay_calls=int(extra[1]),overlay_selected=int(extra[2]),points_changed=int(extra[3]),overlay_seconds=float(extra[4]))
    # Full accepted-state objective, not candidate costs, must never increase.
    curve=[float(line.split(',')[1]) for line in (out/'curve.csv').read_text().splitlines()[2:] if line]
    assert all(math.isfinite(c) for c in curve) and all(b<=a+1e-8*max(1,abs(a)) for a,b in zip(curve,curve[1:])),out
    write(rp,row);print(json.dumps(row),flush=True);return row

def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['calibrate','screen','extend-calibrate','extend','repeat']);ap.add_argument('--arms',nargs='+');args=ap.parse_args()
    if args.stage in ['calibrate','extend-calibrate']:
        assert sha(ORIGINAL)==CONF['binary_sha256']
        scenes=SCENES if args.stage=='calibrate' else ['ladybug-598','muell-gba146'];cap=12 if args.stage=='calibrate' else 25
        # All reference runs complete and target file freezes before any candidates.
        rows=[run(s,'champion',rep,args.stage,cap=cap,binary=ORIGINAL) for s in scenes for rep in range(3)]
        targets={s:1.001*statistics.median(r['final_cost'] for r in rows if r['scene']==s) for s in scenes}
        write(P/(args.stage+'-targets.json'),dict(targets=targets,rows=rows,protocol_sha256=sha(P/'PROTOCOL.md')))
    else:
        ext=args.stage=='extend';ts=json.loads((P/('extend-calibrate-targets.json' if ext else 'calibrate-targets.json')).read_text())['targets'];cap=25 if ext else 12
        arms=args.arms or list(ARMS);rows=[]
        reps=range(3,10) if args.stage=='repeat' else range(3)
        for s,target in ts.items():
            for rep in reps:
                offset=rep%len(arms)
                for a in arms[offset:]+arms[:offset]:rows.append(run(s,a,rep,args.stage,target,cap))
        write(P/(args.stage+'-results.json'),rows)
if __name__=='__main__':main()
