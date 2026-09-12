#!/usr/bin/env python3
"""Read-only endpoint class and controller diagnostics; no new runs or tuning."""
import gzip,json,re,struct
from pathlib import Path
import numpy as np
from run import P,G

def state_costs(path,dims,obs):
    with gzip.open(path,'rb') as f:b=f.read()
    assert b[:8]==b'PRISMS01' and struct.unpack('<QQQ',b[8:32])==dims
    nc,np_,no=dims;v=np.frombuffer(b,dtype='<f8',offset=32);o=0
    R=v[o:o+9*nc].reshape(nc,3,3);o+=9*nc
    t=v[o:o+3*nc].reshape(nc,3);o+=3*nc
    X=v[o:o+3*np_].reshape(np_,3);o+=3*np_
    intr=v[o:o+3*nc].reshape(3,nc);assert len(v)==o+3*nc and np.all(intr[2]==0)
    costs=np.zeros(np_)
    for start in range(0,no,100000):
        ob=obs[start:start+100000];ci=ob[:,0].astype(int);pi=ob[:,1].astype(int)
        Y=np.einsum('nij,nj->ni',R[ci],X[pi])+t[ci]
        uv=-Y[:,:2]/Y[:,2,None];r2=(uv*uv).sum(axis=1)
        res=uv*(intr[0,ci]*(1+intr[1,ci]*r2))[:,None]-ob[:,2:4]
        costs+=np.bincount(pi,weights=.5*(res*res).sum(axis=1),minlength=np_)
    return costs
def main():
    rows=json.loads((P/'tail-results.json').read_text());answer={}
    for scene in sorted({r['scene'] for r in rows}):
        dims,obs=G.observations(Path('/workspace/bal')/(scene+'.txt'))
        counts=np.bincount(obs[:,1].astype(int),minlength=dims[1]);cl=np.where(counts<=2,0,np.where(counts<=5,1,2))
        ends={};diagnostics=[]
        for r in [r for r in rows if r['scene']==scene]:
            folder=P/r['source'];costs=state_costs(folder/'endpoint.state.gz',dims,obs)
            assert abs(costs.sum()-r['cost'])/max(1,r['cost'])<1e-12
            ends[r['rep'],r['arm']]=costs
            text=(folder/'stdout.log').read_text()
            traces=[dict((k,float(v)) for k,v in re.findall(r'(\w+)=([^ ]+)',line))
                    for line in re.findall(r'^ATTR_RADIUS (.*)$',text,re.M)]
            last=traces[-1]
            diagnostics.append(dict(rep=r['rep'],arm=r['arm'],cost=r['cost'],
              class_costs=[float(costs[cl==i].sum()) for i in range(3)],
              last_raw_norm=last['raw_norm'],last_clipped_norm=last['norm'],
              raw_clipped_ratio=last['raw_norm']/max(1e-300,last['norm']),
              last_radius=last['radius'],last_lambda=last['lambda'],last_rho=last['rho']))
        pairs=[]
        for rep in range(5):
            diff=ends[rep,'on']-ends[rep,'off'];pos=np.maximum(diff,0)
            pairs.append(dict(rep=rep,total_delta=float(diff.sum()),
              class_delta=[float(diff[cl==i].sum()) for i in range(3)],
              top200_share_positive_cost_increase=float(np.sort(pos)[-200:].sum()/max(1e-300,pos.sum()))))
        answer[scene]=dict(runs=diagnostics,pairs=pairs,
          note='Endpoint class differences compare complete coupled trajectories; they do not isolate causal point-only effects.')
    G.write(P/'tail_diagnostics.json',answer)
    for scene,d in answer.items():
        for arm in ['off','on']:
            rr=[r for r in d['runs'] if r['arm']==arm]
            print(scene,arm,'median class costs',np.median([r['class_costs'] for r in rr],axis=0),
              'clip ratio',np.median([r['raw_clipped_ratio'] for r in rr]),'rho',np.median([r['last_rho'] for r in rr]))
        print('class delta pairs',[r['class_delta'] for r in d['pairs']])
if __name__=='__main__':main()
