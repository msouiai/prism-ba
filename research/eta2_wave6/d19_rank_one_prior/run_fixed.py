#!/usr/bin/env python3
"""Run D19 on the five corrected D18 captures."""
from __future__ import annotations
import fcntl,hashlib,json,pathlib,re,subprocess

HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[2];CAPTURE=pathlib.Path('/workspace/prism-wave6-d18');BINARY=pathlib.Path('/tmp/prism-wave6-d19-build/rank_one_fixed');OUT=pathlib.Path('/workspace/prism-wave6-d19/fixed-solutions')
def sha(path):
 with pathlib.Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def main():
 build=json.loads((HERE/'build-manifest.json').read_text());assert sha(BINARY)==build['binary_sha256'];OUT.mkdir(parents=True,exist_ok=True);cases=[]
 pattern=re.compile(r'D19 arm=(\S+) rep=(\d+) updates=(\d+) products=(\d+) recursive_relative=(\S+) true_relative=(\S+) hit=(\d+) negative=(\d+) min_curvature=(\S+) total_ms=(\S+) raw_norm=(\S+) gated_energy_fraction=(\S+)')
 with open('/tmp/prism_gpu.lock','w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  for index in range(5):
   capture=CAPTURE/f'venice-terminal-{index}';destination=OUT/f'venice-terminal-{index}';destination.mkdir(parents=True,exist_ok=True);command=[str(BINARY),str(capture),str(destination)]
   process=subprocess.run(command,text=True,capture_output=True,check=True,timeout=180);(destination/'stdout.log').write_text(process.stdout);rows=[]
   for m in pattern.finditer(process.stdout):
    arm,rep,updates,products,recursive,true,hit,negative,curvature,ms,norm,fraction=m.groups();rows.append({'index':index,'arm':arm,'rep':int(rep),'updates':int(updates),'products':int(products),'recursive_relative':float(recursive),'true_relative':float(true),'hit':bool(int(hit)),'negative':bool(int(negative)),'min_curvature':float(curvature),'total_ms':float(ms),'raw_norm':float(norm),'gated_energy_fraction':float(fraction)})
   system=re.search(r'SYSTEM .* gated=(\d+) mu_ref=(\S+) top_camera=(\d+) weakest_camera=(\d+) raw_ratio=(\S+) top_energy_fraction=(\S+) ids=([^\n]*)',process.stdout)
   if not system or len(rows)!=6:raise RuntimeError(('D19 parse',index,len(rows),process.stdout[-1000:]))
   case={'index':index,'system':{'gated':int(system[1]),'mu_ref':float(system[2]),'top_camera':int(system[3]),'weakest_camera':int(system[4]),'raw_ratio':float(system[5]),'top_energy_fraction':float(system[6]),'gate_ids':[int(x) for x in system[7].split(',') if x]},'rows':rows,'command':command,'stdout_sha256':sha(destination/'stdout.log'),'capture_manifest_sha256':sha(capture/'capture_manifest.json')};cases.append(case);print('D19_FIXED',index,case['system'],flush=True)
 record={'protocol_sha256':sha(ROOT/'research/eta2_wave6/D19_RANK_ONE_SLOPPY_PRIOR_PROTOCOL.md'),'build_manifest_sha256':sha(HERE/'build-manifest.json'),'d18_capture_manifest_sha256':sha(ROOT/'research/eta2_wave6/d18_geometric_prior/capture-manifest.json'),'binary_sha256':sha(BINARY),'cases':cases};(HERE/'fixed-run-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
if __name__=='__main__':main()
