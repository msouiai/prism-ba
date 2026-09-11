  // Default-off one-shot experiments; the original source is not edited.
  const bool depth_stop=getenv("OCA_DEPTH_STOP") && atoi(getenv("OCA_DEPTH_STOP"))!=0;
  const bool depth_declip=getenv("OCA_DEPTH_DECLIP") && atoi(getenv("OCA_DEPTH_DECLIP"))!=0;
  if((depth_stop||depth_declip) && (!classical_lm||!attr_radius||!attr_strict||!numeric_guard||
      !pcg||pcg->reuse||pcg->schur||L!=1||CD!=9||shared_intr||mf_fp32||rk||block_eq||
      camera_tr||demand_mode||recycle_mode||replay_load||replay_save))
    throw std::runtime_error("depth rescue requires fresh guarded Eta2 without replay");
  int depth_pending=0,depth_active=0;
  bool depth_stop_spent=false,depth_declip_spent=false;
  double depth_flat_center=lam_cam,depth_requested_center=lam_cam;
  double depth_true_residual=-1,depth_start_seconds=0;
  int depth_linear_iterations=0;
  long depth_calls=0,depth_wins=0,depth_failures=0,depth_begin_mv=0;
  double depth_seconds=0;
  std::function<void()> depth_restore;
