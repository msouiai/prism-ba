#include "projection.h"
extern "C" void o2_eval(const double* in,double* out){
  o2::ResidualGrad12(in,in+9,in+12,in[15],in[16],in[17],in[18],in[19],in[20],in[21],out,out+12,out+24,out+25);
  out[8]=out[20]=0; // Native SIMPLE_RADIAL k2 mask.
}
