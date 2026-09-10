#pragma once
#include <algorithm>
#include <cmath>
// q(a,b)=gc*a+gp*b+.5*(cc*a*a+2*cp*a*b+pp*b*b), [0,1]^2.
struct PrismSubspaceBox {
 struct Result {double a=0,b=0,prediction=0,slope=0;bool valid=false;};
 static Result Solve(double gc,double gp,double cc,double cp,double pp,bool scalar=false){
  Result out;
  double scale=0;for(double v:{gc,gp,cc,cp,pp}){if(!std::isfinite(v))return out;scale=std::max(scale,std::abs(v));}
  if(!(scale>0) || cc<0 || pp<0)return out;
  using Q=long double;
  Q g=gc/scale,h=gp/scale,A=cc/scale,B=cp/scale,C=pp/scale;
  Q bound=std::sqrt(A*C);
  if(std::abs(B)>bound+1e-12L)return out;
  B=std::clamp(B,-bound,bound); // only roundoff-size PSD repair
  Q best=0,aa=0,bb=0;
  auto consider=[&](Q a,Q b){if(!(a>=0&&a<=1&&b>=0&&b<=1))return;
   Q q=g*a+h*b+.5L*(A*a*a+2*B*a*b+C*b*b);
   if(q<best){best=q;aa=a;bb=b;}};
  auto line=[](Q gradient,Q curvature){return curvature>0?std::clamp(-gradient/curvature,Q(0),Q(1)):(gradient<0?Q(1):Q(0));};
  Q t=line(g+h,std::max(Q(0),A+2*B+C));consider(t,t);
  if(!scalar){
   for(Q a:{Q(0),Q(1)})consider(a,line(h+B*a,C));
   for(Q b:{Q(0),Q(1)})consider(line(g+B*b,A),b);
   Q det=A*C-B*B;
   if(det>0)consider((B*h-C*g)/det,(B*g-A*h)/det);
  }
  out.a=double(aa);out.b=double(bb);out.slope=gc*out.a+gp*out.b;
  // Evaluate the original coefficients, not the rounded PSD repair.
  out.prediction=-(out.slope+.5*(cc*out.a*out.a+2*cp*out.a*out.b+pp*out.b*out.b));
  out.valid=std::isfinite(out.prediction)&&out.prediction>0&&std::isfinite(out.slope)&&out.slope<0;
  return out;
 }
 // Fit positive discrepancy at the rejected full step with E*max(a,b)^2.
 // This is a convex calibrated surrogate, not an error bound elsewhere.
 static Result Calibrated(double gc,double gp,double cc,double cp,double pp,double error,bool scalar=false){
  if(!(error>=0&&std::isfinite(error)))return {};
  if(error==0)return Solve(gc,gp,cc,cp,pp,scalar);
  double scale=error;for(double v:{gc,gp,cc,cp,pp}){if(!std::isfinite(v))return {};scale=std::max(scale,std::abs(v));}
  if(cc<0||pp<0)return {};
  using Q=long double;Q g=gc/scale,h=gp/scale,A=cc/scale,B=cp/scale,C=pp/scale,E=error/scale;
  Q bound=std::sqrt(A*C);if(std::abs(B)>bound+1e-12L)return {};B=std::clamp(B,-bound,bound);
  Q best=0,aa=0,bb=0;
  auto consider=[&](Q a,Q b){if(!(a>=0&&a<=1&&b>=0&&b<=1))return;
   Q t=std::max(a,b),q=g*a+h*b+.5L*(A*a*a+2*B*a*b+C*b*b)+E*t*t;
   if(q<best){best=q;aa=a;bb=b;}};
  auto line=[](Q gradient,Q curvature){return curvature>0?std::clamp(-gradient/curvature,Q(0),Q(1)):(gradient<0?Q(1):Q(0));};
  Q t=line(g+h,std::max(Q(0),A+2*B+C)+2*E);consider(t,t);
  if(!scalar){
   consider(line(g,A+2*E),0);consider(1,line(h+B,C));
   consider(0,line(h,C+2*E));consider(line(g+B,A),1);
   Q det=(A+2*E)*C-B*B;
   if(det>0){Q a=(B*h-C*g)/det,b=(B*g-(A+2*E)*h)/det;if(a>=b)consider(a,b);}
   det=A*(C+2*E)-B*B;
   if(det>0){Q a=(B*h-(C+2*E)*g)/det,b=(B*g-A*h)/det;if(b>=a)consider(a,b);}
  }
  Result out;out.a=double(aa);out.b=double(bb);out.slope=gc*out.a+gp*out.b;
  double tmax=std::max(out.a,out.b);
  out.prediction=-(out.slope+.5*(cc*out.a*out.a+2*cp*out.a*out.b+pp*out.b*out.b)+error*tmax*tmax);
  out.valid=std::isfinite(out.prediction)&&out.prediction>0&&std::isfinite(out.slope)&&out.slope<0;return out;
 }

};
