#!/usr/bin/env python3
"""Freeze a self-contained opt-in candidate and its audited experiment records."""
import pathlib,shutil,json,subprocess,argparse
from build_tr_candidate import sha
ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=pathlib.Path,required=True);ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args();src=a.candidate;out=a.output;out.mkdir();m=json.loads((src/'stop-manifest.json').read_text());assert sha(src/'source.cu')==m['source_sha256'];assert sha(src/'prism-tr')==m['binary_sha256'];assert all(sha(src/'headers'/k)==v for k,v in m['headers_sha256'].items());shutil.copytree(src/'headers',out/'headers')
for name in ['source.cu','prism-tr','stop-manifest.json']:shutil.copy2(src/name,out/name)
(out/'build.sh').write_text('#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nnvcc -O3 -DNDEBUG -std=c++17 -arch=sm_89 -I/usr/include/eigen3 -Iheaders source.cu -o prism-tr-rebuilt -lcublas -lcusolver\n');(out/'build.sh').chmod(0o755)
base=pathlib.Path('/workspace/prism-tr-point-prep');records=out/'results';records.mkdir()
for p in base.rglob('*.json'):
 if out in p.parents:continue
 dest=records/p.relative_to(base);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
repo=pathlib.Path(__file__).resolve().parents[1];(out/'bench').mkdir();shutil.copy2(repo/'bench/run_point_prep_package.py',out/'run.py');
for name in ['audit_prism_state.py','cached_benchmark_input.py','point_prep_comparison.py','point_prep_study.py','tr_cg_study.py','cg_stop_large.py','profile_iterations.py','novelty_ablation.py','build_tr_candidate.py','point_prep_bench.cu','test_point_prep.cu']:
 shutil.copy2(repo/'bench'/name,out/'bench'/name)
shutil.copy2(repo/'docs/point_preparation_results.md',out/'RESULTS.md');cfg=json.loads(pathlib.Path('/workspace/prism-tr-safeguard/recommended_candidate.json').read_text());cfg['binary_sha256']=m['binary_sha256'];cfg['command'][4]='./prism-tr';cfg['command'][cfg['command'].index('--state_out')+1]='example.state';cfg['recommendation']='Opt-in experimental candidate; see RESULTS.md for scope and counterexamples.';cfg['flags'].pop('OCA_FP32_PRODUCTS',None);cfg['flags'].pop('OCA_PAIR_SAFE',None);(out/'recommended_candidate.json').write_text(json.dumps(cfg,indent=2))
(out/'README.md').write_text('Self-contained PRISM opt-in research snapshot. CUDA 12.8, Eigen3, cuBLAS/cuSOLVER, sm_89. Run ./build.sh to rebuild without overwriting the tested binary. The recommended_candidate.json records the tested flags and example command; adjust input and output paths. Frozen source includes the existing solver and headers; no earlier workspace build is needed. Benchmarks exclude input loading and retain established solver setup differences. Original-double endpoint audits are required. Results are a small bounded panel, not a universal superiority claim.\n')
(out/'files.json').write_text(json.dumps({str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()},indent=2));subprocess.run(['tar','-czf',str(out)+'.tar.gz','-C',str(out.parent),out.name],check=True);print(out)
