#!/usr/bin/env python3
"""Four preselected repair states, three arms, two three-step continuations."""
import csv,json,os,pathlib,re,shutil,struct,subprocess,time
from profile_iterations import COMMON,sha
from novelty_ablation import EXEC
from cached_benchmark_input import load_input
from audit_prism_state import audit
from expanded_caspar_screen import write

ROOT=pathlib.Path('/workspace/prism-repair-rollout')
DATA=pathlib.Path('/workspace/bal/dubrovnik-88.txt')
BINARY=ROOT/'prism-rollout'

def main():
    base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
    flags=dict(COMMON,**EXEC,OCA_NSHIFTS='1',OCA_MENU_BACKTRACK='8',OCA_BACKTRACK_REARM='1',
               OCA_COMPACT_FRAGMENTS='2',OCA_POINT_SAFEGUARD='1',OCA_DEMAND_MENU='0',OCA_SWITCH_RESTART='0',OCA_MAX_SECONDS='4')
    dh,(dims,obs),initial=load_input(DATA,'/workspace/prism-caspar-expanded/cpu-cache')
    jobs=[]
    for rep in [1,2]:
        for i,outer in enumerate([15,16,17,18] if rep==1 else [18,17,16,15]):
            arms=['single','five','five-probe'];offset=(i+rep-1)%3
            if rep==2:arms.reverse()
            for arm in arms[offset:]+arms[:offset]:jobs.append(dict(outer=outer,arm=arm,rep=rep,name=f'o{outer}-{arm}-{rep}'))
    source=pathlib.Path(__file__).resolve().parent
    protocol=dict(data_sha256=dh,binary_sha256=sha(BINARY),source_sha256=sha(ROOT/'source-rollout.cu'),
        source_before_sha256=sha(ROOT/'source-before.cu'),flags=flags,capture_outers=[15,16,17,18],jobs=jobs,
        horizon=3,native_cap=4,process_timeout=45,
        probe='Only first replayed outer, repair the already accepted five-shift winner; retain ordinary step unless full-cost improvement passes Armijo. Later steps use unchanged five-shift policy.',
        timing='No profiler or candidate log. Report complete native return including checkpoint load/setup and every probe; captures charged separately.',
        tooling_sha256={f:sha(source/f) for f in ['build_repair_rollout.py','repair_rollout_study.py','audit_prism_state.py','cached_benchmark_input.py','profile_iterations.py','novelty_ablation.py']})
    pp=ROOT/'protocol.json'
    if pp.exists():assert json.loads(pp.read_text())==protocol
    else:
        write(pp,protocol);(ROOT/'tooling').mkdir(exist_ok=True)
        for f in protocol['tooling_sha256']:shutil.copy2(source/f,ROOT/'tooling'/f)
        headers={}
        for p in (source.parent/'gpu').iterdir():
            if p.suffix in ['.h','.cuh']:headers[p.name]=sha(p);shutil.copy2(p,ROOT/'tooling'/p.name)
        write(ROOT/'headers.json',headers)
    def run(name,outer,arm,rep,capture=False):
        stem=ROOT/name;rp=stem.with_suffix('.result.json');checkpoint=ROOT/f'o{outer}.checkpoint'
        if rp.exists():return json.loads(rp.read_text())
        env=dict(base,**flags);env.update(OCA_REPLAY_STEPS='3')
        env['OCA_NSHIFTS']='1' if arm=='single' else '5'
        if capture:env.update(OCA_REPLAY_SAVE=str(checkpoint),OCA_REPLAY_AT=str(outer))
        else:env['OCA_REPLAY_LOAD']=str(checkpoint)
        if arm=='five-probe':env['OCA_REPLAY_REPAIR_PROBE']='1'
        cmd=['flock','/tmp/prism_gpu.lock','timeout','45',str(BINARY),'--problem',str(DATA),'--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','30','--csv',str(stem.with_suffix('.csv')),'--state_out',str(stem.with_suffix('.state'))]
        assert sha(BINARY)==protocol['binary_sha256']
        manifest=dict(name=name,outer=outer,arm=arm,rep=rep,capture=capture,command=cmd,
            flags={k:v for k,v in env.items() if k.startswith('OCA_')},binary_sha256=sha(BINARY),data_sha256=dh)
        if not capture:manifest['checkpoint_sha256']=sha(checkpoint)
        if stem.with_suffix('.log').exists():
            assert json.loads(stem.with_suffix('.manifest.json').read_text())==manifest
            assert 'RESULT algo=' in stem.with_suffix('.log').read_text(), 'Incomplete executable run; inspect'
            wall=None  # Completed run retained after parser assertion; never rerun it.
        else:
            write(stem.with_suffix('.manifest.json'),manifest)
            print('RUN',name,flush=True);start=time.monotonic()
            with stem.with_suffix('.log').open('x') as f,stem.with_suffix('.stderr').open('x') as e:q=subprocess.run(cmd,env=env,stdout=f,stderr=e)
            wall=time.monotonic()-start
            write(stem.with_suffix('.process.json'),dict(returncode=q.returncode,wall=wall))
            assert q.returncode==0,(name,q.returncode)
        log=stem.with_suffix('.log').read_text()
        m=re.search(r'RESULT .*?final_cost=(\S+) solve_seconds=(\S+)',log);assert m
        replay=re.search(r'REPLAY (?:save|load) (.*)',log);assert replay
        header={k:float(v) for k,v in re.findall(r'(\w+)=([\d.e+-]+)',replay[1])}
        assert header['outer']==outer
        state=ROOT/f'o{outer}.initial.state'
        if capture:
            # Replay's final bytes are exactly R,t,X,intr, in PRISMS01 order.
            count=(15*dims[0]+3*dims[1])*8
            payload=checkpoint.read_bytes()[-count:]
            state.write_bytes(b'PRISMS01'+struct.pack('<QQQ',*dims)+payload)
        cpu_initial=audit(state,dims,obs);assert abs(cpu_initial-header['cost'])/cpu_initial<1e-10
        cost=audit(stem.with_suffix('.state'),dims,obs);error=abs(cost-float(m[1]))/cost;assert error<1e-7
        with stem.with_suffix('.csv').open() as f:trace=list(csv.DictReader(l for l in f if not l.startswith('#')))
        assert abs(float(trace[0]['cost'])-(initial if capture else cpu_initial))/max(1,float(trace[0]['cost']))<1e-9
        steps=[r for r in trace if int(r['iter'])>outer];assert len(steps)==3,(name,len(steps))
        assert all(float(b['cost'])<=float(a['cost'])*(1+1e-10) for a,b in zip(trace,trace[1:]))
        assert abs(float(steps[-1]['cost'])-cost)/cost<1e-7
        counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+)',log);assert counts
        scoring=re.search(r'\[scoring\].*?total_scored=(\d+)',log);assert scoring
        probe=re.search(r'REPAIR_PROBE (.*)',log)
        pd={k:float(v) for k,v in re.findall(r'(\w+)=([\d.e+-]+)',probe[1])} if probe else None
        if pd:
            assert pd['o']==outer and pd['candidate']<=pd['ordinary']+1e-8*max(1,pd['ordinary'])
            if pd['won']:assert pd['candidate']<pd['ordinary'] and pd['slope']<0 and pd['candidate']<=pd['current']+1e-4*pd['slope']
        if arm=='five-probe' and pd is None:
            assert re.search(r'POINT_SAFE o='+str(outer)+r' ',log), 'Explain absent probe before accepting record'
        repair=re.search(r'POINT_SAFE o='+str(outer)+r' .*? won=(\d+)',log)
        row=dict(name=name,outer=outer,arm=arm,rep=rep,capture=capture,cost=cost,initial_cost=cpu_initial,
            seconds=float(m[2]),process_wall=wall,audit_error=error,checkpoint=header,checkpoint_sha256=sha(checkpoint),
            checkpoint_state_sha256=sha(state),first_cost=float(steps[0]['cost']),trace=steps,probe=pd,probe_eligible=pd is not None,
            first_existing_repair_won=bool(repair and repair[1]=='1'),
            accepts=int(counts[1])-header['accepts'],rejects=int(counts[2])-header['rejects'],
            matvecs=int(counts[3])-header['matvecs'],scored=int(scoring[1])-header['scored'])
        if capture:assert row['first_existing_repair_won'],'Preselected state did not reproduce repair win; retain and inspect'
        row['gain']=cpu_initial-cost;row['gain_per_native_second']=row['gain']/row['seconds']
        write(rp,row);print('DONE',name,'cost',cost,'gain',row['gain'],'s',row['seconds'],'probe',pd,flush=True)
        return row
    captures=[]
    for o in protocol['capture_outers']:
        captures.append(run(f'capture-o{o}',o,'single',0,True));write(ROOT/'captures.json',captures)
    rows=[]
    for j in jobs:
        rows.append(run(**j));write(ROOT/'results.json',rows)
    print('COMPLETE four captures + 24 three-step branches',flush=True)

if __name__=='__main__':main()
