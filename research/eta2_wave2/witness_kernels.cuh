#pragma once
inline void WaveLoad(const std::string& dir,const char* name,double* device,size_t n){
  std::vector<double> v(n);std::ifstream f(dir+"/"+name,std::ios::binary);
  f.read(reinterpret_cast<char*>(v.data()),8*n);if(!f||f.peek()!=EOF)throw std::runtime_error("wave witness input size mismatch");
  CUDA_CHECK(cudaMemcpy(device,v.data(),8*n,cudaMemcpyHostToDevice));
}
inline void WaveSave(const std::string& file,const double* device,size_t n){
  std::vector<double> v(n);CUDA_CHECK(cudaMemcpy(v.data(),device,8*n,cudaMemcpyDeviceToHost));
  std::ofstream f(file,std::ios::binary);f.write(reinterpret_cast<char*>(v.data()),8*n);f.close();if(!f)throw std::runtime_error("wave witness export failed");
}
__global__ void WaveFullJ(const int* ci,const int* pi,const int* slot,const double* jc,
 const double* jp,const double* d,int nc,int no,double* y){
 int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=no)return;
 int c=ci[o],j=pi[o],a=slot[o];
 for(int r=0;r<2;++r){double v=0;for(int k=0;k<9;++k)v+=jc[18ul*a+9*r+k]*d[9*c+k];
  for(int k=0;k<3;++k)v+=jp[6ul*o+3*r+k]*d[9*nc+3*j+k];y[2ul*o+r]=v;}
}
__global__ void WaveSecondResidual(const int* ci,const int* pi,const double* uv,
 const double* R,const double* t,const double* X,const double* f,const double* k1,const double* k2,
 const double* r0,const double* jd,int no,double h,double* r2){
 int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=no)return;int c=ci[o],j=pi[o];
 const double* q=R+9*c;const double* x=X+3*j;double gx[12],gy[12],rx,ry;
 BalResidualGrad12(q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],t[3*c],t[3*c+1],t[3*c+2],
  x[0],x[1],x[2],f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],gx,gy,&rx,&ry);
 r2[2ul*o]=2*(rx-r0[2ul*o]-h*jd[2ul*o])/(h*h);
 r2[2ul*o+1]=2*(ry-r0[2ul*o+1]-h*jd[2ul*o+1])/(h*h);
}
__global__ void WaveMetric(const double* d,const double* E,const double* diag,int nc,int np,double* out){
 int a=blockIdx.x*blockDim.x+threadIdx.x;
 if(a<9*nc)out[a]=d[a]/E[a];
 if(a<3*np){int j=a/3;double mean=(diag[3*j]+diag[3*j+1]+diag[3*j+2])/3;
  double dp=fmax(diag[a],.001*fmax(mean,1e-32));out[9*nc+a]=d[9*nc+a]*sqrt(dp);}
}
