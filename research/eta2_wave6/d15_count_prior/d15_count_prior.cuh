#pragma once
#include <Eigen/Eigenvalues>
#include <chrono>
#include <numeric>

__global__ void D15PriorAdd(int nc,const double*D,const double*x,double*y){
  int c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=nc)return;const double*d=D+81ul*c;const double*v=x+9*c;double*out=y+9*c;
  for(int i=0;i<8;++i){double a=0;for(int j=0;j<8;++j)a+=d[9*i+j]*v[j];out[i]+=a;}
}

struct D15CountPrior{
  int nc,no;bool active=false;double dose=1.;double*delta=nullptr,*block=nullptr;
  std::vector<int> offsets,points,counts,gate;std::vector<double> host_delta,host_block,host_E,host_step;
  long activations=0,tests=0;double build_seconds=0;
  D15CountPrior(int n,const int*d_off,const int*d_points):nc(n){
    const char*e=getenv("OCA_D15_COUNT_PRIOR");dose=e?atof(e):0.;
    if(dose!=1.)throw std::runtime_error("D15 registered native dose is exactly 1");
    offsets.resize(nc+1);CUDA_CHECK(cudaMemcpy(offsets.data(),d_off,(nc+1)*sizeof(int),cudaMemcpyDeviceToHost));no=offsets.back();
    points.resize(no);CUDA_CHECK(cudaMemcpy(points.data(),d_points,no*sizeof(int),cudaMemcpyDeviceToHost));counts.resize(nc);gate.assign(nc,0);
    for(int c=0;c<nc;++c){auto a=points.begin()+offsets[c],b=points.begin()+offsets[c+1];std::vector<int> q(a,b);std::sort(q.begin(),q.end());counts[c]=std::unique(q.begin(),q.end())-q.begin();}
    auto sorted=counts;std::sort(sorted.begin(),sorted.end());double med=sorted[nc/2];if(nc%2==0)med=.5*(med+sorted[nc/2-1]);
    std::vector<int> order(nc);std::iota(order.begin(),order.end(),0);std::sort(order.begin(),order.end(),[&](int a,int b){return std::pair<int,int>(counts[a],a)<std::pair<int,int>(counts[b],b);});
    const int q=(nc+99)/100;for(int k=0;k<q;++k)if(counts[order[k]]<med/4)gate[order[k]]=1;
    CUDA_CHECK(cudaMalloc(&delta,81ul*nc*sizeof(double)));CUDA_CHECK(cudaMalloc(&block,81ul*nc*sizeof(double)));host_delta.resize(81ul*nc);host_block.resize(81ul*nc);host_E.resize(9ul*nc);host_step.resize(9ul*nc);
    std::printf("D15_GATE ncam=%d median=%.17g selected=%d ids=",nc,med,std::accumulate(gate.begin(),gate.end(),0));for(int c=0;c<nc;++c)if(gate[c])std::printf("%d:%d,",c,counts[c]);std::printf("\n");
  }
  ~D15CountPrior(){cudaFree(delta);cudaFree(block);}
  void Reset(){active=false;CUDA_CHECK(cudaMemset(delta,0,81ul*nc*sizeof(double)));}
  struct Stat{double norm=0,ratio=0,gated_fraction=0;};
  Stat Inspect(const double*z,double radius){
    ++tests;CUDA_CHECK(cudaMemcpy(host_step.data(),z,9ul*nc*sizeof(double),cudaMemcpyDeviceToHost));long double all=0,g=0;
    for(int c=0;c<nc;++c)for(int j=0;j<8;++j){long double x=host_step[9ul*c+j];all+=x*x;if(gate[c])g+=x*x;}
    Stat s;s.norm=std::sqrt((double)all);s.ratio=radius>0?s.norm/radius:1.;s.gated_fraction=(double)(g/std::max(all,(long double)1e-300));return s;
  }
  template<class F> void Build(const F*Gc,const int*cspt,const int*coff,const double*Rf,const double*Hcc,const double*E,int nobs,const int*slots=nullptr){
    auto start=std::chrono::steady_clock::now();CUDA_CHECK(cudaMemset(block,0,81ul*nc*sizeof(double)));
    MFBlockSchurCM<9,F><<<nc,32>>>(Gc,cspt,coff,Rf,nobs,block,slots);MFBlockAddHcc<9><<<(nc+255)/256,256>>>(Hcc,nc,block);
    CUDA_CHECK(cudaMemcpy(host_block.data(),block,81ul*nc*sizeof(double),cudaMemcpyDeviceToHost));CUDA_CHECK(cudaMemcpy(host_E.data(),E,9ul*nc*sizeof(double),cudaMemcpyDeviceToHost));
    std::vector<double> maxima;maxima.reserve(nc);std::vector<Eigen::Matrix<double,8,8>> mats(nc);
    for(int c=0;c<nc;++c){Eigen::Matrix<double,8,8>A;for(int i=0;i<8;++i)for(int j=0;j<8;++j)A(i,j)=.5*(host_block[81ul*c+9*i+j]+host_block[81ul*c+9*j+i])*host_E[9*c+i]*host_E[9*c+j];mats[c]=A;
      Eigen::SelfAdjointEigenSolver<Eigen::Matrix<double,8,8>>es(A);if(es.info()!=Eigen::Success)throw std::runtime_error("D15 Schur block eigensolve");if(!gate[c])maxima.push_back(es.eigenvalues()[7]);}
    std::sort(maxima.begin(),maxima.end());double ref=maxima[maxima.size()/2];if(maxima.size()%2==0)ref=.5*(ref+maxima[maxima.size()/2-1]);std::fill(host_delta.begin(),host_delta.end(),0.);
    for(int c=0;c<nc;++c)if(gate[c]){Eigen::SelfAdjointEigenSolver<Eigen::Matrix<double,8,8>>es(mats[c]);Eigen::Array<double,8,1>d=(dose*ref-es.eigenvalues().array()).max(0.);Eigen::Matrix<double,8,8>D=es.eigenvectors()*d.matrix().asDiagonal()*es.eigenvectors().transpose();for(int i=0;i<8;++i)for(int j=0;j<8;++j)host_delta[81ul*c+9*i+j]=D(i,j);}
    CUDA_CHECK(cudaMemcpy(delta,host_delta.data(),81ul*nc*sizeof(double),cudaMemcpyHostToDevice));active=true;++activations;build_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    std::printf("D15_BUILD activation=%ld mu_ref=%.17g dose=%.17g seconds=%.9g\n",activations,ref,dose,build_seconds);
  }
  void Add(const double*x,double*y){if(active)D15PriorAdd<<<(nc+63)/64,64>>>(nc,delta,x,y);}
  void Final(){std::printf("D15_SUMMARY tests=%ld activations=%ld build_seconds=%.9g\n",tests,activations,build_seconds);}
};
