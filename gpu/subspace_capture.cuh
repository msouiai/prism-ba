#pragma once
// Exact research state/direction export. Exclusive creates preserve old evidence.
inline void PrismCaptureSubspace(const char* prefix,long call,int outer,
    const DeviceProblem& p,const DeviceState& s,const double* step,double cost,
    double full_cost,const PrismSubspaceModel::Result& m){
 if(!prefix || !(call==1 || call==8 || call==16))return;
 std::string stem=std::string(prefix)+"-"+std::to_string(call);
 auto write=[&](const std::string& path,bool state){
  FILE* f=std::fopen(path.c_str(),"wbx");if(!f)throw std::runtime_error("capture refuses existing/unwritable output");
  auto bytes=[&](const void* x,size_t n){if(std::fwrite(x,1,n,f)!=n)throw std::runtime_error("capture write failed");};
  auto device=[&](const double* d,size_t n){std::vector<double> h(n);CUDA_CHECK(cudaMemcpy(h.data(),d,n*sizeof(double),cudaMemcpyDeviceToHost));bytes(h.data(),n*sizeof(double));};
  if(state){bytes("PRISMS01",8);uint64_t dims[3]={(uint64_t)p.ncam,(uint64_t)p.npt,(uint64_t)p.nobs};bytes(dims,sizeof(dims));
   device(s.R,9ul*p.ncam);device(s.t,3ul*p.ncam);device(s.X,3ul*p.npt);
   device(INTR_F(p,s),p.ncam);device(INTR_K1(p,s),p.ncam);device(INTR_K2(p,s),p.ncam);
  }else device(step,9ul*p.ncam+3ul*p.npt);
  if(std::fclose(f))throw std::runtime_error("capture close failed");
 };
 write(stem+".state",true);write(stem+".step",false);
 FILE* f=std::fopen((stem+".json").c_str(),"wbx");if(!f)throw std::runtime_error("capture metadata exists/unwritable");
 std::fprintf(f,"{\"call\":%ld,\"outer\":%d,\"cost\":%.17g,\"full_cost\":%.17g,\"gc\":%.17g,\"gp\":%.17g,\"cc\":%.17g,\"cp\":%.17g,\"pp\":%.17g}\n",call,outer,cost,full_cost,m.gc,m.gp,m.cc,m.cp,m.pp);
 if(std::fclose(f))throw std::runtime_error("capture metadata close failed");
}
