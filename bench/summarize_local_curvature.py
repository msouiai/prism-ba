#!/usr/bin/env python3
import json,pathlib,statistics,collections
r=pathlib.Path('/workspace/prism-local-curvature');rows=[json.loads(p.read_text()) for p in sorted((r/'measurements').glob('*.json'))];groups={}
for scene in sorted({x['scene'] for x in rows}):
 rr=[x for x in rows if x['scene']==scene];models={}
 for h in [.5,.125,.03125]:
  pairs=[(x,next(m for m in x['models'] if m['radius']==h)) for x in rr];n=len(pairs);beat=sum(bool(x['original_rescue'] and m['coupled']['armijo'] and m['coupled']['cost']<x['original_rescue']['cost']) for x,m in pairs)
  models[str(h)]=dict(n=n,armijo=sum(m['coupled']['armijo'] for x,m in pairs),beats_original=beat,beats_scalar=sum(m['coupled']['armijo'] and m['coupled']['cost']<m['scalar']['cost']-1e-8*max(1,x['base']['cost']) for x,m in pairs),median_gn_error=statistics.median(v['gn_error'] for x,m in pairs for v in m['validation']),median_secant_error=statistics.median(v['secant_error'] for x,m in pairs for v in m['validation']),indefinite=sum(m['min_eigenvalue']<0 for x,m in pairs))
 groups[scene]=dict(captures=n,models=models,median_full_top10_share=statistics.median(x['full']['top10_cost_share'] for x in rr),full_depth_flips=[x['full']['depth_flips'] for x in rr])
initial=['venice-52','dubrovnik-356','ladybug-1197'];gate=all(s in groups and groups[s]['models']['0.125']['armijo']/groups[s]['captures']>=.8 and groups[s]['models']['0.125']['beats_original']/groups[s]['captures']>=.6 for s in initial)
out=dict(captures=len(rows),objective_evaluations=sum(x['objective_evaluations'] for x in rows),cpu_seconds=sum(x['seconds'] for x in rows),max_state_error=max(x['cpu_audits']['state'] for x in rows),max_full_step_error=max(x['cpu_audits']['full'] for x in rows),groups=groups,online_gate=gate)
(r/'summary.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
