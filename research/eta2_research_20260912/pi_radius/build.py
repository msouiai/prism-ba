#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,subprocess
P=Path(__file__).resolve().parent;F=P.parents[1]/'eta2_champion'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    original=(F/'source/prism_eta2.cu').read_text();s=original;patches=[]
    def patch(a,b):
        nonlocal s
        assert s.count(a)==1,(a[:80],s.count(a));s=s.replace(a,b);patches.append((a,b))
    patch('  double attr_R=0,attr_old_R=0,attr_norm=0,attr_next_lambda=0,attr_raw_norm=0;',
      '  const bool pi_radius=getenv("OCA_PI_RADIUS") && atoi(getenv("OCA_PI_RADIUS"))!=0;\n'
      '  double pi_previous_error=0; long pi_updates=0,pi_invalid=0;\n'
      '  double attr_R=0,attr_old_R=0,attr_norm=0,attr_next_lambda=0,attr_raw_norm=0;')
    a='        attr_R=prism_camera_tr::radius_after(attr_old_R,attr_norm,lm_rho);'
    patch(a,a+'''\n        if(pi_radius && have){
          double e=std::max(1e-6,std::fabs(1.-lm_rho));
          if(std::isfinite(e)){
            double previous=pi_previous_error>0?pi_previous_error:e;
            double factor=std::clamp(std::exp(.3*std::log(.3/e)+.4*std::log(previous/e)),.25,2.);
            attr_R=std::max(1e-14,attr_old_R*factor);
            pi_previous_error=e; ++pi_updates;
            printf("PI_RADIUS o=%d e=%.17g previous=%.17g factor=%.17g radius=%.17g next=%.17g\\n",k,e,previous,factor,attr_old_R,attr_R);
          } else ++pi_invalid;
        }''')
    undo=s
    for a,b in reversed(patches):assert undo.count(b)==1;undo=undo.replace(b,a)
    assert undo==original
    b=P/'build';b.mkdir(exist_ok=True);src=b/'prism_pi.cu';src.write_text(s)
    cmd=['nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(F/'source/headers'),str(src),'-o',str(b/'prism-pi'),'-lcublas','-lcusolver']
    with (b/'build.log').open('w') as out:subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT,check=True)
    out=dict(command=cmd,source_sha256=sha(src),binary_sha256=sha(b/'prism-pi'),frozen_source_sha256=sha(F/'source/prism_eta2.cu'),
      reverse_patch_byte_identity=True,protocol_sha256=sha(P/'PROTOCOL.md'))
    (b/'manifest.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
