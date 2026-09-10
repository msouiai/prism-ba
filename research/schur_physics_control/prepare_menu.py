#!/usr/bin/env python3
"""CPU reference eigendecompositions for the exact projected damping family."""
import pathlib,time,json,numpy as np,hashlib
from paths import OUT
for name in ['muell-gba146-o12','ladybug-598-o8','final-1936-o0']:
 p=OUT/name;meta=(p/'dimensions.txt').read_text().split();n=int(meta[2]);start=time.monotonic()
 R=np.fromfile(p/'R0',dtype=np.float64).reshape(n,6)
 diag=np.fromfile(p/'Cdiag',dtype=np.float64).reshape(n,3)
 D=np.maximum(diag,1e-3*diag.sum(axis=1,keepdims=True)/3)
 assert np.all(D>0), 'zero diagonal needs separately modeled absolute safeguard'
 C=np.empty((n,3,3))
 C[:,0,0]=R[:,0]**2;C[:,0,1]=C[:,1,0]=R[:,0]*R[:,1];C[:,0,2]=C[:,2,0]=R[:,0]*R[:,2]
 C[:,1,1]=R[:,1]**2+R[:,3]**2;C[:,1,2]=C[:,2,1]=R[:,1]*R[:,2]+R[:,3]*R[:,4]
 C[:,2,2]=R[:,2]**2+R[:,4]**2+R[:,5]**2
 inv=1/np.sqrt(D)
 normalized=C*inv[:,:,None]*inv[:,None,:]
 eig,V=np.linalg.eigh(normalized)
 F=inv[:,:,None]*V
 compute_ms=1000*(time.monotonic()-start)
 assert np.min(eig)+float(meta[4])*.25>0, 'menu has nonpositive spectral point denominator'
 F.tofile(p/'spectral_F');eig.tofile(p/'spectral_values')
 reconstruction=(V*eig[:,None,:])@V.transpose(0,2,1)
 relative=float(np.linalg.norm(reconstruction-normalized)/np.linalg.norm(normalized))
 def sha(x):
  with x.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
 data={'point_count':n,'compute_ms_including_input_read':compute_ms,'relative_normalized_reconstruction_error':relative,'minimum_eigenvalue':float(eig.min()),'maximum_eigenvalue':float(eig.max()),'note':'CPU reference setup charged to projected menus; files are exact inputs, not a measured GPU eigensolver','input_sha256':{f:sha(p/f) for f in ['R0','Cdiag']},'output_sha256':{f:sha(p/f) for f in ['spectral_F','spectral_values']}}
 (p/'spectral_manifest.json').write_text(json.dumps(data,indent=2)+'\n')
 print(name,json.dumps(data),flush=True)
