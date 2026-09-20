#pragma once
// Bounded, explicit research export. Never runs without OCA_MODEL_CAPTURE.
inline void PrismModelCapture(const std::string& stem, const DeviceProblem& p,
    const DeviceState& s, const double* step, const double* point_diag,
    int outer, double cost, double trial, double lambda, double tau,
    double pap=0, double pp=0) {
  auto write = [&](const std::string& path, bool state) {
    FILE* f=std::fopen(path.c_str(),"wbx");
    if(!f)throw std::runtime_error("model capture refuses existing output");
    auto bytes=[&](const void* x,size_t n){if(std::fwrite(x,1,n,f)!=n)throw std::runtime_error("model capture write failed");};
    auto device=[&](const double* x,size_t n){std::vector<double> h(n);CUDA_CHECK(cudaMemcpy(h.data(),x,n*sizeof(double),cudaMemcpyDeviceToHost));bytes(h.data(),n*sizeof(double));};
    if(state){bytes("PRISMS01",8);uint64_t dims[3]={(uint64_t)p.ncam,(uint64_t)p.npt,(uint64_t)p.nobs};bytes(dims,sizeof(dims));device(s.R,9ul*p.ncam);device(s.t,3ul*p.ncam);device(s.X,3ul*p.npt);device(INTR_F(p,s),p.ncam);device(INTR_K1(p,s),p.ncam);device(INTR_K2(p,s),p.ncam);}
    else device(step,9ul*p.ncam+3ul*p.npt);
    if(std::fclose(f))throw std::runtime_error("model capture close failed");
  };
  write(stem+".state",true);write(stem+".step",false);
  if(point_diag){std::vector<double> h(3ul*p.npt);CUDA_CHECK(cudaMemcpy(h.data(),point_diag,h.size()*sizeof(double),cudaMemcpyDeviceToHost));FILE*f=std::fopen((stem+".diag").c_str(),"wbx");if(!f||std::fwrite(h.data(),sizeof(double),h.size(),f)!=h.size())throw std::runtime_error("capture diagonal");std::fclose(f);}
  FILE*f=std::fopen((stem+".json").c_str(),"wbx");if(!f)throw std::runtime_error("model capture metadata");
  std::fprintf(f,"{\"outer\":%d,\"cost\":%.17g,\"trial\":%.17g,\"lambda\":%.17g,\"tau\":%.17g,\"pap\":%.17g,\"pp\":%.17g}\n",outer,cost,std::isfinite(trial)?trial:-1,lambda,tau,pap,pp);std::fclose(f);
}
