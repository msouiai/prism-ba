#include "geometry.h"
#include <fstream>
#include <iostream>
int main(int argc,char** argv){
  if(argc!=3)return 2;
  std::ifstream in(argv[1],std::ios::binary);int nc=0;in.read((char*)&nc,4);
  if(nc<1||nc>20000)throw std::runtime_error("invalid probe input");
  std::vector<double> R(9ul*nc),t(3ul*nc),E(9ul*nc);
  for(auto* a:{&R,&t,&E})in.read((char*)a->data(),8*a->size());
  if(!in)throw std::runtime_error("incomplete geometry input");
  prism_coarse::Geometry g(nc);g.Build(R,t,E);
  std::ofstream out(argv[2],std::ios::binary);
  for(int a:{nc,g.K,g.rank})out.write((char*)&a,4);
  for(auto* a:{&g.label,&g.local_rank,&g.offset})out.write((char*)a->data(),4*a->size());
  out.write((char*)g.Z.data(),8*g.Z.size());
  if(!out)throw std::runtime_error("cannot write probe output");
}
