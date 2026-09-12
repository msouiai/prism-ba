#pragma once
#include <chrono>
#include <cstdio>

struct PrismCoarseAttemptLedger {
  using Clock=std::chrono::steady_clock;
  bool enabled;long attempts=0,products=0,pcg_products=0,numeric_attempts=0;
  double seconds=0,failed_seconds=0,retry_index_seconds=0;
  explicit PrismCoarseAttemptLedger(bool yes):enabled(yes){}
  ~PrismCoarseAttemptLedger(){if(enabled)std::printf("ATTEMPT_SUMMARY attempts=%ld products=%ld pcg_products=%ld seconds=%.9g failed_seconds=%.9g failed_fraction=%.9g retry_index_seconds=%.9g retry_index_fraction=%.9g numeric_attempts=%ld timing=host_native_attempt_no_extra_sync\n",attempts,products,pcg_products,seconds,failed_seconds,seconds>0?failed_seconds/seconds:0,retry_index_seconds,seconds>0?retry_index_seconds/seconds:0,numeric_attempts);}
  struct Attempt {
    PrismCoarseAttemptLedger& ledger;int outer,retry,a0,r0;long m0,n0;
    const int &accepts,&rejects;const long &matvecs,&numeric;
    long pcg=0;Clock::time_point start;
    Attempt(PrismCoarseAttemptLedger& l,int o,int r,const int& a,const int& rej,const long& m,const long& num):ledger(l),outer(o),retry(r),a0(a),r0(rej),m0(m),n0(num),accepts(a),rejects(rej),matvecs(m),numeric(num){if(ledger.enabled)start=Clock::now();}
    ~Attempt(){if(!ledger.enabled)return;double t=std::chrono::duration<double>(Clock::now()-start).count();bool accepted=accepts>a0,rejected=rejects>r0,numeric_retry=numeric>n0;
      ++ledger.attempts;ledger.products+=matvecs-m0;ledger.pcg_products+=pcg;ledger.seconds+=t;
      if(rejected||numeric_retry)ledger.failed_seconds+=t;if(retry>0)ledger.retry_index_seconds+=t;if(numeric_retry)++ledger.numeric_attempts;
      std::printf("ATTEMPT o=%d retry=%d accepted=%d rejected=%d numeric_retry=%d products=%ld pcg_products=%ld seconds=%.9g\n",outer,retry,(int)accepted,(int)rejected,(int)numeric_retry,matvecs-m0,pcg,t);
    }
  };
};
