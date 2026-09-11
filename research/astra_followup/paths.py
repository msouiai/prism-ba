import pathlib
import sys
ROOT = pathlib.Path(__file__).resolve().parent
GEOMETRY = ROOT.parent/'geometry_agenda'
COLLECTIVE = ROOT.parent/'collective_bal'
sys.path.insert(0, str(GEOMETRY))

def jsonable(value):
    import numpy as np
    if isinstance(value, dict): return {str(k): jsonable(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [jsonable(v) for v in value]
    if isinstance(value, np.ndarray): return jsonable(value.tolist())
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (np.bool_,)): return bool(value)
    if isinstance(value, (float,np.floating)): return float(value) if np.isfinite(value) else None
    return value

def write_json(path, value):
    import json
    path.write_text(json.dumps(jsonable(value), indent=2, allow_nan=False)+'\n')

def load_packed(path):
    import numpy as np
    from geometry import State
    a = np.load(path)
    return State(*[a[k].copy() for k in ['R','t','X','intr']]), a['observations'].copy()
