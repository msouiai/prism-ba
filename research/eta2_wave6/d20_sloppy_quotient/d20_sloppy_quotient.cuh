#pragma once
#include <Eigen/Eigenvalues>
#include <chrono>

struct D20SloppyQuotient {
  int nc;
  double *block=nullptr;
  std::vector<double> host_block,host_E,host_step;
  long tests=0,block_builds=0,projections=0;
  double block_seconds=0.;

  explicit D20SloppyQuotient(int n):nc(n) {
    CUDA_CHECK(cudaMalloc(&block,81ul*nc*sizeof(double)));
    host_block.resize(81ul*nc);host_E.resize(9ul*nc);host_step.resize(9ul*nc);
  }
  ~D20SloppyQuotient(){cudaFree(block);}

  struct Inspection {
    double norm=0.,ratio=0.,top_fraction=0.;
    int top=-1;
  };

  Inspection Inspect(const double*z,double radius){
    ++tests;
    CUDA_CHECK(cudaMemcpy(host_step.data(),z,9ul*nc*sizeof(double),cudaMemcpyDeviceToHost));
    long double all=0.;std::vector<long double> energy(nc,0.);
    for(int c=0;c<nc;++c)for(int j=0;j<9;++j){
      const long double x=host_step[9ul*c+j];all+=x*x;
      if(j<8)energy[c]+=x*x;
    }
    int top=0;for(int c=1;c<nc;++c)if(energy[c]>energy[top])top=c;
    Inspection s;s.norm=std::sqrt((double)all);s.ratio=radius>0?s.norm/radius:1.;s.top=top;
    s.top_fraction=(double)(energy[top]/std::max(all,(long double)1e-300));return s;
  }

  struct Projection {
    bool trigger=false;int weakest=-1;double weakest_value=0.;
    double removed_fraction=0.,post_norm=0.;
  };

  template<class F>
  Projection BuildAndProject(const F*Gc,const int*cspt,const int*coff,
      const double*Rf,const double*Hcc,const double*E,int nobs,double*z,
      int top,const int*slots=nullptr){
    auto start=std::chrono::steady_clock::now();++block_builds;
    CUDA_CHECK(cudaMemset(block,0,81ul*nc*sizeof(double)));
    MFBlockSchurCM<9,F><<<nc,32>>>(Gc,cspt,coff,Rf,nobs,block,slots);
    MFBlockAddHcc<9><<<(nc+255)/256,256>>>(Hcc,nc,block);
    CUDA_CHECK(cudaMemcpy(host_block.data(),block,81ul*nc*sizeof(double),cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(host_E.data(),E,9ul*nc*sizeof(double),cudaMemcpyDeviceToHost));

    int weakest=0;double weakest_value=0.;Eigen::Matrix<double,8,1> top_q;
    for(int c=0;c<nc;++c){
      Eigen::Matrix<double,8,8>A;
      for(int i=0;i<8;++i)for(int j=0;j<8;++j)
        A(i,j)=.5*(host_block[81ul*c+9*i+j]+host_block[81ul*c+9*j+i])
               *host_E[9ul*c+i]*host_E[9ul*c+j];
      Eigen::SelfAdjointEigenSolver<Eigen::Matrix<double,8,8>>es(A);
      if(es.info()!=Eigen::Success)throw std::runtime_error("D20 Schur block eigensolve");
      const double value=es.eigenvalues()[0];
      if(c==0||value<weakest_value){weakest=c;weakest_value=value;}
      if(c==top)top_q=es.eigenvectors().col(0);
    }

    Projection out;out.weakest=weakest;out.weakest_value=weakest_value;
    long double before=0.;for(double x:host_step)before+=(long double)x*x;
    if(top==weakest){
      double coefficient=0.;for(int j=0;j<8;++j)coefficient+=top_q[j]*host_step[9ul*top+j];
      for(int j=0;j<8;++j)host_step[9ul*top+j]-=coefficient*top_q[j];
      CUDA_CHECK(cudaMemcpy(z+9ul*top,host_step.data()+9ul*top,9*sizeof(double),cudaMemcpyHostToDevice));
      long double after=0.;for(double x:host_step)after+=(long double)x*x;
      out.trigger=true;out.removed_fraction=(double)((before-after)/std::max(before,(long double)1e-300));
      out.post_norm=std::sqrt((double)after);++projections;
    } else out.post_norm=std::sqrt((double)before);
    block_seconds+=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    return out;
  }

  void Final(){
    std::printf("D20_SUMMARY tests=%ld block_builds=%ld projections=%ld block_seconds=%.9g\n",
                tests,block_builds,projections,block_seconds);
  }
};

