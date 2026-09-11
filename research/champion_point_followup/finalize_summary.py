import pathlib,json,statistics,math
P=pathlib.Path(__file__).resolve().parent
rows=[json.loads(f.read_text()) for f in (P/'evidence').glob('*/*/result.json')]
out=[]
for stage in ['conditional','original-target-repeat','generated-target-repeat','tolerance-1.005','tolerance-1.01']:
 for scene in sorted({r['scene'] for r in rows if r['stage']==stage}):
  for arm in sorted({r['arm'] for r in rows if r['stage']==stage and r['scene']==scene}):
   rs=[r for r in rows if r['stage']==stage and r['scene']==scene and r['arm']==arm];hits=[r for r in rs if r['hit']]
   out.append(dict(stage=stage,scene=scene,arm=arm,n=len(rs),hits=len(hits),hit_seconds=statistics.median(r['target_seconds'] for r in hits) if hits else None,
      **{k:statistics.median(r.get(k,0) for r in rs) for k in ['outers','rejects','matvecs','overlay_calls','overlay_selected','overlay_seconds','final_cost']},
      by_one_second=sum(r['hit'] and r['target_seconds']<=1 for r in rs)))
a=next(r for r in out if r['stage']=='conditional' and r['scene']=='venice-52' and r['arm']=='polish_gate')
b=next(r for r in out if r['stage']=='conditional' and r['scene']=='venice-52' and r['arm']=='champion')
success=a['hits']+b['hits'];total=a['n']+b['n'];den=math.comb(total,a['n'])
probs={k:math.comb(success,k)*math.comb(total-success,a['n']-k)/den for k in range(max(0,a['n']-(total-success)),min(a['n'],success)+1)}
p1=sum(p for k,p in probs.items() if k>=a['hits']);p2=sum(p for p in probs.values() if p<=probs[a['hits']]+1e-12)
result=dict(rows=out,venice_fisher_one_sided_p=p1,venice_fisher_two_sided_p=p2,warning='Exploratory post-screen hypothesis; medians condition on successful target hits. No unconditional speedup inferred from them.')
(P/'conditional_summary.json').write_text(json.dumps(result,indent=2)+'\n')
for r in out:print(r['stage'],r['scene'],r['arm'],r['hits'],r['n'],r['hit_seconds'],r['overlay_calls'])
print('nominal exact p, one and two sided:',p1,p2)
