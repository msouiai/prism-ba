#!/usr/bin/env python3
import pathlib,subprocess,json,shutil
from build_tr_candidate import REPO,sha
ROOT=pathlib.Path('/workspace/prism-tr-cg-stop/build')
def main():
 subprocess.run(['python3',str(REPO/'bench/build_tr_mixed_storage.py'),'--source-only','--output',str(ROOT)],check=True)
 p=ROOT/'source.cu';s=p.read_text()
 helper='''
static void prism_cg_save(const std::string& path,const void* device,size_t bytes){
 FILE* f=fopen(path.c_str(),"wb");if(!f)throw std::runtime_error("CG capture open failed");
 std::vector<unsigned char> h(std::min(bytes,(size_t)8*1024*1024));
 for(size_t pos=0;pos<bytes;pos+=h.size()){
  size_t n=std::min(h.size(),bytes-pos);CUDA_CHECK(cudaMemcpy(h.data(),(const char*)device+pos,n,cudaMemcpyDeviceToHost));
  if(fwrite(h.data(),1,n,f)!=n)throw std::runtime_error("CG capture write failed");
 }
 if(fclose(f))throw std::runtime_error("CG capture close failed");
}
'''
 marker='template <int CD, class HT>\n__global__ void MFAssemble('
 assert s.count(marker)==1;s=s.replace(marker,helper+'\n'+marker)
 capture='''
    if(camera_tr && getenv("OCA_CG_CAPTURE") && k==(getenv("OCA_CG_CAPTURE_OUTER")?atoi(getenv("OCA_CG_CAPTURE_OUTER")):6)){
      std::string dir=getenv("OCA_CG_CAPTURE");
      prism_cg_save(dir+"/W",Gp,(size_t)nobs*CD*3*sizeof(Fragment));
      prism_cg_save(dir+"/U",Hcc,(size_t)ncam*CD*CD*8);
      prism_cg_save(dir+"/R",Rf,(size_t)npt*6*8);
      prism_cg_save(dir+"/E",E,(size_t)n_c*8);
      prism_cg_save(dir+"/b",bprime,(size_t)n_c*8);
      prism_cg_save(dir+"/cams",fragment_cams,(size_t)nobs*4);
      prism_cg_save(dir+"/points",fragment_points,(size_t)nobs*4);
      prism_cg_save(dir+"/offsets",p.mf_coff,(size_t)(ncam+1)*4);
      FILE* f=fopen((dir+"/dimensions.txt").c_str(),"w");if(!f)throw std::runtime_error("capture metadata");
      fprintf(f,"%d %d %d %d %.17g %.17g %.17g\\n",CD,ncam,npt,nobs,(double)shifts[0],tr->radius,(double)eta);fclose(f);
    }
'''
 marker='    int maxck = ckpts.empty()?64:*std::max_element(ckpts.begin(),ckpts.end());'
 assert s.count(marker)==1;s=s.replace(marker,capture+marker)
 marker='      if(progressive && !progressive_checked && std::isfinite(zeta[grid_down]) &&'
 assert s.count(marker)==1;s=s.replace(marker,'#include "tr_cg_stop.inc"\n'+marker)
 p.write_text(s);shutil.copy2(REPO/'gpu/tr_cg_stop.inc',ROOT/'headers/tr_cg_stop.inc')
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I'+str(ROOT/'headers'),str(p),'-o',str(ROOT/'prism-tr'),'-lcublas','-lcusolver']
 with (ROOT/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 (ROOT/'stop-manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(p),binary_sha256=sha(ROOT/'prism-tr'),header_sha256=sha(ROOT/'headers/tr_cg_stop.inc')),indent=2));print(ROOT/'prism-tr')
if __name__=='__main__':main()
