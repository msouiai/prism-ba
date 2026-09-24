#include "../gpu/selective_reuse.h"
#include <stdexcept>
#include <cstdio>
int main(){
 using P=PrismSelectiveReuse;P p;
 auto expect=[&](int depth,P::Decision result){if(p.Decide(depth,5,64)!=result)throw std::runtime_error("selective reuse decision mismatch");};
 expect(0,P::Cheap);expect(10,P::Cheap);expect(11,P::Use);expect(32,P::Use);expect(33,P::Capacity);expect(64,P::Capacity);
 p.Observe(false);expect(16,P::Cooldown);expect(16,P::Cooldown);expect(16,P::Use);
 p.Observe(true);expect(16,P::Use);
 if(p.Decide(6,3,32)!=P::Cheap || p.Decide(7,3,32)!=P::Use)throw std::runtime_error("shift-count cost gate mismatch");
 std::puts("PASS cost boundary, extension capacity, failure cooldown, recovery");
}
