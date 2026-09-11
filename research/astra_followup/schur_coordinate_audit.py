"""Metadata/algebra caveat audit; does not rerun or change tested bases."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import pathlib,numpy as np
from paths import ROOT,write_json
raw=pathlib.Path('/workspace/prism-schur-physics');rows=[]
for name,k,previous in [('muell-gba146',12,11),('ladybug-598',8,7)]:
    old=np.fromfile(raw/f'{name}-o{previous}'/'E',dtype=np.float64)
    new=np.fromfile(raw/f'{name}-o{k}'/'E',dtype=np.float64)
    ratio=old/new;v=np.random.default_rng(1).normal(size=(len(old),4))
    transported=ratio[:,None]*v
    err=np.linalg.norm(new[:,None]*transported-old[:,None]*v)/np.linalg.norm(old[:,None]*v)
    assert np.isfinite(ratio).all() and err<1e-14
    rows.append({'scene':name,'E_previous_over_current_min':ratio.min(),'E_previous_over_current_max':ratio.max(),
        'physical_tangent_transport_relative_error':err,'transport_applied_in_benchmark':False})
write_json(ROOT/'schur_coordinate_audit.json',{'rows':rows,
    'limitation':'Benchmark preserves prior study untransported normalized-coordinate history. Current S/preconditioner/RHS and residual tests remain valid. A normalization-transported history is untested; pose-chart transport may also be needed for a different nonlinear retraction.'})
print(rows)
