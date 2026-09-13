#!/usr/bin/env python3
"""Parse compact D11 logs and write the immutable gate result."""
from __future__ import annotations
import hashlib, json, pathlib, re, statistics

HERE=pathlib.Path(__file__).resolve().parent
EV=HERE/'evidence'

def tokens(line):
    out={}
    for key,value in re.findall(r'(\w+)=([^ ]+)',line):
        try: out[key]=float(value) if any(c in value for c in '.eE') else int(value)
        except ValueError: out[key]=value
    return out

def parse(scene):
    path=EV/f'{scene}.log';top=None;rows=[]
    for line in path.read_text().splitlines():
        if line.startswith('TOPOLOGY '): top=tokens(line)
        elif line.startswith('GSP '): rows.append(tokens(line))
    assert top and len(rows)==9
    arms={}
    for q in (0,2,3):
        group=[x for x in rows if x['q']==q]
        arms[str(q)]={k:statistics.median(x[k] for x in group) for k in
            ('iterations','products','true_relative','assembly_ms','symbolic_ms','factor_ms','solve_ms','preconditioner_ms','factor_plus_solve_ms')}
        arms[str(q)].update({k:group[0][k] for k in ('selected','offdiag_blocks','matrix_nnz','factor_nnz','hit','neg')})
    return {'topology':top,'arms':arms,'log_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

result={'muell-gba146':parse('muell-gba146'),'ladybug-598':parse('ladybug-598')}
for scene in ('muell-gba146','ladybug-598','final-1936'):
    fixed=pathlib.Path('/workspace/prism-schur-eta2')/scene/'fixed.log'
    base=[tokens(x) for x in fixed.read_text().splitlines() if x.startswith('FIXED ') and 'mode=1 ' in x and 'tolerance=0.5 ' in x]
    result.setdefault(scene,{})['frozen_hcc']={k:statistics.median(x[k] for x in base) for k in ('iterations','products','true_relative','setup_ms','solve_ms','total_ms')}
top=tokens((EV/'final-1936-topology.log').read_text().strip())
result['final-1936']['topology']=top

mu=result['muell-gba146'];lb=result['ladybug-598'];q3=mu['arms']['3']
dense=(9*mu['topology']['nc'])**2
gates={
 'calibration_iteration_match':mu['arms']['0']['iterations']==mu['frozen_hcc']['iterations'],
 'calibration_residual_abs_delta':abs(mu['arms']['0']['true_relative']-mu['frozen_hcc']['true_relative']),
 'muell_product_reduction_fraction':1-q3['products']/mu['frozen_hcc']['products'],
 'muell_factor_plus_solve_below_frozen':q3['factor_plus_solve_ms']<mu['frozen_hcc']['total_ms'],
 'ladybug_products_not_increased':lb['arms']['3']['products']<=lb['frozen_hcc']['products'],
 'muell_factor_fill_fraction_of_dense':q3['factor_nnz']/dense,
 'fixed_cpu_gate_pass':None,
 'native_backend_gate_pass':False,
}
gates['fixed_cpu_gate_pass']=all((gates['calibration_iteration_match'],gates['calibration_residual_abs_delta']<1e-10,
                                  gates['muell_product_reduction_fraction']>=.3,gates['muell_factor_plus_solve_below_frozen'],
                                  gates['ladybug_products_not_increased'],gates['muell_factor_fill_fraction_of_dense']<.2))
result['gates']=gates
result['backend_probes']={
 'cusolver_lowlevel':{'scene':'ladybug-598','outcome':'terminated after >90 s before analysis/factor result','usable':False},
 'cudss_0.8.0.10':{'scene':'ladybug-598','outcome':'terminated after >60 s in symbolic analysis','usable':False,
                   'wheel_sha256':'602eb6e394c6595a698ed10b74cf5e251a0fbbd6e84da9a755e02fafb6c60ef1'},
 'final1936_q3':{'outcome':'terminated after >60 s in serial construction/factor path; no scored solve','usable':False,
                 'reason':'frozen Hcc already reaches eta in one iteration (two products, 16.35 ms total)'}
}
result['source_hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
    [HERE/'gsp_fixed.cu',HERE/'build.py',HERE/'run.py',pathlib.Path(__file__),HERE.parent/'D11_VISIBILITY_SUBGRAPH_PROTOCOL.md']}
(HERE.parent/'d11-visibility-subgraph-results.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({'gates':gates,'muell_q3':q3,'ladybug_q3':lb['arms']['3']},indent=2))
