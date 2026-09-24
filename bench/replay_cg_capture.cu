#define main prism_saved_main
#include "source.cu"
#undef main
#include "projected_radius.h"
template<class T>T* cg_load(const std::string& name,size_t n){
 T* d=nullptr;CUDA_CHECK(cudaMalloc(&d,n*sizeof(T)));FILE*f=fopen(name.c_str(),"rb");if(!f)throw std::runtime_error("replay open");
 std::vector<T> h(std::min(n,(size_t)1024*1024));for(size_t i=0;i<n;i+=h.size()){size_t k=std::min(h.size(),n-i);if(fread(h.data(),sizeof(T),k,f)!=k)throw std::runtime_error("replay read");CUDA_CHECK(cudaMemcpy(d+i,h.data(),k*sizeof(T),cudaMemcpyHostToDevice));}fclose(f);return d;
}
int main(){
 std::string dir="/workspace/prism-tr-cg-stop/capture/";
 FILE*f=fopen((dir+"dimensions.txt").c_str(),"r");int cd,nc,np,no;double sigma,radius,eta;fscanf(f,"%d %d %d %d %lf %lf %lf",&cd,&nc,&np,&no,&sigma,&radius,&eta);fclose(f);int n=9*nc;
 float*W=cg_load<float>(dir+"W",(size_t)27*no);double*U=cg_load<double>(dir+"U",81ul*nc),*R=cg_load<double>(dir+"R",6ul*np),*E=cg_load<double>(dir+"E",n),*b=cg_load<double>(dir+"b",n);
 int*cam=cg_load<int>(dir+"cams",no),*pt=cg_load<int>(dir+"points",no),*off=cg_load<int>(dir+"offsets",nc+1);
 double *v,*t,*u,*y;CUDA_CHECK(cudaMalloc(&v,n*8));CUDA_CHECK(cudaMalloc(&y,n*8));CUDA_CHECK(cudaMalloc(&t,3ul*np*8));CUDA_CHECK(cudaMalloc(&u,3ul*np*8));cublasHandle_t h;cublasCreate(&h);
 auto dot=[&](double*a,double*c){double q;cublasDdot(h,n,a,1,c,1,&q);return q;};double nb=std::sqrt(dot(b,b));
 for(int depth:{16,32,64,128}){
  double*x=cg_load<double>(dir+"projected-"+std::to_string(depth)+".x",n);double*expected=cg_load<double>(dir+"projected-"+std::to_string(depth)+".sx",n);
  CUDA_CHECK(cudaMemcpy(v,x,n*8,cudaMemcpyDeviceToDevice));MFScaleVec<<<GridSize(n),256>>>(v,E,n);CUDA_CHECK(cudaMemset(t,0,3ul*np*8));MFPass1<9,float><<<GridSize(no),256>>>(W,cam,pt,v,no,t);MFVinvApply<<<GridSize(np),256>>>(R,t,np,u);MFPass2<9,float><<<nc,256>>>(W,pt,off,u,U,v,no,y);MFScaleVec<<<GridSize(n),256>>>(y,E,n);
  double bx=dot(b,x),xsx=dot(x,y),minus=-1.;cublasDaxpy(h,n,&minus,y,1,expected,1);double err=std::sqrt(dot(expected,expected))/nb;cublasDaxpy(h,n,&minus,b,1,y,1);double gn=std::sqrt(dot(y,y)),pred=bx-.5*xsx,fw=xsx-bx+radius*gn;
  printf("REPLAY depth=%d prediction=%.17g fw_gap=%.17g ratio=%.17g operator_error=%.17g\n",depth,pred,fw,fw/pred,err);if(!(err<1e-7))return 2;cudaFree(x);cudaFree(expected);
 }

 auto apply=[&](const double*in,double*out){
  CUDA_CHECK(cudaMemcpy(v,in,n*8,cudaMemcpyDeviceToDevice));MFScaleVec<<<GridSize(n),256>>>(v,E,n);CUDA_CHECK(cudaMemset(t,0,3ul*np*8));MFPass1<9,float><<<GridSize(no),256>>>(W,cam,pt,v,no,t);MFVinvApply<<<GridSize(np),256>>>(R,t,np,u);MFPass2<9,float><<<nc,256>>>(W,pt,off,u,U,v,no,out);MFScaleVec<<<GridSize(n),256>>>(out,E,n);
 };
 prism_recycle::Basis basis(n,128);basis.Reset(h,b);
 double*sol;CUDA_CHECK(cudaMalloc(&sol,n*8));
 for(int depth:{16,32,64,128}){
  basis.Grow(h,apply,depth);int m=basis.m;Eigen::MatrixXd H(m,m);Eigen::VectorXd rhs=Eigen::VectorXd::Zero(m);rhs[0]=nb;
  for(int i=0;i<m;++i)for(int j=0;j<m;++j)H(i,j)=basis.H[i*128+j];
  PrismProjectedRadius model(H,rhs);auto result=model.Solve(radius);
  CUDA_CHECK(cudaMemcpy(basis.coeff,result.y.data(),m*8,cudaMemcpyHostToDevice));const double one=1.,zero=0.,minus=-1.;
  cublasDgemv(h,CUBLAS_OP_N,n,m,&one,basis.q,n,basis.coeff,1,&zero,sol,1);
  apply(sol,y);double bx=dot(b,sol),xsx=dot(sol,y),pred=bx-.5*xsx;
  cublasDaxpy(h,n,&minus,b,1,y,1);double fw=xsx-bx+radius*std::sqrt(dot(y,y));
  printf("BASIS_TR depth=%d dimension=%d prediction=%.17g fw_gap=%.17g ratio=%.17g lambda=%.17g norm=%.17g\n",depth,m,pred,fw,fw/pred,result.lambda,std::sqrt(dot(sol,sol)));fflush(stdout);
 }
 return 0;
}
