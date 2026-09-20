#!/usr/bin/env python3
import pathlib,shutil,subprocess,json
from build_tr_candidate import REPO,sha
ROOT=pathlib.Path('/workspace/prism-tr-cg-stop/guarded')
def main():
 ROOT.mkdir();base=pathlib.Path('/workspace/prism-tr-cg-stop/projection');shutil.copytree(base/'headers',ROOT/'headers');s=(base/'source.cu').read_text()
 s=s.replace('  std::unique_ptr<PrismCgProjection> cg_projection;', '  std::unique_ptr<PrismCameraTR> legacy_tr;\n  std::unique_ptr<PrismCgProjection> cg_projection;',1)
 s=s.replace('cg_projection=std::make_unique<PrismCgProjection>(n_c);','{cg_projection=std::make_unique<PrismCgProjection>(n_c);legacy_tr=std::make_unique<PrismCameraTR>(n_c);}',1)
 s=s.replace('    if(cg_projection)cg_projection->Reset();','    if(cg_projection){cg_projection->Reset();legacy_tr->Reset();}',1)
 marker='        tr->Add(tr->work,-1,0,bprime,blas,KvS);';assert s.count(marker)==1;s=s.replace(marker,marker+'\n        if(legacy_tr){legacy_tr->radius=tr->radius;legacy_tr->Select(tr->work,tr->entries.back(),blas);}')
 marker='      if(tr->best_prediction>0)Score(tr->best,tr->best_sh,tr->best_depth);';assert s.count(marker)==1
 s=s.replace(marker,'''      if(legacy_tr && !tr_reuse && legacy_tr->best_prediction>0){
        Score(legacy_tr->best,legacy_tr->best_sh,legacy_tr->best_depth);
        if(tr->best_sh==-2)Score(tr->best,tr->best_sh,tr->best_depth);
        if(have){tr->best_sh=best_sh;tr->best_depth=best_ck;}
      }else if(tr->best_prediction>0)Score(tr->best,tr->best_sh,tr->best_depth);''')
 h=ROOT/'headers/tr_recurrence_score.inc';txt=h.read_text();marker='tr->entries.push_back(e);tr->Select(saved,e,blas);';assert txt.count(marker)==1;txt=txt.replace(marker,marker+'\n if(legacy_tr){legacy_tr->radius=tr->radius;legacy_tr->Select(saved,e,blas);}')
 h.write_text(txt)
 h=ROOT/'headers/cg_tr_projection_step.inc';txt=h.read_text().replace('cg_projection && (cg_it+1)%16==0 && tr->radius>0 && cg_projection->Solve(blas,bprime,tr->radius)','cg_projection && (cg_it+1)%16==0 && tr->radius>0 && tr->best_norm>=.8*tr->radius && cg_projection->Solve(blas,bprime,tr->radius) && cg_projection->multiplier>shifts[0]')
 txt=txt.replace(' if(!verified && getenv("OCA_CG_STOP_TRACE"))throw std::runtime_error("CG projected model audit failed");',' // A failed model check discards the projection; continue the original CG solve.');h.write_text(txt)
 p=ROOT/'source.cu';p.write_text(s);cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(ROOT/'headers'),str(p),'-o',str(ROOT/'prism-tr'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 (ROOT/'stop-manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(p),binary_sha256=sha(ROOT/'prism-tr'),base_source_sha256=sha(base/'source.cu'),headers_sha256={p.name:sha(p) for p in (ROOT/'headers').iterdir()}),indent=2));print(ROOT/'prism-tr')
if __name__=='__main__':main()
