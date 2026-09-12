#pragma once

// Diagnostic and optional opening guard for D10.  Each warp owns one point,
// so the per-track costs are deterministic even though this is only a research
// path.  The scored objective remains the ordinary full L2 objective.
struct W6TrackDamageStats {
  double max_increase=0, positive_sum=0, concentration=0, burden=0;
  double old_track=0, new_track=0;
  int max_point=-1, increased_tracks=0;
};

__global__ void W6TrackDamageKernel(const int* offsets,const int* order,
    const int* ci,const double* uv,const double* oldR,const double* oldt,
    const double* oldX,const double* oldf,const double* oldk1,
    const double* oldk2,const double* newR,const double* newt,
    const double* newX,const double* newf,const double* newk1,
    const double* newk2,int np,double2* costs){
  const int lane=threadIdx.x&31;
  const int point=(blockIdx.x*blockDim.x+threadIdx.x)>>5;
  if(point>=np)return;
  double old_cost=0,new_cost=0;
  for(int j=offsets[point]+lane;j<offsets[point+1];j+=32){
    const int o=order[j];
    old_cost+=PrismTrackObservation(o,point,ci,uv,oldR,oldt,oldX,
                                    oldf,oldk1,oldk2);
    new_cost+=PrismTrackObservation(o,point,ci,uv,newR,newt,newX,
                                    newf,newk1,newk2);
  }
  for(int width=16;width;width>>=1){
    old_cost+=__shfl_down_sync(0xffffffff,old_cost,width);
    new_cost+=__shfl_down_sync(0xffffffff,new_cost,width);
  }
  if(lane==0)costs[point]=make_double2(old_cost,new_cost);
}

struct W6TrackDamage {
  double2* device_costs=nullptr;
  std::vector<double2> host_costs;
  explicit W6TrackDamage(int np):host_costs(np){
    CUDA_CHECK(cudaMalloc(&device_costs,(size_t)np*sizeof(double2)));
  }
  ~W6TrackDamage(){cudaFree(device_costs);}
  W6TrackDamage(const W6TrackDamage&)=delete;

  W6TrackDamageStats Evaluate(const DeviceProblem& p,const DeviceState& old_state,
                              const DeviceState& new_state,double global_gain){
    W6TrackDamageKernel<<<(p.npt+7)/8,256>>>(p.point_obs_offsets,
      p.point_obs_list,p.cam_idx,p.uv,old_state.R,old_state.t,old_state.X,
      INTR_F(p,old_state),INTR_K1(p,old_state),INTR_K2(p,old_state),
      new_state.R,new_state.t,new_state.X,INTR_F(p,new_state),
      INTR_K1(p,new_state),INTR_K2(p,new_state),p.npt,device_costs);
    CUDA_CHECK(cudaMemcpy(host_costs.data(),device_costs,
                          host_costs.size()*sizeof(double2),cudaMemcpyDeviceToHost));
    W6TrackDamageStats out;
    long double sum=0;
    for(int point=0;point<p.npt;++point){
      const double old_cost=host_costs[point].x,new_cost=host_costs[point].y;
      if(!std::isfinite(old_cost)||!std::isfinite(new_cost)){
        out.max_increase=std::numeric_limits<double>::infinity();
        out.max_point=point;out.old_track=old_cost;out.new_track=new_cost;
        continue;
      }
      const double delta=new_cost-old_cost;
      if(delta>0){
        sum+=(long double)delta;++out.increased_tracks;
        if(delta>out.max_increase){out.max_increase=delta;out.max_point=point;
          out.old_track=old_cost;out.new_track=new_cost;}
      }
    }
    out.positive_sum=(double)sum;
    out.concentration=out.positive_sum>0?out.max_increase/out.positive_sum:0;
    out.burden=global_gain>0?out.max_increase/global_gain:
      std::numeric_limits<double>::infinity();
    return out;
  }
};

