// Diagnostic-only unrounded camera Jacobian rows, in original observation order.
__global__ void CurvatureCameraRows(const int* ci,const int* pi,const double* uv,
    const double* R,const double* t,const double* X,const double* f,
    const double* k1,const double* k2,int no,double k2mask,double* J){
  int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=no)return;
  int c=ci[o],p=pi[o];const double* r=R+9*c;const double* x=X+3*p;
  double gx[12],gy[12],rx,ry;
  BalResidualGrad12(r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[8],
    t[3*c],t[3*c+1],t[3*c+2],x[0],x[1],x[2],f[c],k1[c],k2[c],
    uv[2*o],uv[2*o+1],gx,gy,&rx,&ry);
  gx[8]*=k2mask;gy[8]*=k2mask;
  for(int i=0;i<9;++i){J[18ul*o+i]=gx[i];J[18ul*o+9+i]=gy[i];}
}
