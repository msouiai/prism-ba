// Cold workspace/construction follow-up. Matrices are already resident.
#define PRISM_FIXED_LIBRARY
#include "fixed.cu"
#include <chrono>
int main(int argc,char**argv){
  if(argc!=3)return 2;System current(argv[1]),previous(argv[2]);
  if(current.n!=previous.n)return 3;
  cublasHandle_t h;PrismCoarse::blas(cublasCreate(&h));
  for(int rank:{0,8,16}){
    CK(cudaDeviceSynchronize());auto start=std::chrono::steady_clock::now();
    PrismCoarse*coarse=rank?new PrismCoarse(current.n,rank):nullptr;
    previous.Prepare();auto prior=Solve(previous,h,coarse,true);
    current.Prepare();if(coarse)coarse->Prepare(h,[&](const double*a,double*b){current.Apply(a,b);});
    auto r=Solve(current,h,coarse,true);delete coarse;
    CK(cudaDeviceSynchronize());
    double ms=1000*std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    printf("COARSE_COLD rank=%d pair_ms=%.9g prior_hit=%d current_hit=%d prior_iterations=%d current_iterations=%d\n",rank,ms,prior.hit,r.hit,prior.iterations,r.iterations);
  }
  cublasDestroy(h);
}
