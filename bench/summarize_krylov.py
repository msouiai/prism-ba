#!/usr/bin/env python3
import argparse,json,pathlib,re,statistics,math
p=argparse.ArgumentParser();p.add_argument('--data',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args();m=json.loads((a.data/'preregistered.json').read_text());rows=[]
for f in a.data.glob('*.log'):
 scene,outer=f.stem.rsplit('-outer',1)
 for method,rep,tol,seconds,mv,curvature,residuals in re.findall(r'KRYLOV_AUDIT method=(\S+) rep=(\d+) tol=(\S+) seconds=(\S+) matvecs=(\d+) curvature_ok=(\d+) residuals=(\S+)',f.read_text()):
  res=[float(x) for x in residuals.split(',')];rows.append(dict(scene=scene,outer=int(outer),method=method,rep=int(rep),tol=float(tol),seconds=float(seconds),matvecs=int(mv),residuals=res,valid=bool(int(curvature)) and all(math.isfinite(x) and x<=float(tol)*1.01 for x in res)))
lines=['# Fixed-Schur-system Krylov audit','',
 'A diagnostic executable captures the actual operator, RHS and five shifts at an outer iteration. Both methods solve those same equations. Shared recurrence and independent CG each stop at requested relative residual, with a 2,048-iteration cap. True residual checks and solution export occur outside timing. Independent solves can stop each shift separately; the shared sweep follows the seed system.',
 'Each captured system has N=3 alternating-order repeats. A speed ratio is reported only if every solve meets the true residual target within 1% numerical slack and has no detected nonpositive curvature. Different snapshots are not repetitions of one operator. No nonlinear speedup follows from this microbenchmark alone.',
 '', '| Scene | Outer | Tolerance | N shared/independent | Shared/independent matvec medians | Shared/independent seconds medians | Independent/shared time | Max true residual shared/independent |',
 '|---|---:|---:|---|---|---|---|---|']
for scene in m['scenes']:
 for outer in m['outers']:
  for tol in m['tolerances']:
   ss=[r for r in rows if (r['scene'],r['outer'],r['tol'],r['method'])==(scene,outer,tol,'shared')];ii=[r for r in rows if (r['scene'],r['outer'],r['tol'],r['method'])==(scene,outer,tol,'independent')]
   if len(ss)!=3 or len(ii)!=3:lines.append(f'| {scene} | {outer} | {tol:g} | {len(ss)}/{len(ii)} | — | — | incomplete | — |');continue
   def resmax(rr):
    vals=[x for r in rr for x in r['residuals']]
    return f'{max(vals):.3g}' if all(math.isfinite(x) for x in vals) else 'nonfinite'
   med=lambda rr,k:statistics.median(r[k] for r in rr)
   ratio=f"{med(ii,'seconds')/med(ss,'seconds'):.3f}x" if all(r['valid'] for r in ss+ii) else 'accuracy/curvature gate failed'
   lines.append(f"| {scene} | {outer} | {tol:g} | 3/3 | {med(ss,'matvecs'):g}/{med(ii,'matvecs'):g} | {med(ss,'seconds'):.6f}/{med(ii,'seconds'):.6f} | {ratio} | {resmax(ss)}/{resmax(ii)} |")
a.out.write_text('\n'.join(lines)+'\n');(a.data/'results.json').write_text(json.dumps([{**r, 'residuals':[x if math.isfinite(x) else None for x in r['residuals']]} for r in rows],indent=2,allow_nan=False)+'\n')
