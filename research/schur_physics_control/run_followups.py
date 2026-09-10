#!/usr/bin/env python3
"""Short transfer and compilation/instrumentation controls, then menu audit."""
import pathlib,json,os,subprocess,fcntl,time,shutil
ROOT=pathlib.Path(__file__).resolve().parent;from paths import OUT
base={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','COLMAP_MFREE','MF_DEBUG'))}
cfg=json.loads((ROOT.parent/'eta2_champion/champion.json').read_text())
def run(path,cmd,flags,timeout=150):
 print(path.name,flush=True);t=time.monotonic()
 with path.open('w') as f:
  try:rc=subprocess.run(cmd,env=base|flags,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired:rc=124
 path.with_suffix('.json').write_text(json.dumps({'command':cmd,'flags':flags,'returncode':rc,'process_seconds':time.monotonic()-t},indent=2)+'\n');return rc
transfer=OUT/'transfer';transfer.mkdir(exist_ok=True)
(transfer/'protocol.json').write_text(json.dumps({'scene':'ladybug-598','repeats':3,'ranks':[0,8,16],'target':182215.47143051997,'target_source':'/tmp/prism-ba-accuracy/train-rows.json: pre-existing original arm target; no fitting to new candidate outputs'},indent=2)+'\n')
control=OUT/'audit-controls';control.mkdir(exist_ok=True)
(control/'protocol.json').write_text(json.dumps({'scene':'final-3068','repeats':10,'arms':['delivered-v2','rebuilt-off'],'purpose':'Separate source rebuild/cohort variability from gradient instrumentation. Both disable the new diagnostic and use identical original stopping settings.','process_cap':30},indent=2)+'\n')
menu=OUT/'menu';menu.mkdir(exist_ok=True)
(menu/'protocol.json').write_text(json.dumps({'repeats':3,'ranks':[0,8,16],'factors':[.25,.5,1,2,4],'basis_amendment':'Before testing: retain current slow Ritz vectors and replace the last with the actually computed center step. If only one/two directions exist, report actual rank. Seed solve, projection, factor refresh, validation and CPU eigendecomposition charged.','comparison':'Five projected candidates versus five independent Hcc solves; also report the single center cost. Passing only the center does not pass the menu.','cpu_setup_note':'CPU reference eigendecomposition setup is measured once per capture and charged to each projected batch; GPU-only subtotal is explicitly separate.'},indent=2)+'\n')
with open('/tmp/prism_gpu.lock','w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 # Transfer costs only a few seconds; useful even though Muell did not win.
 for rep in range(3):
  ranks=[0,8,16];ranks=ranks[rep:]+ranks[:rep]
  for r in ranks:
   cmd=[str(ROOT/'build/prism-coarse'),'--problem','/workspace/bal/ladybug-598.txt',*cfg['cli']]
   run(transfer/f'r{r}-{rep}.log',cmd,cfg['flags']|{'OCA_COARSE_RANK':str(r),'OCA_TARGET_COST':'182215.47143051997','OCA_MAX_SECONDS':'4'})
 # Menu residual validation before spending time on additional noise controls.
 p=OUT/'ladybug-598-o8';ms=json.loads((p/'spectral_manifest.json').read_text())['compute_ms_including_input_read']
 cmd=['compute-sanitizer','--tool','memcheck','--error-exitcode','9',str(ROOT/'build/menu'),str(p),str(ms)]
 assert run(menu/'memcheck.log',cmd,{'PRISM_MENU_REPS':'1'},180)==0
 for name in ['muell-gba146-o12','ladybug-598-o8','final-1936-o0']:
  p=OUT/name;ms=json.loads((p/'spectral_manifest.json').read_text())['compute_ms_including_input_read']
  assert run(menu/(name+'.log'),[str(ROOT/'build/menu'),str(p),str(ms)],{})==0
 shutil.copy2(ROOT/'build/menu-manifest.json',menu/'manifest.json')
 flags={'OCA_RHO_LAMBDA':'1','OCA_GRID_DOWN':'2','OCA_RHO_SHIFT':'1','OCA_ALPHA_RHO':'1'}
 cli=['--problem','/workspace/bal/final-3068.txt','--algo','mfree_shifted_cg','--dof9','--zero_k2','--max_iter','60','--lam0','10.0','--tau_pt','3e-3','--func-tol','1e-6','--max-consec-fail','3']
 arms=[('delivered-v2','/workspace/multishift_repro/oca_cuda_v2'),('rebuilt-off',str(ROOT/'build/v2/audit-v2'))]
 for rep in range(10):
  for name,binary in (arms if rep%2==0 else arms[::-1]):run(control/f'{name}-{rep:02}.log',[binary,*cli],flags,30)
print('DONE transfer/menu/controls',flush=True)
