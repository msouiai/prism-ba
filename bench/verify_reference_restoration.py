#!/usr/bin/env python3
"""Post-study correctness diagnostic; never include these timings in selection."""
import json, pathlib, shutil, subprocess
import reference_forcing_study as study

ROOT = study.ROOT
OUT = ROOT / 'restoration-build'

def main():
    OUT.mkdir(exist_ok=False)
    parent = ROOT / 'build-v2'
    shutil.copytree(parent / 'headers', OUT / 'headers')
    source = (parent / 'source.cu').read_text()
    start = '      auto ref_start=std::chrono::steady_clock::now();'
    before = r'''
      auto snapshot=[](const void* ptr,size_t bytes){
        std::vector<unsigned char> value(bytes);
        CUDA_CHECK(cudaMemcpy(value.data(),ptr,bytes,cudaMemcpyDeviceToHost));return value;
      };
      auto saved_rf=snapshot(Rf,(size_t)npt*6*sizeof(Scalar));
      auto saved_ok=snapshot(okf,(size_t)npt*sizeof(int));
      auto saved_rhs=snapshot(bprime,(size_t)n_c*sizeof(Scalar));
      auto saved_metric=snapshot(E,(size_t)n_c*sizeof(Scalar));
'''
    end = '      rrf.probe_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-ref_start).count();'
    after = r'''
      if(saved_rf!=snapshot(Rf,saved_rf.size()) || saved_ok!=snapshot(okf,saved_ok.size()) ||
         saved_rhs!=snapshot(bprime,saved_rhs.size()) || saved_metric!=snapshot(E,saved_metric.size()))
        throw std::runtime_error("reference restoration byte check failed");
      std::printf("REFERENCE_RESTORATION outer=%d byte_equal=1\n",k);
'''
    assert source.count(start)==source.count(end)==1
    source=source.replace(start,before+start).replace(end,end+after)
    (OUT/'source.cu').write_text(source)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3',
         '-I'+str(OUT/'headers'),str(OUT/'source.cu'),'-o',str(OUT/'prism-tr'),'-lcublas','-lcusolver']
    with (OUT/'build.log').open('w') as f:
        subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    study.put('restoration-build/manifest.json',dict(command=cmd,parent_binary_sha256=study.p.sha(study.BIN),
        source_sha256=study.p.sha(OUT/'source.cu'),binary_sha256=study.p.sha(OUT/'prism-tr'),
        scope='Post-study correctness only. Host snapshots perturb timings; excluded from all speed claims.'))
    rows=[]
    for rep in range(3):
        r=study.run(f'diagnostic-restoration-dubrovnik-356-{rep}','dubrovnik-356','probe',lam=10,
                    cap=6,iters=45,binary=OUT/'prism-tr',verify=True)
        text=(ROOT/'runs'/r['name']/'stdout.log').read_text()
        count=text.count('REFERENCE_RESTORATION ')
        assert count>=23 and 'byte_equal=0' not in text
        rows.append(dict(name=r['name'],checks=count,summary=r['reference_summary']))
        study.put('restoration-verification.json',dict(passed=True,runs=rows,
            checked_buffers=['Rf','okf','bprime','E'],timings_excluded=True))
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
