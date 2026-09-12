#pragma once
#include "geodesic_analytic.cuh"
__global__ void GeoGradient(const int* ci,const int* pi,const double* uv,const double* R,
 const double* t,const double* X,const double* f,const double* k1,const double* k2,
 const double* rsecond,int no,double* gc,double* gp){
 int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=no)return;int c=ci[o],j=pi[o];
 const double* q=R+9*c;const double* x=X+3*j;double gx[12],gy[12],rx,ry;
 BalResidualGrad12(q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],t[3*c],t[3*c+1],t[3*c+2],
  x[0],x[1],x[2],f[c],k1[c],k2[c],uv[2*o],uv[2*o+1],gx,gy,&rx,&ry);
 for(int a=0;a<8;++a)atomicAdd(gc+9*c+a,gx[a]*rsecond[2ul*o]+gy[a]*rsecond[2ul*o+1]);
 for(int a=0;a<3;++a)atomicAdd(gp+3*j+a,gx[9+a]*rsecond[2ul*o]+gy[9+a]*rsecond[2ul*o+1]);
}
__global__ void GeoRhs(const double* gc,const double* corr,const double* E,int n,double* rhs){
 int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)rhs[i]=E[i]*(gc[i]-corr[i]);
}
__global__ void GeoMetric(const double* d,const double* E,const double* diag,int nc,int np,double* out){
 int a=blockIdx.x*blockDim.x+threadIdx.x;
 if(a<9*nc)out[a]=d[a]/E[a];
 if(a<3*np){int j=a/3;double mean=(diag[3*j]+diag[3*j+1]+diag[3*j+2])/3;
  out[9*nc+a]=d[9*nc+a]*sqrt(fmax(diag[a],.001*fmax(mean,1e-32)));}
}
struct GeoNative {
 bool audit_written=false;
 int nc,np,no,nc9,np3,n;
 double *second,*gc,*gp,*u,*corr,*rhs,*x,*r,*v,*Ap,*tac,*d2,*candidate,*first,*metric;
 std::vector<double*> allocations;
 double* New(size_t n){double* p=nullptr;CUDA_CHECK(cudaMalloc(&p,8*n));allocations.push_back(p);return p;}
 GeoNative(int c,int p,int o):nc(c),np(p),no(o),nc9(9*c),np3(3*p),n(nc9+np3){
  second=New(2ul*o);gc=New(nc9);gp=New(np3);u=New(np3);corr=New(nc9);rhs=New(nc9);
  x=New(nc9);r=New(nc9);v=New(nc9);Ap=New(nc9);tac=New(np3);
  d2=New(n);candidate=New(n);first=New(n);metric=New(n);
 }
 ~GeoNative(){for(auto p:allocations)cudaFree(p);}
};
template<class T> void GeoDump(const std::string& prefix,const char* name,const T* device,size_t count){
 std::vector<T> host(count);CUDA_CHECK(cudaMemcpy(host.data(),device,count*sizeof(T),cudaMemcpyDeviceToHost));
 FILE* f=fopen((prefix+"."+name).c_str(),"wb");if(!f)throw std::runtime_error("geodesic audit write failed");
 if(fwrite(host.data(),sizeof(T),count,f)!=count){fclose(f);throw std::runtime_error("geodesic audit short write");}fclose(f);
}
