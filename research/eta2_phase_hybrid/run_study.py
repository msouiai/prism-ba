#!/usr/bin/env python3
"""Frozen phase-hybrid target runs; use the previously audited native launcher."""
import pathlib,sys,json,hashlib,re,argparse,statistics,math
P=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(P.parent/'champion_point_followup'))
import run_native as base
base.P=P
base.ARMS={'champion':{},'shared_center':{'OCA_PHASE_HYBRID':'1'},'shared_menu':{'OCA_PHASE_HYBRID':'2'},'menu_feedback':{'OCA_PHASE_HYBRID':'3'}}
BIN=P/'build/prism-hybrid';ORIG=base.ORIGINAL
SMALL=['ladybug-49','dubrovnik-88','venice-52'];LARGE=['final-3068','final-4585']
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(scene,arm,rep,stage,target=None,cap=12,binary=BIN,maxiter=600):
    r=base.run(scene,arm,rep,stage,target,cap,binary,maxiter)
    folder=P/r['source'];text=(folder/'stdout.log').read_text();text=re.sub(r'\[R9\] wrote [^\n]+\n','',text)
    assert json.loads((folder/'manifest.json').read_text())['binary_sha256']==sha(binary)
    m=re.search(r'MFCG: accepts=(\d+)\s+rejects=(\d+)\s+total_matvecs=(\d+)',text);assert m,folder
    r.update(accepted=int(m[1]),rejects=int(m[2]),matvecs=int(m[3]))
    m=re.search(r'PHASE_SUMMARY mode=(\d+) sweeps=(\d+) failures=(\d+) products=(\d+) seconds=(\S+) open=(\d+)',text)
    if m:r.update(hybrid_sweeps=int(m[2]),hybrid_failures=int(m[3]),hybrid_products=int(m[4]),hybrid_seconds=float(m[5]),hybrid_open=bool(int(m[6])))
    hand=re.search(r'PHASE_HANDOVER outer=(\d+) reason=(\S+)',text)
    r.update(handover_outer=int(hand[1]) if hand else None,handover_reason=hand[2] if hand else None)
    traces=[]
    for line in text.splitlines():
        if line.startswith('PHASE_SWEEP '):
            fields=dict(re.findall(r'(\w+)=(\S+)',line));traces.append(fields)
    r['sweeps']=traces
    r['stop_reason']='target' if r['hit'] else 'budget' if r['cap_hit'] else 'ftol' if 'converged (OCA_FTOL' in text else 'other_or_outer_cap'
    write(folder/'result.json',r);return r

def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['parity','small','calibrate-large','large']);args=ap.parse_args()
    assert sha(ORIG)==base.CONF['binary_sha256']
    if args.stage=='parity':
        rows=[]
        for scene in SMALL:
            for rep in range(3):
                for name,b in [('original-parity',ORIG),('new-parity',BIN)]:rows.append(run(scene,'champion',rep,name,binary=b,maxiter=8))
        write(P/'parity.json',rows);return
    if args.stage=='small':
        refpath=P.parent/'champion_point_followup/calibrate-targets.json'
        refs=json.loads(refpath.read_text())['targets'];targets={s:refs[s]*1.01/1.001 for s in SMALL}
        frozen=P/'small-targets.json';value=dict(targets=targets,reference_file=str(refpath),reference_sha256=sha(refpath),protocol_sha256=sha(P/'PROTOCOL.md'))
        if frozen.exists():assert json.loads(frozen.read_text())==value
        else:write(frozen,value)
        rows=[];arms=list(base.ARMS)
        for s in SMALL:
            for rep in range(3):
                for a in arms[rep:]+arms[:rep]:rows.append(run(s,a,rep,'small',targets[s]))
        write(P/'small-results.json',rows)
        paired=[s for s in SMALL if all(r['hit'] for r in rows if r['scene']==s and r['arm'] in ['shared_menu','menu_feedback'])]
        scores=[]
        for a in ['shared_menu','menu_feedback']:
            rr=[r for r in rows if r['arm']==a];hit=sum(r['hit'] for r in rr)
            metric=math.exp(sum(math.log(statistics.median(r['target_seconds'] for r in rr if r['scene']==s)) for s in paired)/len(paired)) if paired else None
            scores.append(dict(arm=a,hits=hit,paired_scenes=paired,time_geomean=metric))
        winner=min(scores,key=lambda r:(-r['hits'],r['time_geomean'] if r['time_geomean'] is not None else float('inf'),r['arm']!='shared_menu'))['arm']
        write(P/'selection.json',dict(selected=winner,scores=scores,interpretation='Choice for the requested bimodal check; not a champion promotion.'))
    elif args.stage=='calibrate-large':
        rows=[run(s,'champion',rep,'calibrate-large',cap=15,binary=ORIG) for s in LARGE for rep in range(3)]
        targets={s:1.01*statistics.median(r['final_cost'] for r in rows if r['scene']==s) for s in LARGE}
        write(P/'large-targets.json',dict(targets=targets,rows=rows,protocol_sha256=sha(P/'PROTOCOL.md')))
    else:
        targets=json.loads((P/'large-targets.json').read_text())['targets'];selected=json.loads((P/'selection.json').read_text())['selected'];rows=[]
        for s in LARGE:
            for rep in range(10):
                arms=['champion',selected];order=arms[rep%2:]+arms[:rep%2]
                for a in order:rows.append(run(s,a,rep,'large',targets[s],15))
        write(P/'large-results.json',rows)
if __name__=='__main__':main()
