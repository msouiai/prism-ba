#pragma once
#include "rl_damping.h"
#include <Eigen/Eigenvalues>
#include <vector>

// Research-only extension. No GPU operations; estimates belong to ONE fixed
// damped/preconditioned Schur solve. Never join recurrences across retries.
struct PrismCurvatureDamping : PrismRLDamping {
  bool collect=false, controller=false, use_curvature=false, fallback=false;
  int mode=0,budget=2,actions=0,last_action=-1000000;
  double rho_gate=.75,alpha_gate=1.5,condition_gate=100;
  std::vector<double> alphas,betas;
  bool recurrence_valid=true,model_valid=false,spectrum_valid=false;
  double slope=0,curvature=0,quad_alpha=0,previous_quad_alpha=0;
  double theta_min=0,theta_max=0,condition=0,rayleigh_min=0,rayleigh_max=0;
  int depth=0;

  PrismCurvatureDamping(){
    collect=getenv("OCA_RLC_COLLECT") || getenv("OCA_RLC_POLICY");
    if(collect){
      if(getenv("OCA_RLD_SAVE") || getenv("OCA_RLD_LOAD"))
        throw std::runtime_error("curvature replay is not supported");
      enabled=true;alphas.reserve(128);betas.reserve(128);
    }
    if(const char* path=getenv("OCA_RLC_POLICY")){
      if(policy || episode || getenv("OCA_RLD_ACTION") || getenv("OCA_RLD_OPENING"))
        throw std::runtime_error("curvature controller must be exclusive");
      std::ifstream in(path);std::string magic;int use=0;
      in>>magic>>use>>mode>>budget>>rho_gate>>alpha_gate>>condition_gate;
      if(!in || magic!="PRISM_RLC_V1" || use<0 || use>1 || mode<0 || mode>3 ||
         budget<0 || budget>8 || !std::isfinite(rho_gate) || rho_gate<.25 || rho_gate>1.5 ||
         !std::isfinite(alpha_gate) || alpha_gate<=1 || !std::isfinite(condition_gate) || condition_gate<1)
        throw std::runtime_error("invalid curvature controller");
      controller=true;use_curvature=use;
    }
  }
  void ResetCG(){
    alphas.clear();betas.clear();recurrence_valid=true;rayleigh_min=rayleigh_max=0;
  }
  void ObserveCG(double alpha,double beta,double rayleigh){
    if(!(alpha>0 && beta>=0 && std::isfinite(alpha) && std::isfinite(beta) &&
         rayleigh>0 && std::isfinite(rayleigh)) || alphas.size()>=128){recurrence_valid=false;return;}
    if(alphas.empty())rayleigh_min=rayleigh_max=rayleigh;
    else{rayleigh_min=std::min(rayleigh_min,rayleigh);rayleigh_max=std::max(rayleigh_max,rayleigh);}
    alphas.push_back(alpha);betas.push_back(beta);
  }
  void ObserveModel(double gdotd,double dHGN_d){slope=gdotd;curvature=dHGN_d;}
  void Summarize(){
    previous_quad_alpha=quad_alpha;
    model_valid=std::isfinite(slope)&&std::isfinite(curvature)&&slope<0&&curvature>0;
    quad_alpha=model_valid?-slope/curvature:0;
    if(!std::isfinite(quad_alpha)){quad_alpha=0;model_valid=false;}
    depth=int(alphas.size());spectrum_valid=false;theta_min=theta_max=condition=0;
    if(recurrence_valid && depth>=4){
      Eigen::VectorXd diagonal(depth),off(depth-1);
      for(int i=0;i<depth;++i){
        diagonal[i]=1/alphas[i]+(i?betas[i-1]/alphas[i-1]:0);
        if(i)off[i-1]=std::sqrt(betas[i-1])/alphas[i-1];
      }
      if(diagonal.allFinite()&&off.allFinite()){
        Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> eigen;
        eigen.computeFromTridiagonal(diagonal,off,Eigen::EigenvaluesOnly);
        if(eigen.info()==Eigen::Success){
          theta_min=eigen.eigenvalues()[0];theta_max=eigen.eigenvalues()[depth-1];
          spectrum_valid=theta_min>0&&std::isfinite(theta_max)&&std::isfinite(theta_max/theta_min);
          if(spectrum_valid)condition=theta_max/theta_min;
          else theta_min=theta_max=0;
        }
      }
    }
  }
  int Action(int outer){
    if(!controller)return PrismRLDamping::Action(outer);
    if(!history_count || !mode)return 0;
    if(history[8]>0 || history[9]>0 || history[2]<.25 || history[2]>1.5 || history[3]<-7)fallback=true;
    if(fallback || actions>=budget || outer-last_action<=1 || history[0]<-12 || history[0]>1)return 0;
    bool up=history[7]>=.99;
    bool down=history[2]>=rho_gate && history[7]<=.25;
    if(use_curvature){
      up=up && spectrum_valid && condition>=condition_gate && model_valid && quad_alpha<=alpha_gate;
      // Require a descent-model indication that persists beyond one step.
      down=history[2]>=rho_gate && model_valid && quad_alpha>=alpha_gate &&
           (history_count<2 || previous_quad_alpha>1);
    }
    int action=((mode==2||mode==3)&&up)?1:((mode==1||mode==3)&&down)?-1:0;
    if(action){++actions;last_action=outer;}
    return action;
  }
  void End(int outer,bool accepted,double used,double next,double floor,double rho,double pred,
      double raw_norm,double radius,double nb,double eta,int cg,int maxck,long mv,long rejects,
      long repairs,double cost,int nobs,int nc,int np){
    if(collect)Summarize();
    PrismRLDamping::End(outer,accepted,used,next,floor,rho,pred,raw_norm,radius,nb,eta,cg,maxck,
                       mv,rejects,repairs,cost,nobs,nc,np);
    if(controller && (history[8]>0 || history[9]>0 || history[2]<.25 || history[2]>1.5 || history[3]<-7))fallback=true;
    if(collect && file){
      std::fprintf(file,"{\"type\":\"curvature\",\"outer\":%d,\"model_valid\":%d,\"slope\":%.17g,\"curvature\":%.17g,\"quad_alpha\":%.17g,\"previous_quad_alpha\":%.17g,\"depth\":%d,\"spectrum_valid\":%d,\"theta_min\":%.17g,\"theta_max\":%.17g,\"condition\":%.17g,\"rayleigh_min\":%.17g,\"rayleigh_max\":%.17g,\"actions\":%d,\"fallback\":%d}\n",
        outer,int(model_valid),Fin(slope),Fin(curvature),quad_alpha,previous_quad_alpha,depth,
        int(spectrum_valid),theta_min,theta_max,condition,rayleigh_min,rayleigh_max,actions,int(fallback));
    }
  }
};
