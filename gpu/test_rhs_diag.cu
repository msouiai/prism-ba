// Standalone numerical and timing gate for the fused camera-major kernel.
#define OCA_CORE_LIBRARY
#include "oca_cuda.cu"
#include <random>

template<int CD, class HT> void CheckRhsDiag(int nc, int np, int per_camera) {
  const int no=(nc-1)*per_camera; // include an empty camera
  std::mt19937 rng(42);
  std::uniform_real_distribution<double> random(-1,1);
  std::vector<HT> g((size_t)3*CD*no);
  for(auto& v:g) v=(HT)random(rng);
  std::vector<int> points(no),cams(no),off(nc+1);
  for(int k=0;k<no;++k){points[k]=rng()%np;cams[k]=k/per_camera;}
  for(int c=0;c<=nc;++c) off[c]=std::min(c*per_camera,no);
  std::vector<double> r(6*np),u(3*np);
  for(auto& v:u) v=random(rng);
  for(int p=0;p<np;++p){
    r[6*p]=1+std::abs(random(rng)); r[6*p+1]=random(rng);
    r[6*p+2]=random(rng); r[6*p+3]=1+std::abs(random(rng));
    r[6*p+4]=random(rng); r[6*p+5]=1+std::abs(random(rng));
    if(p%17==0) r[6*p]=0; // invalid factors: RHS still exists, diagonal skips
  }
  HT* dg; int *dp,*dc,*dof; double *dr,*du,*oldr,*oldd,*newr,*newd;
  auto upload=[](auto& vec,auto** ptr){
    CUDA_CHECK(cudaMalloc(ptr,vec.size()*sizeof(vec[0])));
    CUDA_CHECK(cudaMemcpy(*ptr,vec.data(),vec.size()*sizeof(vec[0]),cudaMemcpyHostToDevice));
  };
  upload(g,&dg);upload(points,&dp);upload(cams,&dc);upload(off,&dof);upload(r,&dr);upload(u,&du);
  const size_t bytes=CD*nc*sizeof(double);
  for(auto p:{&oldr,&oldd,&newr,&newd}) CUDA_CHECK(cudaMalloc(p,bytes));
  auto legacy=[&](){
    CUDA_CHECK(cudaMemset(oldr,0,bytes));CUDA_CHECK(cudaMemset(oldd,0,bytes));
    MFRhsPrime<CD,HT><<<GridSize(no),256>>>(dg,dc,dp,du,no,oldr);
    MFDiagK<CD,HT><<<GridSize(no),256>>>(dg,dp,dc,dr,no,oldd);
  };
  auto fused=[&](){MFRhsDiagCamera<CD,HT><<<nc,256>>>(dg,dp,dof,dr,du,no,newr,newd);};
  legacy();fused();CUDA_CHECK(cudaDeviceSynchronize());
  std::vector<double> a(CD*nc),b(CD*nc);
  double max_error=0;
  for(int which=0;which<2;++which){
    CUDA_CHECK(cudaMemcpy(a.data(),which?oldd:oldr,bytes,cudaMemcpyDeviceToHost));
    CUDA_CHECK(cudaMemcpy(b.data(),which?newd:newr,bytes,cudaMemcpyDeviceToHost));
    for(int i=0;i<CD*nc;++i){
      double err=std::abs(a[i]-b[i])/(1+std::abs(a[i]));
      max_error=std::max(max_error,err);
      if(!std::isfinite(b[i]) || err>1e-10) throw std::runtime_error("RHS/diagonal mismatch");
    }
  }
  // Exercise the RHS-only path used when diagonal scaling is not needed.
  MFRhsDiagCamera<CD,HT><<<nc,256>>>(dg,dp,dof,dr,du,no,newr,nullptr);
  CUDA_CHECK(cudaMemcpy(b.data(),newr,bytes,cudaMemcpyDeviceToHost));
  CUDA_CHECK(cudaMemcpy(a.data(),oldr,bytes,cudaMemcpyDeviceToHost));
  for(int i=0;i<CD*nc;++i)
    if(std::abs(a[i]-b[i])>1e-10*(1+std::abs(a[i]))) throw std::runtime_error("RHS-only mismatch");
  auto norm=[&](){
    CUDA_CHECK(cudaMemset(newd,0,bytes));
    MFDiagK<CD,HT,true><<<GridSize(no),256>>>(dg,dp,dc,dr,no,newd);
  };
  norm();
  CUDA_CHECK(cudaMemcpy(a.data(),oldd,bytes,cudaMemcpyDeviceToHost));
  CUDA_CHECK(cudaMemcpy(b.data(),newd,bytes,cudaMemcpyDeviceToHost));
  for(int i=0;i<CD*nc;++i)
    if(!std::isfinite(b[i]) || std::abs(a[i]-b[i])>1e-10*(1+std::abs(a[i])))
      throw std::runtime_error("Forward-norm diagonal mismatch");
  auto time=[&](auto&& fn){
    cudaEvent_t start,end;CUDA_CHECK(cudaEventCreate(&start));CUDA_CHECK(cudaEventCreate(&end));
    fn(); CUDA_CHECK(cudaEventRecord(start));
    for(int rep=0;rep<20;++rep) fn();
    CUDA_CHECK(cudaEventRecord(end));CUDA_CHECK(cudaEventSynchronize(end));
    float ms;CUDA_CHECK(cudaEventElapsedTime(&ms,start,end));
    cudaEventDestroy(start);cudaEventDestroy(end);return ms/20;
  };
  auto legacy_diag=[&](){
    CUDA_CHECK(cudaMemset(oldd,0,bytes));
    MFDiagK<CD,HT><<<GridSize(no),256>>>(dg,dp,dc,dr,no,oldd);
  };
  float old_ms=time(legacy),new_ms=time(fused),diag_ms=time(legacy_diag),norm_ms=time(norm);
  std::printf("CD=%d storage=%zu cams=%d obs=%d error=%.3g legacy_ms=%.3f fused_ms=%.3f speedup=%.2f diag_ms=%.3f norm_ms=%.3f\n",
              CD,sizeof(HT),nc,no,max_error,old_ms,new_ms,old_ms/new_ms,diag_ms,norm_ms);
  cudaFree(dg);cudaFree(dp);cudaFree(dc);cudaFree(dof);cudaFree(dr);cudaFree(du);
  cudaFree(oldr);cudaFree(oldd);cudaFree(newr);cudaFree(newd);
}
int main(){
  try {
    CheckRhsDiag<6,double>(53,4099,257);
    CheckRhsDiag<9,float>(53,4099,257);
    CheckRhsDiag<9,double>(53,4099,257);
    CheckRhsDiag<9,double>(512,65537,2048);
  } catch(const std::exception& e){std::fprintf(stderr,"%s\n",e.what());return 1;}
}
