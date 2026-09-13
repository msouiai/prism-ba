#pragma once
#include <numeric>

__global__ void D16ProjectKernel(int nc,const int*gate,double*x){
  int c=blockIdx.x*blockDim.x+threadIdx.x;
  if(c<nc&&gate[c])for(int j=0;j<8;++j)x[9*c+j]=0.;
}

struct D16CountProject{
  int nc,no;int*d_gate=nullptr;std::vector<int>offsets,points,counts,gate;
  std::vector<double>host_step;long tests=0,projections=0;
  D16CountProject(int n,const int*d_off,const int*d_points):nc(n){
    offsets.resize(nc+1);CUDA_CHECK(cudaMemcpy(offsets.data(),d_off,(nc+1)*sizeof(int),cudaMemcpyDeviceToHost));no=offsets.back();
    points.resize(no);CUDA_CHECK(cudaMemcpy(points.data(),d_points,no*sizeof(int),cudaMemcpyDeviceToHost));counts.resize(nc);gate.assign(nc,0);
    for(int c=0;c<nc;++c){auto a=points.begin()+offsets[c],b=points.begin()+offsets[c+1];std::vector<int>q(a,b);std::sort(q.begin(),q.end());counts[c]=std::unique(q.begin(),q.end())-q.begin();}
    auto sorted=counts;std::sort(sorted.begin(),sorted.end());double med=sorted[nc/2];if(nc%2==0)med=.5*(med+sorted[nc/2-1]);
    std::vector<int>order(nc);std::iota(order.begin(),order.end(),0);std::sort(order.begin(),order.end(),[&](int a,int b){return std::pair<int,int>(counts[a],a)<std::pair<int,int>(counts[b],b);});
    const int q=(nc+99)/100;for(int k=0;k<q;++k)if(counts[order[k]]<med/4)gate[order[k]]=1;
    CUDA_CHECK(cudaMalloc(&d_gate,nc*sizeof(int)));CUDA_CHECK(cudaMemcpy(d_gate,gate.data(),nc*sizeof(int),cudaMemcpyHostToDevice));host_step.resize(9ul*nc);
    std::printf("D16_GATE ncam=%d median=%.17g selected=%d ids=",nc,med,std::accumulate(gate.begin(),gate.end(),0));for(int c=0;c<nc;++c)if(gate[c])std::printf("%d:%d,",c,counts[c]);std::printf("\n");
  }
  ~D16CountProject(){cudaFree(d_gate);}
  struct Stat{double norm=0,ratio=0,gated_fraction=0;};
  Stat Inspect(const double*z,double radius){
    ++tests;CUDA_CHECK(cudaMemcpy(host_step.data(),z,9ul*nc*sizeof(double),cudaMemcpyDeviceToHost));long double all=0,g=0;
    for(int c=0;c<nc;++c)for(int j=0;j<8;++j){long double x=host_step[9ul*c+j];all+=x*x;if(gate[c])g+=x*x;}
    Stat s;s.norm=std::sqrt((double)all);s.ratio=radius>0?s.norm/radius:1.;s.gated_fraction=(double)(g/std::max(all,(long double)1e-300));return s;
  }
  void Project(double*z){D16ProjectKernel<<<(nc+63)/64,64>>>(nc,d_gate,z);++projections;}
  void Final(){std::printf("D16_SUMMARY tests=%ld projections=%ld\n",tests,projections);}
};
