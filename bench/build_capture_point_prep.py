import pathlib,shutil,json,subprocess,argparse
ap=argparse.ArgumentParser();ap.add_argument('--output',type=pathlib.Path,default=pathlib.Path('/workspace/prism-tr-point-prep/capture-build-v2'));args=ap.parse_args();root=args.output;root.mkdir();base=pathlib.Path('/workspace/prism-tr-safeguard/factored');shutil.copytree(base/'headers',root/'headers');s=(base/'source.cu').read_text();anchor='    // b\' = b_c - H_cp V^-1 b_p';assert s.count(anchor)==1
s=s.replace(anchor,'''    if(getenv("PRISM_PREP_CAPTURE") && k==0 && retries==0){
      std::string dir=getenv("PRISM_PREP_CAPTURE");
      auto dump=[&](const char* name,const void* ptr,size_t bytes){std::vector<char> h(bytes);CUDA_CHECK(cudaMemcpy(h.data(),ptr,bytes,cudaMemcpyDeviceToHost));FILE*f=fopen((dir+"/"+name).c_str(),"wb");if(!f||fwrite(h.data(),1,bytes,f)!=bytes)throw std::runtime_error("prep capture");fclose(f);};
      FILE*f=fopen((dir+"/dims").c_str(),"w");fprintf(f,"%d %d %d %.17g\\n",ncam,npt,nobs,(double)tau_eff);fclose(f);
      dump("Bo",mf_fp32?Bo32:Bo,6ul*nobs*sizeof(float));dump("poff",p.point_obs_offsets,(npt+1ul)*sizeof(int));dump("plist",p.point_obs_list,nobs*sizeof(int));dump("Cdiag",Cdiag,3ul*npt*sizeof(double));dump("R0",R0f,6ul*npt*sizeof(double));dump("R",Rf,6ul*npt*sizeof(double));dump("bp",bp,3ul*npt*sizeof(double));
    }
'''+anchor)
(root/'source.cu').write_text(s);cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(root/'headers'),str(root/'source.cu'),'-o',str(root/'prism-tr'),'-lcublas','-lcusolver'];
with (root/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
