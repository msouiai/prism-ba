#!/usr/bin/env python3
"""Interleaved Prism A/B timing and quality gate (no external baseline claims)."""
import argparse, csv, hashlib, json, os, pathlib, re, statistics, subprocess, time

COMMON = dict(OCA_FORCE_UNSHARED='1', OCA_RHO_LAMBDA='1', OCA_GRID_DOWN='2',
              OCA_RHO_SHIFT='1', OCA_ALPHA_RHO='1', OCA_MENU_GATE='1e-2',
              OCA_FTOL='1e-5', OCA_FTOL_K='8', OCA_TAU_LAM='1', OCA_TAU_LAM_RATCHET='1')
ARMS = {'reference': {}, 'optimized': {'OCA_RETRY_CACHE':'1','OCA_MULTI_RHS':'1'}}

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1<<20),b''): h.update(block)
    return h.hexdigest()

def score_initial(path):
    """Independent fp64 Rodrigues + SIMPLE_RADIAL evaluation, including all depths."""
    import numpy as np
    with open(path) as f:
        nc,np_,no=map(int,f.readline().split())
        obs=np.loadtxt(f,max_rows=no)
        values=np.loadtxt(f)
    cams=values[:9*nc].reshape(nc,9); pts=values[9*nc:].reshape(np_,3)
    aa=cams[:,:3]; theta=np.linalg.norm(aa,axis=1)
    axis=np.divide(aa,theta[:,None],out=np.zeros_like(aa),where=theta[:,None]!=0)
    R=np.zeros((nc,3,3)); ct=np.cos(theta); st=np.sin(theta)
    for i in range(3):
        for j in range(3): R[:,i,j]=(1-ct)*axis[:,i]*axis[:,j]+(ct if i==j else 0)
    R[:,0,1]-=st*axis[:,2]; R[:,1,0]+=st*axis[:,2]
    R[:,0,2]+=st*axis[:,1]; R[:,2,0]-=st*axis[:,1]
    R[:,1,2]-=st*axis[:,0]; R[:,2,1]+=st*axis[:,0]
    total=0.
    for start in range(0,no,100000):
        o=obs[start:start+100000]; ci=o[:,0].astype(int); pi=o[:,1].astype(int)
        q=np.einsum('nij,nj->ni',R[ci],pts[pi])+cams[ci,3:6]
        xy=-q[:,:2]/q[:,2,None]; r2=np.sum(xy*xy,axis=1)
        residual=xy*(cams[ci,6]*(1+cams[ci,7]*r2))[:,None]-o[:,2:4]
        total+=float(np.sum(residual*residual,dtype=np.float64)*.5)
    return total

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--reference',required=True); ap.add_argument('--optimized',required=True)
    ap.add_argument('--data',type=pathlib.Path,required=True); ap.add_argument('--out',type=pathlib.Path,required=True)
    ap.add_argument('--scenes',nargs='+',required=True); ap.add_argument('--reps',type=int,default=3)
    ap.add_argument('--max-iter',type=int,default=600); ap.add_argument('--config',choices=['A','B'],default='A')
    ap.add_argument('--optimized-env',action='append',default=[],metavar='OCA_FLAG=VALUE')
    ap.add_argument('--reference-env',action='append',default=[],metavar='OCA_FLAG=VALUE')
    ap.add_argument('--recover-completed',action='store_true',help='parse retained completed logs after a harness failure instead of rerunning them')
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    for arm in ARMS:
        for entry in getattr(args,arm+'_env'):
            key,sep,value=entry.partition('=')
            if not sep or not key.startswith('OCA_'): ap.error('arm environment requires OCA_FLAG=VALUE')
            ARMS[arm][key]=value
    binaries={a:str(pathlib.Path(getattr(args,a)).resolve()) for a in ARMS}
    for arm,path in binaries.items():
        binary=pathlib.Path(path).read_bytes()
        required=set(COMMON)|set(ARMS[arm])
        if args.config=='B':required.update(['OCA_TAU_LAM_COND','OCA_RETRY_SPAN'])
        missing=[flag for flag in sorted(required) if flag.encode()+b'\0' not in binary]
        if missing:raise RuntimeError(f'{arm} binary lacks flag strings: {missing}')
    provenance={'binaries':{a:{'path':p,'sha256':sha(p)} for a,p in binaries.items()},
                'common':COMMON,'arms':ARMS,'config':args.config,'max_iter':args.max_iter,'reps':args.reps,
                'scenes':args.scenes,'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version','--format=csv,noheader'],text=True)}
    manifest=args.out/'preregistered.json'
    if manifest.exists():
        registered=json.loads(manifest.read_text())
        if any(registered.get(k)!=v for k,v in provenance.items()): raise RuntimeError('Existing experiment differs; use a new output directory')
    else: manifest.write_text(json.dumps(provenance,indent=2)+'\n')
    rows=[]
    for scene in args.scenes:
        path=args.data/(scene+'.txt'); initial=score_initial(path); data_sha=sha(path)
        for rep in range(args.reps):
            for arm in (list(ARMS) if rep%2==0 else list(reversed(ARMS))):
                stem=args.out/f'{scene}-{arm}-{rep+1}'; result=stem.with_suffix('.json')
                if result.exists():
                    saved=json.loads(result.read_text())
                    if saved['data_sha256']!=data_sha:raise RuntimeError('Input changed since saved run')
                    if abs(saved['score_init']-initial)>1e-6*max(1,abs(initial)):raise RuntimeError('Saved initial objective mismatch')
                    rows.append(saved);continue
                env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','COLMAP_MFREE','MF_DEBUG'))}
                env.update(COMMON);env.update(ARMS[arm])
                if args.config=='B':env.update(OCA_TAU_LAM_COND='0.2',OCA_RETRY_SPAN='3')
                command=['flock','/tmp/prism_gpu.lock',binaries[arm],'--problem',str(path),
                         '--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter',str(args.max_iter),
                         '--csv',str(stem.with_suffix('.csv'))]
                logpath=stem.with_suffix('.log')
                prior=logpath.read_text() if logpath.exists() else ''
                # Older logs merged buffered stdout and unbuffered stderr;
                # the CSV announcement can split even a summary field name.
                prior_clean=re.sub(r'\[R9\] wrote [^\r\n]*\r?\n','',prior)
                recover=args.recover_completed and 'RESULT algo=' in prior_clean and 'DIAGNOSTICS ' in prior_clean and stem.with_suffix('.csv').exists()
                print('RECOVER' if recover else 'RUN',scene,arm,rep+1,flush=True)
                if not recover:
                    with logpath.open('w') as f, stem.with_suffix('.stderr').open('w') as err:
                        subprocess.run(command,env=env,stdout=f,stderr=err,check=True)
                log=re.sub(r'\[R9\] wrote [^\r\n]*\r?\n','',logpath.read_text())
                m=re.search(r'RESULT .*?iters=(\d+) final_cost=([\d.e+-]+) solve_seconds=([\d.e+-]+)',log)
                with stem.with_suffix('.csv').open() as f:
                    trace=list(csv.DictReader(line for line in f if not line.startswith('#')))
                actual=float(trace[0]['cost']); rel=abs(actual-initial)/max(1,abs(initial))
                if rel>1e-6: raise RuntimeError(f'Initial objective mismatch: {rel}')
                counts=re.search(r'accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?cand_evals=(\d+)',log)
                row={'scene':scene,'arm':arm,'rep':rep+1,'iters':int(m[1]),'cost':float(m[2]),'seconds':float(m[3]),
                     'score_init':actual,'independent_score_init':initial,'score_init_relerr':rel,
                     'accepts':int(counts[1]),'rejects':int(counts[2]),'matvecs':int(counts[3]),'menu_evals':int(counts[4]),
                     'trace':trace,'data_sha256':data_sha}
                extra=re.search(r'\[menu-backtrack\] trials=(\d+) rescues=(\d+) evals=(\d+).*?total_scored=(\d+)',log)
                if recover:
                    row['recovered_completed_log']=True
                if extra:
                    row.update(backtrack_trials=int(extra[1]),backtrack_rescues=int(extra[2]),
                               backtrack_evals=int(extra[3]),total_scored=int(extra[4]))
                alpha=re.search(r'alpha_evals=(\d+)',log)
                if alpha:
                    row['alpha_evals']=int(alpha[1])
                    row['total_scored']=row['menu_evals']+row['alpha_evals']+row.get('backtrack_evals',0)
                result.write_text(json.dumps(row,indent=2)+'\n');rows.append(row)
                print('DONE',scene,arm,rep+1,row['cost'],row['seconds'],flush=True)
                (args.out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
    summary=[]
    for scene in args.scenes:
        group={a:[r for r in rows if r['scene']==scene and r['arm']==a] for a in ARMS}
        cell={'scene':scene}
        for a,rr in group.items():
            cell[a]={key:{'median':statistics.median(r[key] for r in rr),'min':min(r[key] for r in rr),'max':max(r[key] for r in rr)} for key in ['cost','seconds','rejects']}
        # Crossings in both directions against the other arm's median endpoint.
        for a,other in [('reference','optimized'),('optimized','reference')]:
            target=cell[other]['cost']['median']
            cell[a]['crossing_seconds']=[next((float(t['wall_s']) for t in r['trace'] if float(t['cost'])<=target),None) for r in group[a]]
        summary.append(cell)
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')

if __name__=='__main__': main()
