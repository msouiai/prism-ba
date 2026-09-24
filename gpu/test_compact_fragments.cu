// Fixed-input gate: camera kernels must retain exactly the same arithmetic
// with a permuted fragment store. Includes empty cameras and invalid factors.
#define OCA_CORE_LIBRARY
#include "oca_cuda.cu"
#include <random>
#include <numeric>
#include <cstring>

template<int CD> void CheckCompact(){
  const int nc=7,np=71,no=6*269;
  std::mt19937 rng(71+CD);std::uniform_real_distribution<double> rnd(-1,1);
  std::vector<int> map(no),o2p(no),o2c(no),points(no),off(nc+1);
  std::iota(map.begin(),map.end(),0);std::shuffle(map.begin(),map.end(),rng);
  // Original observation order differs from both traversal orders.
  std::iota(o2c.begin(),o2c.end(),0);std::shuffle(o2c.begin(),o2c.end(),rng);
  for(int o=0;o<no;++o)o2p[o]=map[o2c[o]];
  for(int k=0;k<no;++k)points[k]=rng()%np;
  for(int c=0;c<=nc;++c)off[c]=std::min(c*269,no);
  std::vector<double> gc(3*CD*no),gp(gc.size()),rf(6*np),u(3*np),h(CD*CD*nc),v(CD*nc);
  for(auto& x:gc)x=rnd(rng);
  for(int t=0;t<3*CD;++t)for(int k=0;k<no;++k)gp[t*no+map[k]]=gc[t*no+k];
  for(auto& x:rf)x=rnd(rng);
  for(int p=0;p<np;++p){rf[6*p]=2;rf[6*p+3]=2;rf[6*p+5]=2;if(p%11==0)rf[6*p]=0;}
  for(auto* a:{&u,&h,&v})for(auto& x:*a)x=rnd(rng);
  std::vector<void*> owned;
  auto up=[&](auto& a){using T=typename std::decay_t<decltype(a)>::value_type;T* d;
    CUDA_CHECK(cudaMalloc(&d,a.size()*sizeof(T)));owned.push_back(d);
    CUDA_CHECK(cudaMemcpy(d,a.data(),a.size()*sizeof(T),cudaMemcpyHostToDevice));return d;};
  auto dc=up(gc),dp=up(gp),dr=up(rf),du=up(u),dh=up(h),dv=up(v);
  auto dpt=up(points),dof=up(off),dmap=up(map),do2p=up(o2p),do2c=up(o2c);
  CUDA_CHECK(cudaMemset(dmap,0xff,no*sizeof(int)));
  MFFragmentSlots<<<GridSize(no),256>>>(do2p,do2c,no,dmap);
  std::vector<int> got(no);CUDA_CHECK(cudaMemcpy(got.data(),dmap,no*sizeof(int),cudaMemcpyDeviceToHost));
  if(got!=map)throw std::runtime_error("slot permutation mismatch");
  std::vector<double> zero(CD*CD*nc,0);auto a=up(zero),b=up(zero),x=up(zero),y=up(zero);
  auto equal=[&](double* aa,double* bb,int count,const char* name){
    std::vector<double> av(count),bv(count);
    CUDA_CHECK(cudaMemcpy(av.data(),aa,count*sizeof(double),cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(bv.data(),bb,count*sizeof(double),cudaMemcpyDeviceToHost));
    for(int i=0;i<count;++i)if(!std::isfinite(av[i])||!std::isfinite(bv[i]))throw std::runtime_error("nonfinite output");
    if(std::memcmp(av.data(),bv.data(),count*sizeof(double)))throw std::runtime_error(name);
    std::printf("CD=%d %s bit_exact=1\n",CD,name);
  };
  MFPass2<CD,double><<<nc,256>>>(dc,dpt,dof,du,dh,dv,no,a);
  MFPass2<CD,double><<<nc,256>>>(dp,dpt,dof,du,dh,dv,no,b,dmap);
  equal(a,b,CD*nc,"pass2");
  MFRhsDiagCamera<CD,double><<<nc,256>>>(dc,dpt,dof,dr,du,no,a,x);
  MFRhsDiagCamera<CD,double><<<nc,256>>>(dp,dpt,dof,dr,du,no,b,y,dmap);
  equal(a,b,CD*nc,"rhs");equal(x,y,CD*nc,"diagonal");
  MFRhsDiagCamera<CD,double><<<nc,256>>>(dc,dpt,dof,dr,du,no,a,nullptr);
  MFRhsDiagCamera<CD,double><<<nc,256>>>(dp,dpt,dof,dr,du,no,b,nullptr,dmap);
  equal(a,b,CD*nc,"rhs_only");
  CUDA_CHECK(cudaMemset(a,0,zero.size()*sizeof(double)));CUDA_CHECK(cudaMemset(b,0,zero.size()*sizeof(double)));
  MFBlockSchurCM<CD,double><<<nc,32>>>(dc,dpt,dof,dr,no,a);
  MFBlockSchurCM<CD,double><<<nc,32>>>(dp,dpt,dof,dr,no,b,dmap);
  equal(a,b,CD*CD*nc,"block_schur");
  // Mode 2 streams camera-major fragments in Pass1 and all point-scatter
  // kernels instead of gathering them. Check every changed scatter consumer.
  std::vector<int> cc(no),pc(no),pp(no);
  for(int k=0;k<no;++k){cc[k]=k/269;pc[map[k]]=cc[k];pp[map[k]]=points[k];}
  auto dcc=up(cc),dpc=up(pc),dpp=up(pp);
  auto close=[&](double* aa,double* bb,int count,const char* name){
    std::vector<double> av(count),bv(count);
    CUDA_CHECK(cudaMemcpy(av.data(),aa,count*sizeof(double),cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(bv.data(),bb,count*sizeof(double),cudaMemcpyDeviceToHost));
    double err=0;
    for(int i=0;i<count;++i){
      if(!std::isfinite(av[i])||!std::isfinite(bv[i]))throw std::runtime_error("nonfinite scatter");
      err=std::max(err,std::abs(av[i]-bv[i])/(1+std::abs(av[i])));
    }
    if(err>1e-12)throw std::runtime_error(name);
    std::printf("CD=%d %s error=%.3g\n",CD,name,err);
  };
  std::vector<double> scratch(5*3*np,0);auto ta=up(scratch),tb=up(scratch);
  auto clear=[&](){CUDA_CHECK(cudaMemset(ta,0,scratch.size()*8));CUDA_CHECK(cudaMemset(tb,0,scratch.size()*8));
    CUDA_CHECK(cudaMemset(a,0,zero.size()*8));CUDA_CHECK(cudaMemset(b,0,zero.size()*8));};
  clear();
  MFPass1<CD,double><<<GridSize(no),256>>>(dp,dpc,dpp,dv,no,ta);
  MFPass1<CD,double><<<GridSize(no),256>>>(dc,dcc,dpt,dv,no,tb);
  close(ta,tb,3*np,"camera_store_pass1");
  clear();
  MFPass1Stride<CD,double><<<GridSize(no),256>>>(dp,dpc,dpp,dv,no,3,ta);
  MFPass1Stride<CD,double><<<GridSize(no),256>>>(dc,dcc,dpt,dv,no,3,tb);
  close(ta,tb,3*np,"camera_store_stride");
  std::vector<double> vm(5*CD*nc);for(auto& z:vm)z=rnd(rng);auto dvm=up(vm);
  clear();
  MFPass1Multi<CD,double><<<GridSize(no),256>>>(dp,dpc,dpp,dvm,CD*nc,5,no,ta,3*np);
  MFPass1Multi<CD,double><<<GridSize(no),256>>>(dc,dcc,dpt,dvm,CD*nc,5,no,tb,3*np);
  close(ta,tb,5*3*np,"camera_store_multi");
  clear();
  MFRhsPrime<CD,double><<<GridSize(no),256>>>(dp,dpc,dpp,du,no,a);
  MFRhsPrime<CD,double><<<GridSize(no),256>>>(dc,dcc,dpt,du,no,b);
  close(a,b,CD*nc,"camera_store_rhs_scatter");
  clear();
  MFDiagK<CD,double><<<GridSize(no),256>>>(dp,dpp,dpc,dr,no,a);
  MFDiagK<CD,double><<<GridSize(no),256>>>(dc,dpt,dcc,dr,no,b);
  close(a,b,CD*nc,"camera_store_diag_scatter");
  clear();
  MFDiagK<CD,double,true><<<GridSize(no),256>>>(dp,dpp,dpc,dr,no,a);
  MFDiagK<CD,double,true><<<GridSize(no),256>>>(dc,dpt,dcc,dr,no,b);
  close(a,b,CD*nc,"camera_store_diag_norm");
  clear();
  MFBlockSchur<CD,double><<<GridSize(no),256>>>(dp,dpp,dpc,dr,no,a);
  MFBlockSchur<CD,double><<<GridSize(no),256>>>(dc,dpt,dcc,dr,no,b);
  close(a,b,CD*CD*nc,"camera_store_block_scatter");
  CUDA_CHECK(cudaDeviceSynchronize());for(void* ptr:owned)CUDA_CHECK(cudaFree(ptr));
}
int main(){try{CheckCompact<6>();CheckCompact<9>();}
  catch(const std::exception& e){std::fprintf(stderr,"%s\n",e.what());return 1;}}
