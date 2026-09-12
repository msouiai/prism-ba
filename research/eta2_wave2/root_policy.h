#pragma once
struct WaveRootPolicy {
  int outer=-1,updates=0;
  bool active=false;
  double tau=0,base=0,prev_lambda=0,prev_norm=0,lo=0,hi=0;
  void Start(int k,double lambda){if(outer!=k){outer=k;updates=0;active=false;tau=base=lo=lambda;hi=prev_lambda=prev_norm=0;}}
  double Next(double lambda,double norm,double radius){
    if(!(radius>0) || !std::isfinite(norm))return 0;
    if(norm>2*radius)active=true;
    if(!active || (norm>=.5*radius && norm<=radius) || updates>=8)return 0;
    if(norm>radius)lo=lambda;else hi=lambda;
    double next;
    if(hi>lo)next=std::sqrt(lo*hi);
    else{
      double power=1.;
      if(prev_lambda>0&&prev_lambda!=lambda&&norm>0&&prev_norm>0){
        double slope=std::log(norm/prev_norm)/std::log(lambda/prev_lambda);
        if(slope<-.05)power=std::clamp(-1./slope,.25,4.);
      }
      next=lambda*std::clamp(std::pow(norm/(.75*radius),power),2.,1e8);
    }
    prev_lambda=lambda;prev_norm=norm;next=std::clamp(next,base,1e16);
    if(next==lambda)return 0;++updates;return next;
  }
};
