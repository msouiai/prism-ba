#pragma once
#include <Eigen/Eigenvalues>
__global__ void E3Mask(int nc,const int* mask,double* v){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<nc&&mask[i]){v[9*i+6]=0;v[9*i+7]=0;}}
struct E3Local {
 int nc;bool gate;double cap;double* B=nullptr;int* mask=nullptr;
 std::vector<double> block,scale,raw;std::vector<int> gates;
 E3Local(int n,bool g,double c):nc(n),gate(g),cap(c),block(g?81ul*n:0),scale(g?9ul*n:0),raw(c>0?9ul*n:0),gates(g?n:0){
  if(g){CUDA_CHECK(cudaMalloc(&B,81ul*n*8));CUDA_CHECK(cudaMalloc(&mask,n*4));CUDA_CHECK(cudaMemset(mask,0,n*4));}}
 ~E3Local(){if(B)cudaFree(B);if(mask)cudaFree(mask);}
 void Project(double* v){if(gate)E3Mask<<<(nc+255)/256,256>>>(nc,mask,v);}
 void SetGate(const double* E,int outer,int retry){
  CUDA_CHECK(cudaMemcpy(block.data(),B,block.size()*8,cudaMemcpyDeviceToHost));
  CUDA_CHECK(cudaMemcpy(scale.data(),E,scale.size()*8,cudaMemcpyDeviceToHost));
  int touched=0;double minratio=1;
  for(int c=0;c<nc;++c){Eigen::Matrix<double,8,8> a;
   for(int i=0;i<8;++i)for(int j=0;j<8;++j)a(i,j)=.5*(block[81ul*c+9*i+j]+block[81ul*c+9*j+i])*scale[9*c+i]*scale[9*c+j];
   Eigen::SelfAdjointEigenSolver<Eigen::Matrix<double,8,8>> es(a);
   if(es.info()!=Eigen::Success)throw std::runtime_error("E3 block eigen failure");
   auto v=es.eigenvectors().col(0);double f=v[6]*v[6],tz=v[5]*v[5];
   gates[c]=es.eigenvalues()[0]<.001*es.eigenvalues()[7] && f+tz>.5 && f>.05 && tz>.05;
   if(gates[c]){++touched;minratio=std::min(minratio,es.eigenvalues()[0]/std::max(1e-300,es.eigenvalues()[7]));}
  }
  CUDA_CHECK(cudaMemcpy(mask,gates.data(),nc*4,cudaMemcpyHostToDevice));
  printf("E3_GATE o=%d retry=%d touched=%d ncam=%d minratio=%.17g ids=",outer,retry,touched,nc,minratio);
  for(int i=0;i<nc;++i)if(gates[i])printf("%d,",i);printf("\n");
 }
 double Cap(double* z,double R,int outer,int retry){
  CUDA_CHECK(cudaMemcpy(raw.data(),z,raw.size()*8,cudaMemcpyDeviceToHost));
  std::vector<double> norms(nc);double before2=0;
  for(int c=0;c<nc;++c){double n=0;for(int j=0;j<9;++j)n+=raw[9*c+j]*raw[9*c+j];norms[c]=sqrt(n);before2+=n;}
  auto sorted=norms;std::sort(sorted.begin(),sorted.end());double med=sorted[nc/2];if(nc%2==0)med=.5*(med+sorted[nc/2-1]);
  int touched=0;double after2=0;
  for(int c=0;c<nc;++c){double a=std::min(1.,cap*med/std::max(1e-300,norms[c]));
   if(a<1){++touched;for(int j=0;j<9;++j)raw[9*c+j]*=a;}
   for(int j=0;j<9;++j)after2+=raw[9*c+j]*raw[9*c+j];}
  if(touched)CUDA_CHECK(cudaMemcpy(z,raw.data(),raw.size()*8,cudaMemcpyHostToDevice));
  double after=sqrt(after2);printf("E2_CAP o=%d retry=%d touched=%d ncam=%d raw=%.17g capped=%.17g radius=%.17g median=%.17g global_scale=%.17g\n",outer,retry,touched,nc,sqrt(before2),after,R,med,std::min(1.,R/std::max(1e-300,after)));
  return after;
 }
};
