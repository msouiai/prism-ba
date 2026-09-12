#pragma once
#include <filesystem>
template<class T> void W1Save(const std::string& q,const char* name,const T* device,size_t n){
 std::vector<T> host(n);CUDA_CHECK(cudaMemcpy(host.data(),device,n*sizeof(T),cudaMemcpyDeviceToHost));
 std::ofstream f(q+"/"+name,std::ios::binary);f.write((char*)host.data(),n*sizeof(T));f.close();if(!f)throw std::runtime_error("W1 export failed");
}
void W1LoadState(const char* file,DeviceState& s,int nc,int np,int no){
 std::ifstream f(file,std::ios::binary);char magic[8];uint64_t dims[3];f.read(magic,8);f.read((char*)dims,24);
 if(std::string(magic,8)!="PRISMS01"||dims[0]!=nc||dims[1]!=np||dims[2]!=no)throw std::runtime_error("W1 state header mismatch");
 auto load=[&](double* p,size_t n){std::vector<double> v(n);f.read((char*)v.data(),8*n);if(!f)throw std::runtime_error("W1 short state");CUDA_CHECK(cudaMemcpy(p,v.data(),8*n,cudaMemcpyHostToDevice));};
 load(s.R,9ul*nc);load(s.t,3ul*nc);load(s.X,3ul*np);load(s.intr,3ul*nc);
}
