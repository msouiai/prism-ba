#pragma once
// Conservative work gate, evaluated only at an actual menu expansion.
// Five shifts cost five true residual products, plus import overhead. Require
// more than twice that depth, and leave half the basis capacity for extension.
struct PrismSelectiveReuse {
 enum Decision { Use=0, Cheap=1, Capacity=2, Cooldown=3 };
 int cooldown=0;
 Decision Decide(int depth,int shifts,int capacity){
  if(cooldown>0){--cooldown;return Cooldown;}
  if(depth<=2*shifts)return Cheap;
  if(depth>capacity/2)return Capacity;
  return Use;
 }
 void Observe(bool qualified){if(!qualified)cooldown=2;}
};
