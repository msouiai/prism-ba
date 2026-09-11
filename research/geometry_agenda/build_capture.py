#!/usr/bin/env python3
"""Generate read-only T1 candidate captures from verified frozen Eta2 source."""
import hashlib
import json
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent
PKG = ROOT.parent/'eta2_champion'
OUT = ROOT/'build'
OUT.mkdir(exist_ok=True)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest = json.loads((PKG/'source_manifest.json').read_text())
source = PKG/'source/prism_eta2.cu'
assert sha(source) == manifest['source_sha256']
headers = OUT/'headers'
headers.mkdir(exist_ok=True)
for name, expected in manifest['headers_sha256'].items():
    assert sha(PKG/'source/headers'/name) == expected
    shutil.copy2(PKG/'source/headers'/name, headers/name)
s = source.read_text()

def replace(old, new):
    global s
    assert s.count(old) == 1, (old[:100], s.count(old))
    s = s.replace(old, new)

replace('  const char* model_capture=getenv("OCA_MODEL_CAPTURE");', '''  const char* model_capture=getenv("OCA_MODEL_CAPTURE");
  const char* agenda_capture=getenv("OCA_AGENDA_CAPTURE");
  const int agenda_outers=getenv("OCA_AGENDA_OUTERS")?atoi(getenv("OCA_AGENDA_OUTERS")):12;
  if(agenda_capture && (!classical_lm || CD!=9 || shared_intr || mf_fp32 || rk || agenda_outers<=0))
    throw std::runtime_error("agenda captures require frozen unshared FP64 L2 LM engine");
  double* agenda_work=nullptr;
  long agenda_id=0;
''')
# Allocate after camera-space sizes are established, using the existing n_c.
replace('    auto KvS=[&](const Scalar* vin,Scalar* vout){', '''    if(agenda_capture && !agenda_work)CUDA_CHECK(cudaMalloc(&agenda_work,(size_t)n_c*sizeof(double)));
    auto KvS=[&](const Scalar* vin,Scalar* vout){''')
replace('    auto Lift=[&](const Scalar* x_scaled){', '''    double agenda_true_residual=-1,agenda_recurrence_residual=-1;
    auto AgendaCapture=[&](const Scalar* step,double trial,const char* kind,int shift,int depth){
      if(!agenda_capture || k>=agenda_outers)return;
      const auto start=now();
      const std::string stem=std::string(agenda_capture)+"-"+std::to_string(agenda_id++);
      PrismModelCapture(stem,p,s,step,nullptr,k,cost,trial,lam_cam,tau_eff);
      std::ofstream info(stem+".meta.json");info.precision(17);
      info << "{\\"outer\\":" << k << ",\\"retry\\":" << retries
           << ",\\"kind\\":\\"" << kind << "\\",\\"shift\\":" << shift << ",\\"depth\\":" << depth
           << ",\\"raw_reduced_true_residual\\":" << agenda_true_residual
           << ",\\"raw_reduced_recurrence_residual\\":" << agenda_recurrence_residual
           << ",\\"export_seconds\\":" << std::chrono::duration<double>(now()-start).count() << "}\\n";
    };
    auto Lift=[&](const Scalar* x_scaled){''')
replace('      if(model_capture){\n        const char* tag=nullptr;', '''      AgendaCapture(dfull,c,"full",sh,ck);
      if(model_capture){
        const char* tag=nullptr;''')
replace('          ++backtrack_evals;\n          if(backtrack_policy)', '''          AgendaCapture(dfull,c,"backtrack",backtrack_sh,backtrack_ck);
          ++backtrack_evals;
          if(backtrack_policy)''')
replace('            DoRetract(dfull,s_new);candidate=ComputeCost(p,s_new,rk,rk_a2);', '''            DoRetract(dfull,s_new);candidate=ComputeCost(p,s_new,rk,rk_a2);
            AgendaCapture(dfull,candidate,"point_safeguard",backtrack_sh,backtrack_ck);''')
needle='''    if(classical_lm){
      if(model_capture)std::printf("MODEL_LINEAR'''
assert s.count(needle) == 1
s = s.replace(needle, '''    if(classical_lm){
      if(agenda_capture && k<agenda_outers){
        const auto begin=now();
        KvS(xs[0],agenda_work);
        cublasDaxpy(blas,n_c,&shifts[0],xs[0],1,agenda_work,1);
        const double negative=-1.;cublasDaxpy(blas,n_c,&negative,bprime,1,agenda_work,1);
        double residual=0,rhs=0;cublasDnrm2(blas,n_c,agenda_work,1,&residual);cublasDnrm2(blas,n_c,bprime,1,&rhs);
        agenda_true_residual=residual/std::max(1e-300,rhs);
        agenda_recurrence_residual=std::sqrt(rr)/std::max(1e-300,(double)nb);
        std::printf("AGENDA_LINEAR outer=%d retry=%d true_rel=%.17g recurrence_rel=%.17g tolerance=%.17g cg=%d seconds=%.9g\\n",k,retries,agenda_true_residual,agenda_recurrence_residual,(double)eta,cg_broke?cg_it+1:maxck,std::chrono::duration<double>(now()-begin).count());
      }
      if(model_capture)std::printf("MODEL_LINEAR''')
# One per-call allocation; no changed arithmetic with the flag absent.
replace('  if(point_safeguard_mode)std::printf("POINT_SAFE summary', '''  cudaFree(agenda_work);
  if(point_safeguard_mode)std::printf("POINT_SAFE summary''')
unit = OUT/'agenda_capture.cu'
unit.write_text(s)
binary = OUT/'prism-agenda-capture'
cmd = ['nvcc', '-O3', '-DNDEBUG', '-std=c++17', '-arch=sm_89', '-I/usr/include/eigen3',
       '-I'+str(headers), str(unit), '-o', str(binary), '-lcublas', '-lcusolver']
print('Building diagnostic capture binary', flush=True)
with (OUT/'capture-build.log').open('w') as f:
    subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=True)
(OUT/'capture-manifest.json').write_text(json.dumps({'frozen_manifest': manifest, 'command': cmd,
    'source_sha256': sha(unit), 'binary_sha256': sha(binary), 'builder_sha256': sha(pathlib.Path(__file__))}, indent=2)+'\n')
print(binary, flush=True)
