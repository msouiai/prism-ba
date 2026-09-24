#!/usr/bin/env python3
"""Calibrated initialization perturbations and paired frozen-solver evaluation."""
import argparse,datetime,hashlib,json,math,pathlib,re
import numpy as np
import rl_damping_pilot as p

ROOT=pathlib.Path('/tmp/prism-cg-value-noise')
REPO=pathlib.Path(__file__).parents[1]
DATA=pathlib.Path('/workspace/bal')
BIN=pathlib.Path('/tmp/prism-cg-value/build/prism-tr')
SHA='02ec2ea9e479e5752dde95fdf80799924c41488c564e67c454f0c46357fca8a7'
SCENES={'trafalgar-126':105579.58394455544,'dubrovnik-356':724127.912566*1.01,
        'venice-89':303286.305616*1.01}
SEEDS=[17,29,43]
ARMS={'champion':{'OCA_RLA_FIXED_ETA':2},'conservative':{'OCA_RLA_FIXED_ETA':2,'OCA_CGV':3}}
p.ROOT=ROOT;p.DATA=ROOT/'inputs';p.NATIVE_CAP=600
def read(n):return json.loads((ROOT/n).read_text())
def put(n,v):p.put(ROOT/n,v)
def rotation(v):
    theta=np.linalg.norm(v,axis=1)
    K=np.zeros((len(v),3,3));K[:,0,1]=-v[:,2];K[:,0,2]=v[:,1]
    K[:,1,0]=v[:,2];K[:,1,2]=-v[:,0];K[:,2,0]=-v[:,1];K[:,2,1]=v[:,0]
    a=np.sinc(theta/np.pi);b=.5*np.sinc(theta/(2*np.pi))**2
    return np.eye(3)[None]+a[:,None,None]*K+b[:,None,None]*(K@K)
def load(path):
    with path.open('rb') as f:
        header=f.readline();dims=tuple(map(int,header.split()))
        obsbytes=b''.join(f.readline() for _ in range(dims[2]));values=np.loadtxt(f)
    obs=np.fromstring(obsbytes.decode(),sep=' ').reshape(dims[2],4)
    nc,npt,no=dims;assert len(values)==9*nc+3*npt
    return dims,header,obsbytes,obs,values[:9*nc].reshape(nc,9),values[9*nc:].reshape(npt,3)
def project(c,x,obs):
    ci=obs[:,0].astype(np.int64);pi=obs[:,1].astype(np.int64)
    R=rotation(c[:,:3]);q=np.einsum('nij,nj->ni',R[ci],x[pi])+c[ci,3:6]
    with np.errstate(divide='ignore',invalid='ignore',over='ignore'):
        uv=-q[:,:2]/q[:,2,None];r2=np.sum(uv*uv,axis=1)
        uv*= (c[ci,6]*(1+c[ci,7]*r2))[:,None] # k2 fixed zero
        cost=float(.5*np.sum((uv-obs[:,2:4])**2,dtype=np.longdouble))
    return cost,uv,np.signbit(q[:,2])
def register():
    assert p.sha(BIN)==SHA
    record=dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),binary_sha256=SHA,
        code_sha256=p.sha(__file__),protocol_sha256=p.sha(REPO/'docs/cg_value_noise_protocol.md'),
        baseline_flags_sha256=p.sha(p.SELECTED),driver_sha256=p.sha(REPO/'bench/rl_damping_pilot.py'),
        audit_sha256=p.sha(REPO/'bench/audit_prism_state.py'),scenes=SCENES,seeds=SEEDS,arms=ARMS,
        original_sha256={s:p.sha(DATA/(s+'.txt')) for s in SCENES})
    if (ROOT/'protocol.json').exists():
        old=read('protocol.json');assert all(old[k]==v for k,v in record.items() if k!='time')
    else:put('protocol.json',record)
def prepare():
    register();folder=ROOT/'inputs';folder.mkdir(exist_ok=True);cases=[]
    for scene,target in SCENES.items():
        dims,header,raw,obs,c0,x0=load(DATA/(scene+'.txt'))
        cost0,uv0,sign0=project(c0,x0,obs);assert np.isfinite(cost0) and cost0>0
        radius=float(np.median(np.linalg.norm(x0-np.median(x0,axis=0),axis=1)));assert radius>0
        centers=-np.einsum('nji,nj->ni',rotation(c0[:,:3]),c0[:,3:6])
        oh=hashlib.sha256(raw).hexdigest()
        clean=folder/(scene+'-clean.txt')
        if not clean.exists():clean.symlink_to(DATA/(scene+'.txt'))
        assert p.sha(clean)==p.sha(DATA/(scene+'.txt'))
        cases.append(dict(scene=scene,key=scene+'-clean',level='clean',seed=None,target=target,
            initial_cost=cost0,rms_ratio=1.,amplitude=0.,sha256=p.sha(clean),observation_sha256=oh))
        for seed in SEEDS:
            rng=np.random.default_rng(seed)
            dr=rng.normal(0,.001,(dims[0],3));dc=rng.normal(0,.001*radius,centers.shape)
            dx=rng.normal(0,.001*radius,x0.shape)
            def state(a):
                c=c0.copy();c[:,:3]+=a*dr
                c[:,3:6]=-np.einsum('nij,nj->ni',rotation(c[:,:3]),centers+a*dc)
                return c,x0+a*dx
            def evaluate(a):
                c,x=state(a);cost,uv,sign=project(c,x,obs)
                return cost,uv,bool(np.isfinite(cost) and np.all(sign==sign0))
            for label,ratio in [('mild',1.10),('strong',1.50)]:
                desired=cost0*ratio**2;lo=0.;hi=.125
                while True:
                    cost,_,valid=evaluate(hi)
                    if not valid or cost>=desired:break
                    lo=hi;hi*=2
                    if hi>64:raise RuntimeError(f'Cannot bracket {scene} {seed} {label}')
                for _ in range(50):
                    mid=(lo+hi)/2;cost,_,valid=evaluate(mid)
                    if not valid or cost>=desired:hi=mid
                    else:lo=mid
                amplitude=(lo+hi)/2;c,x=state(amplitude)
                cost,uv,valid=evaluate(amplitude)
                assert valid and abs(math.sqrt(cost/cost0)/ratio-1)<1e-6
                key=f'{scene}-{label}-seed{seed}';dest=folder/(key+'.txt')
                if not dest.exists():
                    with dest.open('wb') as f:
                        f.write(header);f.write(raw);np.savetxt(f,np.r_[c.ravel(),x.ravel()],fmt='%.17g')
                dd,hh,rr,oo,cc,xx=load(dest)
                assert dd==dims and hh==header and rr==raw
                assert np.array_equal(cc,c) and np.array_equal(xx,x)
                assert np.array_equal(cc[:,6:],c0[:,6:])
                checked,uv,sign=project(cc,xx,oo)
                assert abs(checked/cost-1)<1e-12 and np.all(sign==sign0)
                item=dict(scene=scene,key=key,level=label,seed=seed,target=target,initial_cost=checked,
                    clean_cost=cost0,rms_ratio=math.sqrt(checked/cost0),amplitude=amplitude,
                    point_radius=radius,projection_displacement_px=np.percentile(np.linalg.norm(uv-uv0,axis=1),[50,95,100]).tolist(),
                    depth_sign_changes=int(np.count_nonzero(sign!=sign0)),sha256=p.sha(dest),observation_sha256=oh)
                cases.append(item);put('inputs/'+key+'.json',item);print('PREPARED',key,'RMS',item['rms_ratio'],'amplitude',amplitude,flush=True)
        put('cases.json',cases)
    assert len(cases)==21
    put('input_verification.json',dict(passed=True,cases=21,variants=18,cases_sha256=p.sha(ROOT/'cases.json')))
def run():
    register();verify=read('input_verification.json');assert verify['passed'] and verify['cases_sha256']==p.sha(ROOT/'cases.json')
    cases=read('cases.json');assert len(cases)==21
    for case in cases:assert p.sha(p.DATA/(case['key']+'.txt'))==case['sha256']
    rows=[]
    for si,scene in enumerate(SCENES):
        common=p.observations(DATA/(scene+'.txt'))
        cc=[c for c in cases if c['scene']==scene]
        for case in cc:p.CACHE[case['key']]=(case['sha256'],common)
        for rep in range(3):
            order=np.random.default_rng(2718+si*10+rep).permutation(len(cc))
            for pos,idx in enumerate(order):
                case=cc[idx];names=list(ARMS)
                if (si+rep+pos)%2:names.reverse()
                for arm in names:
                    name=f"{case['key']}-{arm}-{rep}"
                    result=p.run(name,case['key'],extra=dict(ARMS[arm],OCA_MAX_SECONDS=4,OCA_TARGET_COST=case['target']),
                        binary=BIN,initial_lambda=.1,logging=False,iterations=600,process_timeout=45)
                    initial_error=abs(result['trace'][0]['cost']/case['initial_cost']-1)
                    assert initial_error<1e-7,(name,initial_error)
                    log=(ROOT/'runs'/name/'stdout.log').read_text();m=re.search(r'CG_VALUE_SUMMARY (.*)',log)
                    summary={k:float(v) for k,v in re.findall(r'(\w+)=(\S+)',m[1])} if m else {}
                    row=dict(scene=scene,level=case['level'],seed=case['seed'],rep=rep,arm=arm,key=case['key'],
                        target=case['target'],cap=4,initial_error=initial_error,value_summary=summary,
                        hit='target_seconds' in result and result['target_seconds']<=4 and result['audit_cost']<=case['target'],
                        **{k:result.get(k) for k in ['name','target_seconds','seconds','audit_cost','audit_error','outers','rejects','matvecs']})
                    rows.append(row);put('rows.json',rows)
                    print('SCORED',name,row['hit'],row['target_seconds'],'stops',summary.get('stops',0),flush=True)
        p.CACHE.clear()
    assert len(rows)==126
    put('completion.json',dict(complete=True,runs=len(rows),native_seconds=p.native_spent()))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['prepare','run']);args=ap.parse_args()
    globals()[args.phase]()
