import pathlib,json,shutil,subprocess,re
from build_tr_candidate import sha
R=pathlib.Path('/workspace/prism-tr-preconditioner');repo=pathlib.Path(__file__).resolve().parents[1]
cap=pathlib.Path('/workspace/prism-tr-cg-stop/capture');m=json.loads(pathlib.Path('/workspace/prism-tr-cg-stop/capture-files.json').read_text());verified={}
for name in ['W','U','R','E','b','cams','points','offsets','dimensions.txt','projected-64.x']:
 p=cap/name;d=sha(p);assert d==m[name]['sha256'];verified[name]=d
(R/'fixed-inputs-verified.json').write_text(json.dumps(verified,indent=2))
paused=json.loads(pathlib.Path('/workspace/prism-block-error/paused-verified.json').read_text())
for v in paused:
 f=(pathlib.Path('/proc')/str(v['pid'])/'stat').read_text().split();assert f[2]=='T' and f[21]==v['start_ticks']
(R/'paused-verified.json').write_text(json.dumps(paused,indent=2))
checks=0;maxerr=0
for p in R.glob('*/*.log'):
 if not any(q in p.parent.name for q in ['confirmation','screen','audit','large','winner-']):continue
 for line in p.read_text().splitlines():
  if line.startswith('CAMERA_TR o='):
   v={k:float(x) for k,x in re.findall(r'(\w+)=([^ ]+)',line)}
   if v.get('accept'):assert v['rho']>=.1 and v['prediction']>0 and v['norm']<=v['radius']*(1+1e-8);checks+=1
  if line.startswith('TR_RECURRENCE '):
   e=float(re.search('error=(\\S+)',line)[1]);assert e<1e-7;maxerr=max(maxerr,e)
(R/'final-validation.json').write_text(json.dumps(dict(accepted_steps_checked=checks,max_explicit_curvature_error=maxerr,paused_jobs=len(paused),production_sha256=sha(repo/'gpu/oca_cuda.cu')),indent=2))
P=R/'winner';P.mkdir();base=R/'pcg-v2';shutil.copytree(base/'headers',P/'headers')
for name in ['source.cu','prism-tr','stop-manifest.json']:shutil.copy2(base/name,P/name)
shutil.copy2('/workspace/prism-tr-point-prep/package/build.sh',P/'build.sh');shutil.copy2(repo/'bench/run_point_prep_package.py',P/'run.py');shutil.copy2(repo/'docs/camera_pcg_results.md',P/'RESULTS.md')
cfg=json.loads((R/'hcc-large/final-13682-storage-1.manifest.json').read_text());assert 'OCA_PCG_SCHUR' not in cfg['flags'] and 'OCA_PCG_REUSE' not in cfg['flags'];cfg['command'][4]='./prism-tr';i=cfg['command'].index('--csv');del cfg['command'][i:i+2];cfg['command'][cfg['command'].index('--state_out')+1]='example.state';cfg['recommendation']='Fresh Hcc camera-block PCG, opt-in. Same TR metric; N3 Final13682, N1 Final4585 and small panel. See RESULTS.md.';(P/'recommended_candidate.json').write_text(json.dumps(cfg,indent=2));(R/'recommended_candidate.json').write_text(json.dumps(cfg,indent=2))
(P/'README.md').write_text('Opt-in tested camera-block PCG snapshot. CUDA12.8, Eigen3, cuBLAS/cuSOLVER, sm_89. Run ./build.sh to produce prism-tr-rebuilt. Run python run.py --state-out NEW.state for the recorded Final13682 configuration; override --problem, --target and --seconds together for other scenes. The launcher requires a fresh state path. CSV output is omitted from the convenience launcher; original tested commands are in results manifests. Raw endpoint states stay in the study root. This package contains the tested v2 source (fresh Hcc recommended); the repository also has v3 experimental scale-invariant reuse. The package rebuild script is supplied; this turn tested the original builder-produced binary.\n')
records=P/'results';records.mkdir()
for p in R.rglob('*.json'):
 if P in p.parents:continue
 d=records/p.relative_to(R);d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
files=[repo/'gpu/pcg_camera.cuh',repo/'bench/build_camera_pcg.py',repo/'bench/camera_pcg_study.py',repo/'bench/report_camera_pcg.py',repo/'bench/freeze_camera_pcg.py',repo/'bench/preconditioner_confirmation.py',repo/'bench/build_fixed_preconditioner.py',repo/'bench/fixed_preconditioner.cu',repo/'docs/camera_pcg_results.md'];tooling=R/'final-tooling';tooling.mkdir()
for p in files:shutil.copy2(p,tooling/p.name)
(R/'final-tooling.json').write_text(json.dumps({str(p):sha(p) for p in files},indent=2));shutil.copy2(R/'final-tooling.json',records/'final-tooling.json');(P/'files.json').write_text(json.dumps({str(p.relative_to(P)):sha(p) for p in P.rglob('*') if p.is_file()},indent=2));subprocess.run(['tar','-czf',str(P)+'.tar.gz','-C',str(R),P.name],check=True);(R/'archive.json').write_text(json.dumps(dict(sha256=sha(str(P)+'.tar.gz'),bytes=pathlib.Path(str(P)+'.tar.gz').stat().st_size),indent=2));print('FROZEN',P)
