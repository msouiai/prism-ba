#!/usr/bin/env python3
"""Bounded Final13682 paired initialization-noise extension."""
import argparse,datetime,hashlib,json,math,pathlib,re
import numpy as np
import cg_value_noise as common
import rl_damping_pilot as p

ROOT=pathlib.Path('/tmp/prism-cg-value-noise-large')
REPO=pathlib.Path(__file__).parents[1]
SOURCE=pathlib.Path('/workspace/bal/final-13682.txt')
BIN=common.BIN;SHA=common.SHA;ARMS=common.ARMS;SEEDS=common.SEEDS
TARGET=27591576.557625167;CHUNK=250000
p.ROOT=ROOT;p.DATA=ROOT/'inputs';p.NATIVE_CAP=550
def read(n):return json.loads((ROOT/n).read_text())
def put(n,v):p.put(ROOT/n,v)
def register():
    assert p.sha(BIN)==SHA
    record=dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),binary_sha256=SHA,
        code_sha256=p.sha(__file__),helper_sha256=p.sha(REPO/'bench/cg_value_noise.py'),
        protocol_sha256=p.sha(REPO/'docs/cg_value_noise_large_protocol.md'),
        baseline_flags_sha256=p.sha(p.SELECTED),driver_sha256=p.sha(REPO/'bench/rl_damping_pilot.py'),
        audit_sha256=p.sha(REPO/'bench/audit_prism_state.py'),original_sha256=p.sha(SOURCE),
        target=TARGET,seeds=SEEDS,arms=ARMS)
    if (ROOT/'protocol.json').exists():
        old=read('protocol.json');assert all(old[k]==v for k,v in record.items() if k!='time')
    else:put('protocol.json',record)
def project(c,x,obs,sign0=None,detail=False):
    R=common.rotation(c[:,:3]);cost=np.longdouble(0);valid=True
    uvall=np.empty((len(obs),2)) if detail else None
    signs=np.empty(len(obs),dtype=bool) if detail else None
    for start in range(0,len(obs),CHUNK):
        o=obs[start:start+CHUNK];ci=o[:,0].astype(np.int64);pi=o[:,1].astype(np.int64)
        q=np.einsum('nij,nj->ni',R[ci],x[pi])+c[ci,3:6]
        sg=np.signbit(q[:,2])
        if sign0 is not None:valid=valid and bool(np.all(sg==sign0[start:start+len(o)]))
        with np.errstate(divide='ignore',invalid='ignore',over='ignore'):
            uv=-q[:,:2]/q[:,2,None];r2=np.sum(uv*uv,axis=1)
            uv*= (c[ci,6]*(1+c[ci,7]*r2))[:,None]
            cost+=.5*np.sum((uv-o[:,2:4])**2,dtype=np.longdouble)
        if detail:uvall[start:start+len(o)]=uv;signs[start:start+len(o)]=sg
    return float(cost),uvall,signs,bool(valid and np.isfinite(cost))
def prepare():
    register();folder=ROOT/'inputs';folder.mkdir(exist_ok=True)
    dims,header,raw,obs,c0,x0=common.load(SOURCE)
    cost0,uv0,sign0,valid=project(c0,x0,obs,detail=True);assert valid and cost0>0
    print('BASE',dims,'cost',cost0,flush=True)
    radius=float(np.median(np.linalg.norm(x0-np.median(x0,axis=0),axis=1)));assert radius>0
    centers=-np.einsum('nji,nj->ni',common.rotation(c0[:,:3]),c0[:,3:6])
    oh=hashlib.sha256(raw).hexdigest();clean=folder/'final-13682-clean.txt'
    if not clean.exists():clean.symlink_to(SOURCE)
    assert p.sha(clean)==read('protocol.json')['original_sha256']
    cases=[dict(scene='final-13682',key='final-13682-clean',level='clean',seed=None,target=TARGET,
        initial_cost=cost0,rms_ratio=1.,amplitude=0.,sha256=p.sha(clean),observation_sha256=oh)]
    for seed in SEEDS:
        rng=np.random.default_rng(seed)
        dr=rng.normal(0,.001,(dims[0],3));dc=rng.normal(0,.001*radius,centers.shape)
        dx=rng.normal(0,.001*radius,x0.shape)
        def state(a):
            c=c0.copy();c[:,:3]+=a*dr
            c[:,3:6]=-np.einsum('nij,nj->ni',common.rotation(c[:,:3]),centers+a*dc)
            return c,x0+a*dx
        def evaluate(a):
            c,x=state(a);value,_,_,ok=project(c,x,obs,sign0)
            return value,ok
        desired=cost0*1.1**2;lo=0.;flo=cost0;hi=.125
        while True:
            fhi,ok=evaluate(hi)
            if not ok:fhi=float('inf')
            print('BRACKET',seed,hi,fhi,flush=True)
            if fhi>=desired:break
            lo=hi;flo=fhi;hi*=2
            if hi>64:raise RuntimeError(f'Cannot bracket seed {seed}')
        for it in range(50):
            fraction=float(np.clip((desired-flo)/(fhi-flo),.1,.9)) if math.isfinite(fhi) and fhi>flo else .5
            amplitude=lo+fraction*(hi-lo);value,ok=evaluate(amplitude)
            error=abs(math.sqrt(value/cost0)/1.1-1) if ok else float('inf')
            print('CALIBRATE',seed,it,amplitude,error,flush=True)
            if error<=1e-7:break
            if not ok or value>=desired:hi=amplitude;fhi=value if ok else float('inf')
            else:lo=amplitude;flo=value
        assert ok and error<=1e-6
        c,x=state(amplitude);key=f'final-13682-mild-seed{seed}';dest=folder/(key+'.txt')
        if not dest.exists():
            with dest.open('wb') as f:
                f.write(header);f.write(raw);np.savetxt(f,np.r_[c.ravel(),x.ravel()],fmt='%.17g')
        dd,hh,rr,oo,cc,xx=common.load(dest)
        assert dd==dims and hh==header and rr==raw
        assert np.array_equal(cc,c) and np.array_equal(xx,x) and np.array_equal(cc[:,6:],c0[:,6:])
        checked,uv,sign,ok=project(cc,xx,oo,sign0,detail=True)
        assert ok and abs(checked/value-1)<1e-12
        displacement=np.linalg.norm(uv-uv0,axis=1)
        item=dict(scene='final-13682',key=key,level='mild',seed=seed,target=TARGET,
            initial_cost=checked,clean_cost=cost0,rms_ratio=math.sqrt(checked/cost0),amplitude=amplitude,
            point_radius=radius,projection_displacement_px=np.percentile(displacement,[50,95,100]).tolist(),
            depth_sign_changes=int(np.count_nonzero(sign!=sign0)),sha256=p.sha(dest),observation_sha256=oh)
        cases.append(item);put('inputs/'+key+'.json',item);put('cases.json',cases)
        print('PREPARED',key,item['rms_ratio'],item['projection_displacement_px'],flush=True)
        del dd,hh,rr,oo,cc,xx,uv,sign,displacement,c,x,dx
    put('input_verification.json',dict(passed=True,cases=4,variants=3,cases_sha256=p.sha(ROOT/'cases.json')))
def run():
    register();verify=read('input_verification.json');assert verify['passed'] and verify['cases_sha256']==p.sha(ROOT/'cases.json')
    cases=read('cases.json');assert len(cases)==4
    for case in cases:assert p.sha(p.DATA/(case['key']+'.txt'))==case['sha256']
    original=p.observations(SOURCE)
    for case in cases:p.CACHE[case['key']]=(case['sha256'],original)
    rows=[]
    for rep in range(3):
        for pos,idx in enumerate(np.random.default_rng(2718+rep).permutation(4)):
            case=cases[idx];names=list(ARMS)
            if (rep+pos)%2:names.reverse()
            for arm in names:
                name=f"{case['key']}-{arm}-{rep}"
                result=p.run(name,case['key'],extra=dict(ARMS[arm],OCA_MAX_SECONDS=20,OCA_TARGET_COST=TARGET),
                    binary=BIN,initial_lambda=.1,logging=False,iterations=600,process_timeout=180)
                error=abs(result['trace'][0]['cost']/case['initial_cost']-1);assert error<1e-7
                log=(ROOT/'runs'/name/'stdout.log').read_text();m=re.search(r'CG_VALUE_SUMMARY (.*)',log)
                summary={k:float(v) for k,v in re.findall(r'(\w+)=(\S+)',m[1])} if m else {}
                row=dict(scene='final-13682',level=case['level'],seed=case['seed'],rep=rep,arm=arm,key=case['key'],
                    target=TARGET,cap=20,initial_error=error,value_summary=summary,
                    hit='target_seconds' in result and result['target_seconds']<=20 and result['audit_cost']<=TARGET,
                    **{k:result.get(k) for k in ['name','target_seconds','seconds','audit_cost','audit_error','outers','rejects','matvecs']})
                rows.append(row);put('rows.json',rows)
                print('SCORED',name,row['hit'],row['target_seconds'],'stops',summary.get('stops',0),flush=True)
    assert len(rows)==24
    put('completion.json',dict(complete=True,runs=24,native_seconds=p.native_spent()))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['prepare','run']);args=ap.parse_args()
    globals()[args.phase]()
