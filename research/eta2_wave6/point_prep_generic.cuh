#pragma once

// Diagnostic generalisation of point_prep_candidate.cuh.  Arithmetic and the
// operation order are unchanged; only the stored fragment scalar is templated.
template<class F>
__global__ void MFPointFactorGuarded(const F* Bo,const int* poff,const int* plist,int np,double* out,int* fallback){
 int p=blockIdx.x*blockDim.x+threadIdx.x;if(p>=np)return;
 double a[6]={};int start=poff[p],end=poff[p+1];
 for(int k=start;k<end;++k)for(int row=0;row<2;++row){int o=plist[k];double x=Bo[6ul*o+3*row],y=Bo[6ul*o+3*row+1],z=Bo[6ul*o+3*row+2];a[0]+=x*x;a[1]+=x*y;a[2]+=x*z;a[3]+=y*y;a[4]+=y*z;a[5]+=z*z;}
 double r[6];r[0]=sqrt(a[0]);r[1]=a[1]/r[0];r[2]=a[2]/r[0];r[3]=sqrt(a[3]-r[1]*r[1]);r[4]=(a[4]-r[1]*r[2])/r[3];r[5]=sqrt(a[5]-r[2]*r[2]-r[4]*r[4]);
 double inv[6];inv[0]=1/r[0];inv[3]=1/r[3];inv[5]=1/r[5];inv[1]=-r[1]*inv[0]*inv[3];inv[4]=-r[4]*inv[3]*inv[5];inv[2]=-(r[1]*inv[4]+r[2]*inv[5])*inv[0];
 double nr=0,ni=0;for(int j=0;j<6;++j){nr+=r[j]*r[j];ni+=inv[j]*inv[j];}
 double rec[6]={r[0]*r[0],r[0]*r[1],r[0]*r[2],r[1]*r[1]+r[3]*r[3],r[1]*r[2]+r[3]*r[4],r[2]*r[2]+r[4]*r[4]+r[5]*r[5]};double err=0,scale=0;for(int j=0;j<6;++j){err=fmax(err,fabs(rec[j]-a[j]));scale=fmax(scale,fabs(a[j]));}
 const double budget=64*2.2204460492503131e-16*fmax(1.,2.*(end-start));
 bool good=isfinite(nr*ni)&&r[0]>0&&r[3]>0&&r[5]>0&&budget*nr*ni<1e-8&&err<=budget*scale;
 if(!good){for(int j=0;j<6;++j)r[j]=0;for(int k=start;k<end;++k){int o=plist[k];double v[3]={double(Bo[6ul*o]),double(Bo[6ul*o+1]),double(Bo[6ul*o+2])};MFGivens(r,v);double w[3]={double(Bo[6ul*o+3]),double(Bo[6ul*o+4]),double(Bo[6ul*o+5])};MFGivens(r,w);}}
 for(int j=0;j<6;++j)out[6ul*p+j]=r[j];if(fallback)fallback[p]=!good;
}

template<class F>
__global__ void MFRhsDiagFused(const F* W,const int* cam,const int* pt,const double* R,const double* ub,int no,double* corr,double* dk){
 int k=blockIdx.x*blockDim.x+threadIdx.x;if(k>=no)return;int p=pt[k],c=cam[k];const double*r=R+6ul*p;double u[3]={ub[3ul*p],ub[3ul*p+1],ub[3ul*p+2]};bool valid=r[0]>0&&r[3]>0&&r[5]>0;
 for(int i=0;i<9;++i){double g[3]={double(W[(3ul*i)*no+k]),double(W[(3ul*i+1)*no+k]),double(W[(3ul*i+2)*no+k])};double rhs=0;for(int j=0;j<3;++j)rhs+=g[j]*u[j];atomicAdd(corr+9*c+i,rhs);
 if(valid&&dk){double y0=g[0]/r[0],y1=(g[1]-r[1]*y0)/r[3],y2=(g[2]-r[2]*y0-r[4]*y1)/r[5];atomicAdd(dk+9*c+i,-(y0*y0+y1*y1+y2*y2));}}
}
