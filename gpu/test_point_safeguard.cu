#define OCA_CORE_LIBRARY
#include "oca_cuda.cu"
#include <random>
int main(int argc,char** argv){
  const double keep_scale=argc==2?std::atof(argv[1]):(argc==4?std::atof(argv[3]):0);
  DeviceProblem p{};DeviceState old{},full{};
  std::vector<double> R,t,X,I,step,uv;std::vector<int> ci,pi;
  if(argc>=3){
    auto b=LoadBal(argv[1]);p.ncam=b.ncam;p.npt=b.npt;p.nobs=b.nobs;ci=b.cam_idx;pi=b.pt_idx;uv=b.uv;
    std::ifstream in(std::string(argv[2])+".state",std::ios::binary);char magic[8];uint64_t dims[3];in.read(magic,8);in.read((char*)dims,24);
    if(std::string(magic,8)!="PRISMS01" || dims[0]!=p.ncam || dims[1]!=p.npt || dims[2]!=p.nobs)throw std::runtime_error("bad fixture");
    auto read=[&](std::vector<double>& v,size_t n){v.resize(n);in.read((char*)v.data(),n*8);if(!in)throw std::runtime_error("short fixture");};
    read(R,9ul*p.ncam);read(t,3ul*p.ncam);read(X,3ul*p.npt);read(I,3ul*p.ncam);
    std::ifstream ds(std::string(argv[2])+".step",std::ios::binary);step.resize(9ul*p.ncam+3ul*p.npt);ds.read((char*)step.data(),step.size()*8);if(!ds)throw std::runtime_error("short step");
  }else{
    p.ncam=3;p.npt=65;R.assign(27,0);t.assign(9,0);I.assign(9,0);X.resize(195);step.assign(27+195,0);
    std::mt19937 rng(714);std::normal_distribution<double> normal;
    for(int c=0;c<3;++c){R[9*c]=R[9*c+4]=R[9*c+8]=1;I[c]=500;I[3+c]=.003;t[3*c]=.1*c;step[9*c+3]=.03;}
    for(int j=0;j<65;++j){X[3*j]=normal(rng);X[3*j+1]=normal(rng);X[3*j+2]=4;
      for(int k=0;k<3;++k)step[27+3*j+k]=.2*normal(rng);
      int degree=j==64?0:1+(j*17)%100;
      for(int a=0;a<degree;++a){ci.push_back(a%3);pi.push_back(j);uv.push_back(50*normal(rng));uv.push_back(50*normal(rng));}
    }
    // Exact ties, moved-point pole, old-point pole, both nonfinite, and unseen point.
    for(int k=0;k<3;++k)step[27+k]=0;
    step[27+3+2]=-4;X[3*2+2]=0;step[27+3*2+2]=4;
    X[3*3+2]=0;step[27+3*3+2]=0;
    step[27+3*4]=std::numeric_limits<double>::infinity();
    p.nobs=ci.size();
  }
  std::vector<void*> alloc;auto up=[&](const auto& v,auto** d){CUDA_CHECK(cudaMalloc(d,v.size()*sizeof(v[0])));alloc.push_back(*d);CUDA_CHECK(cudaMemcpy(*d,v.data(),v.size()*sizeof(v[0]),cudaMemcpyHostToDevice));};
  up(ci,&p.cam_idx);up(pi,&p.pt_idx);up(uv,&p.uv);up(R,&old.R);up(t,&old.t);up(X,&old.X);up(I,&old.intr);
  up(R,&full.R);up(t,&full.t);up(X,&full.X);up(I,&full.intr);old.ncam_for_intr=full.ncam_for_intr=p.ncam;
  double* d;up(step,&d);BuildPointObsCSR(p,pi.data(),p.npt,p.nobs);
  RetractDof9(p,old,d,full);
  std::vector<double> newR(R.size()),newt(t.size()),newX(X.size()),newI(I.size()),selected(step.size());
  auto get=[&](auto& v,const auto* ptr){CUDA_CHECK(cudaMemcpy(v.data(),ptr,v.size()*sizeof(v[0]),cudaMemcpyDeviceToHost));};
  get(newR,full.R);get(newt,full.t);get(newX,full.X);get(newI,full.intr);
  std::vector<double> keepX=X;for(size_t j=0;j<X.size();++j)if(keep_scale!=0)keepX[j]+=keep_scale*step[9ul*p.ncam+j];
  std::vector<long double> keep(p.npt,0),move(p.npt,0);
  for(int o=0;o<p.nobs;++o)for(int m=0;m<2;++m){int c=ci[o],j=pi[o];auto& x=m?newX:keepX;long double q[3];
    for(int a=0;a<3;++a){q[a]=newt[3*c+a];for(int b=0;b<3;++b)q[a]+=(long double)newR[9*c+3*a+b]*x[3*j+b];}
    long double u=-q[0]/q[2],v=-q[1]/q[2],r=u*u+v*v;
    long double scale=newI[c]*(1+(long double)newI[p.ncam+c]*r+(long double)newI[2*p.ncam+c]*r*r);
    long double a=scale*u-uv[2*o],b=scale*v-uv[2*o+1],cost=(a*a+b*b)/2;
    (m?move:keep)[j]+=std::isfinite(cost)?cost:std::numeric_limits<long double>::infinity();
  }
  unsigned long long expected=0;long double expected_cost=0;
  for(int j=0;j<p.npt;++j){bool freeze=keep[j]<move[j];expected+=freeze;expected_cost+=freeze?keep[j]:move[j];}
  unsigned long long actual;{PrismPointSafeguard selector;actual=selector.Choose(p,old,full,d,keep_scale);}
  get(selected,d);if(expected!=actual)throw std::runtime_error("CPU track decision count mismatch");
  for(size_t i=0;i<step.size();++i){bool freeze=i>=9ul*p.ncam && keep[(i-9ul*p.ncam)/3]<move[(i-9ul*p.ncam)/3];double want=freeze?(keep_scale==0?0:keep_scale*step[i]):step[i];if(want!=selected[i])throw std::runtime_error("CPU selected step mismatch");}
  double error=0,cost=0;if(std::isfinite(expected_cost)){
    RetractDof9(p,old,d,full);cost=ComputeCost(p,full);error=std::abs(cost-(double)expected_cost)/std::max(1.,std::abs((double)expected_cost));if(error>1e-8)throw std::runtime_error("CPU cost mismatch");
  }
  cudaFree(p.point_obs_offsets);cudaFree(p.point_obs_list);for(void* a:alloc)cudaFree(a);
  std::printf("PASS points=%d observations=%d frozen=%llu cpu_cost=%.17g gpu_cost=%.17g error=%.9g\n",p.npt,p.nobs,actual,(double)expected_cost,cost,error);
}
