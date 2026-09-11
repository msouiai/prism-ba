import pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parent
GEOMETRY=ROOT.parent/'geometry_agenda'
PREVIOUS=ROOT.parent/'astra_followup'
sys.path.insert(0,str(GEOMETRY));sys.path.append(str(PREVIOUS))

def jsonable(x):
    import numpy as np
    if isinstance(x,dict):return {str(k):jsonable(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [jsonable(v) for v in x]
    if isinstance(x,np.ndarray):return jsonable(x.tolist())
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,np.bool_):return bool(x)
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x

def write_json(path,value):
    import json
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(jsonable(value),indent=2,allow_nan=False)+'\n')

def load_packed(path):
    import numpy as np
    from geometry import State
    z=np.load(path)
    return State(*[z[k].copy() for k in ['R','t','X','intr']]),z['observations'].copy()
