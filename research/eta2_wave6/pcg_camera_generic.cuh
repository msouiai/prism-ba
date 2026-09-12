#pragma once

__global__ void PcgNormalize(int nc,const double*H,const double*E,double sig,double*B){int c=blockIdx.x*blockDim.x+threadIdx.x;if(c<nc)for(int i=0;i<9;++i)for(int j=0;j<9;++j)B[81ul*c+9*i+j]=H[81ul*c+9*i+j]*E[9*c+i]*E[9*c+j]+(i==j?sig:0);}
__global__ void PcgDiagDrift(int nc,const double*H,const double*E,double sig,const double*old,int*bad){int c=blockIdx.x*blockDim.x+threadIdx.x;if(c<nc)for(int i=0;i<9;++i){double d=H[81ul*c+10*i]*E[9*c+i]*E[9*c+i]+sig,o=old[9*c+i];if(!(d>.5*o&&d<2*o))atomicExch(bad,1);}}
__global__ void PcgSaveDiag(int nc,const double*B,double*d){int c=blockIdx.x*blockDim.x+threadIdx.x;if(c<nc)for(int i=0;i<9;++i)d[9*c+i]=B[81ul*c+10*i];}
__global__ void PcgReferenceDiag(int nc,const double*H,const double*E,double sig,double*d){int c=blockIdx.x*blockDim.x+threadIdx.x;if(c<nc)for(int i=0;i<9;++i)d[9*c+i]=H[81ul*c+10*i]*E[9*c+i]*E[9*c+i]+sig;}

struct PrismPcg{
 int nc,n,last_outer=-1,last_depth=0;double*B,*z,*tmp,*diag;int*bad;double rz=0;bool reuse,schur;
 PrismPcg(int cams):nc(cams),n(9*cams),reuse(getenv("OCA_PCG_REUSE")!=nullptr),schur(getenv("OCA_PCG_SCHUR")!=nullptr){CUDA_CHECK(cudaMalloc(&B,81ul*nc*8));for(double**p:{&z,&tmp,&diag})CUDA_CHECK(cudaMalloc(p,n*8ul));CUDA_CHECK(cudaMalloc(&bad,4));}
 ~PrismPcg(){for(double*p:{B,z,tmp,diag})cudaFree(p);cudaFree(bad);}
 template<class F>
 void Prepare(const double*H,const double*E,double sig,int outer,int retry,const F*W,const int*pt,const int*off,const double*R,int no){bool rebuild=!reuse||last_outer<0||retry||last_depth>64;int drift=0;if(!rebuild){CUDA_CHECK(cudaMemset(bad,0,4));PcgDiagDrift<<<(nc+255)/256,256>>>(nc,H,E,sig,diag,bad);CUDA_CHECK(cudaMemcpy(&drift,bad,4,cudaMemcpyDeviceToHost));rebuild=drift;}
 if(rebuild){if(schur){CUDA_CHECK(cudaMemset(B,0,81ul*nc*8));MFBlockSchurCM<9,F><<<nc,32>>>(W,pt,off,R,no,B);MFBlockAddHcc<9><<<(nc+255)/256,256>>>(H,nc,B);}PcgNormalize<<<(nc+255)/256,256>>>(nc,schur?B:H,E,sig,B);PcgReferenceDiag<<<(nc+255)/256,256>>>(nc,H,E,sig,diag);MFBlockChol<9><<<(nc+255)/256,256>>>(B,nc,1e-10,nullptr);last_outer=outer;}
 printf("PCG_PREP o=%d rebuild=%d drift=%d previous_depth=%d\n",outer,(int)rebuild,drift,last_depth);
 }
 void Apply(const double*r){MFBlockSolve<9><<<(nc+255)/256,256>>>(B,r,nc,0,tmp);MFBlockSolve<9><<<(nc+255)/256,256>>>(B,tmp,nc,1,z);}
};
