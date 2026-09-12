#pragma once

// Explicit formation of E (Hcc - W V^-1 W^T) E + sigma I from the exact
// numerical ingredients consumed by the matrix-free Eta2 operator.  The
// fragments are SoA and `o2slot` maps original observation ids into that
// storage order.  One block owns each camera diagonal or camera-pair edge, so
// formation needs no cross-block atomics.

template <int CD>
__global__ void W5DenseInit(const Scalar* __restrict__ Hcc,
                            const Scalar* __restrict__ E, Scalar sigma,
                            int ncam, int nc, Scalar* __restrict__ S) {
  const int q = blockIdx.x * blockDim.x + threadIdx.x;
  const int total = ncam * CD * CD;
  if (q >= total) return;
  const int c = q / (CD * CD), ij = q % (CD * CD);
  const int i = ij / CD, j = ij % CD;
  const int row = CD*c+i, col = CD*c+j;
  Scalar v = E[row] * Hcc[(size_t)c*CD*CD + i*CD+j] * E[col];
  if (i == j) v += sigma;
  S[row + (size_t)col*nc] = v;
}

template <int CD, class HT>
__global__ void W5DenseDiag(const HT* __restrict__ W,
                            const int* __restrict__ cspt,
                            const int* __restrict__ coff,
                            const Scalar* __restrict__ Rf,
                            const Scalar* __restrict__ E,
                            int nobs, int nc, Scalar* __restrict__ S) {
  const int c = blockIdx.x, tid = threadIdx.x;
  if (c*CD >= nc) return;
  __shared__ Scalar Ws[CD*3], Us[CD*3];
  Scalar acc = 0;
  for (int o = coff[c]; o < coff[c+1]; ++o) {
    if (tid < CD*3) Ws[tid] = (Scalar)W[(size_t)tid*nobs + o];
    __syncthreads();
    if (tid < CD) {
      Scalar in[3] = {Ws[3*tid], Ws[3*tid+1], Ws[3*tid+2]}, out[3];
      const Scalar* R = Rf + 6*cspt[o];
      const Scalar y0=in[0]/R[0];
      const Scalar y1=(in[1]-R[1]*y0)/R[3];
      const Scalar y2=(in[2]-R[2]*y0-R[4]*y1)/R[5];
      out[2]=y2/R[5];out[1]=(y1-R[4]*out[2])/R[3];
      out[0]=(y0-R[1]*out[1]-R[2]*out[2])/R[0];
      Us[3*tid]=out[0];Us[3*tid+1]=out[1];Us[3*tid+2]=out[2];
    }
    __syncthreads();
    if (tid < CD*CD) {
      const int i=tid/CD,j=tid%CD;
      acc += Us[3*i]*Ws[3*j] + Us[3*i+1]*Ws[3*j+1] + Us[3*i+2]*Ws[3*j+2];
    }
    __syncthreads();
  }
  if (tid < CD*CD) {
    const int i=tid/CD,j=tid%CD,row=CD*c+i,col=CD*c+j;
    S[row+(size_t)col*nc] -= E[row]*acc*E[col];
  }
}

template <int CD, class HT>
__global__ void W5DenseEdges(const HT* __restrict__ W,
                             const int* __restrict__ pt_idx,
                             const int* __restrict__ o2slot,
                             const int* __restrict__ edge_ci,
                             const int* __restrict__ edge_cj,
                             const int* __restrict__ edge_offsets,
                             const int* __restrict__ edge_od,
                             const int* __restrict__ edge_oe,
                             const Scalar* __restrict__ Rf,
                             const Scalar* __restrict__ E,
                             int nedges, int nobs, int nc,
                             Scalar* __restrict__ S) {
  const int edge=blockIdx.x,tid=threadIdx.x;
  if(edge>=nedges)return;
  __shared__ Scalar Wd[CD*3],We[CD*3],Ud[CD*3];
  Scalar acc=0;
  for(int q=edge_offsets[edge];q<edge_offsets[edge+1];++q){
    const int od=edge_od[q],oe=edge_oe[q],sd=o2slot[od],se=o2slot[oe];
    if(tid<CD*3){Wd[tid]=(Scalar)W[(size_t)tid*nobs+sd];We[tid]=(Scalar)W[(size_t)tid*nobs+se];}
    __syncthreads();
    if(tid<CD){
      Scalar in[3]={Wd[3*tid],Wd[3*tid+1],Wd[3*tid+2]},out[3];
      const Scalar* R=Rf+6*pt_idx[od];
      const Scalar y0=in[0]/R[0];
      const Scalar y1=(in[1]-R[1]*y0)/R[3];
      const Scalar y2=(in[2]-R[2]*y0-R[4]*y1)/R[5];
      out[2]=y2/R[5];out[1]=(y1-R[4]*out[2])/R[3];out[0]=(y0-R[1]*out[1]-R[2]*out[2])/R[0];
      Ud[3*tid]=out[0];Ud[3*tid+1]=out[1];Ud[3*tid+2]=out[2];
    }
    __syncthreads();
    if(tid<CD*CD){const int i=tid/CD,j=tid%CD;
      acc+=Ud[3*i]*We[3*j]+Ud[3*i+1]*We[3*j+1]+Ud[3*i+2]*We[3*j+2];}
    __syncthreads();
  }
  if(tid<CD*CD){
    const int i=tid/CD,j=tid%CD,ci=edge_ci[edge],cj=edge_cj[edge];
    const int ri=CD*ci+i,cjcol=CD*cj+j;
    const Scalar v=-E[ri]*acc*E[cjcol];
    S[ri+(size_t)cjcol*nc]=v;
    S[cjcol+(size_t)ri*nc]=v;
  }
}

// Slow, transparent reference formation: one CTA per point, every ordered
// observation pair, and atomic accumulation into the dense matrix.  This is
// deliberately the literal Schur sum and is used as the correctness oracle
// before trusting the edge-CSR optimization above.
template <int CD, class HT>
__global__ void W5DensePoints(const HT* __restrict__ W,
                              const int* __restrict__ cam_idx,
                              const int* __restrict__ poff,
                              const int* __restrict__ plist,
                              const int* __restrict__ o2slot,
                              const Scalar* __restrict__ Rf,
                              const Scalar* __restrict__ E,
                              int npt,int nobs,int nc,Scalar* __restrict__ S){
  const int p=blockIdx.x,tid=threadIdx.x;if(p>=npt)return;
  __shared__ Scalar Wd[CD*3],We[CD*3],Ud[CD*3];
  for(int di=poff[p];di<poff[p+1];++di){
    const int od=plist[di],sd=o2slot[od];
    if(tid<CD*3)Wd[tid]=(Scalar)W[(size_t)tid*nobs+sd];
    __syncthreads();
    if(tid<CD){
      Scalar in[3]={Wd[3*tid],Wd[3*tid+1],Wd[3*tid+2]},out[3];const Scalar* R=Rf+6*p;
      const Scalar y0=in[0]/R[0],y1=(in[1]-R[1]*y0)/R[3],y2=(in[2]-R[2]*y0-R[4]*y1)/R[5];
      out[2]=y2/R[5];out[1]=(y1-R[4]*out[2])/R[3];out[0]=(y0-R[1]*out[1]-R[2]*out[2])/R[0];
      Ud[3*tid]=out[0];Ud[3*tid+1]=out[1];Ud[3*tid+2]=out[2];
    }
    __syncthreads();
    for(int ei=poff[p];ei<poff[p+1];++ei){
      const int oe=plist[ei],se=o2slot[oe];
      if(tid<CD*3)We[tid]=(Scalar)W[(size_t)tid*nobs+se];
      __syncthreads();
      if(tid<CD*CD){
        const int i=tid/CD,j=tid%CD,ci=cam_idx[od],cj=cam_idx[oe];
        const Scalar q=Ud[3*i]*We[3*j]+Ud[3*i+1]*We[3*j+1]+Ud[3*i+2]*We[3*j+2];
        atomicAdd(&S[(CD*ci+i)+(size_t)(CD*cj+j)*nc],-E[CD*ci+i]*q*E[CD*cj+j]);
      }
      __syncthreads();
    }
  }
}

__global__ void W5DenseDifference(const Scalar* __restrict__ a,
                                  const Scalar* __restrict__ b,
                                  Scalar* __restrict__ d, int n){
  int i=blockIdx.x*blockDim.x+threadIdx.x;if(i<n)d[i]=a[i]-b[i];
}
