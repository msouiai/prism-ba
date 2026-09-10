#pragma once
#include <algorithm>
#include <cmath>

// A guess across nonlinear iterations, not reuse of a linear operator.
// Independent narrow/wide lanes; discard history when damping or age changes.
struct PrismBacktrackHistory {
  struct Lane {int outer=-100,index=0,uses=0; double lambda=0,tau=0; bool valid=false;};
  Lane lane[2];
  int Start(int which,int outer,double lambda,double tau,bool& predicted) {
    auto& h=lane[which];predicted=false;
    if(!h.valid || outer<h.outer || outer-h.outer>1 || lambda!=h.lambda || tau!=h.tau){
      h.valid=false;h.uses=0;return 0;
    }
    // Periodic full search recovers larger steps; between resets probe twice
    // the previous successful scale, so the guess can grow at every search.
    if(++h.uses%8==0)return 0;
    predicted=h.index>1;
    return std::max(0,h.index-1);
  }
  void Observe(int which,int outer,double lambda,double tau,int index) {
    auto& h=lane[which];
    h.outer=outer;h.lambda=lambda;h.tau=tau;h.index=index;h.valid=index>=0;
    if(!h.valid)h.uses=0;
  }
};

// Reorders the SAME finite dyadic menu. Never repeats a trial. If a predicted
// small step fails, all omitted larger steps are recovered before giving up.
struct PrismBacktrackSchedule {
  int count,next,mode; unsigned visited=0; bool recovery=false;
  PrismBacktrackSchedule(int n,int first,int m):count(std::clamp(n,0,12)),
    next(std::clamp(first,0,std::max(0,count-1))),mode(m){}
  static double Alpha(int index){return std::ldexp(1.,-index-1);}
  static int Quadratic(double alpha,double value,double initial,double slope,int n){
    const double den=2*(value-initial-alpha*slope);
    double trial=.5*alpha;
    if(std::isfinite(den) && den>0 && std::isfinite(slope) && slope<0){
      const double q=-slope*alpha*alpha/den;
      if(std::isfinite(q))trial=std::clamp(q,.1*alpha,.5*alpha);
    }
    int i=0;while(i<n-1 && Alpha(i)>trial)i++;
    return i;
  }
  int Next(){
    int i=next;
    while(i<count && (visited&(1u<<i)))++i;
    if(i>=count){i=0;while(i<count && (visited&(1u<<i)))++i;recovery=i<count;}
    if(i>=count)return -1;
    visited|=1u<<i;next=i+1;return i;
  }
  void Failed(int index,double value,double initial,double slope){
    if(mode>=2)next=std::max(index+1,Quadratic(Alpha(index),value,initial,slope,count));
  }
  bool Upward(int index){
    // An already evaluated neighbor is the bracket boundary. Never jump
    // across it or pay for a duplicate, even on a nonmonotone objective.
    if(index<=0 || (visited&(1u<<(index-1))))return false;
    next=index-1;return true;
  }
};
