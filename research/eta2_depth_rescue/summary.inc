  if(depth_stop||depth_declip)std::printf("DEPTH_SUMMARY calls=%ld wins=%ld failures=%ld seconds=%.17g stop_spent=%d declip_spent=%d\n",
    depth_calls,depth_wins,depth_failures,depth_seconds,(int)depth_stop_spent,(int)depth_declip_spent);
