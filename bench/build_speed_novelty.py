#!/usr/bin/env python3
"""Build isolated instrumentation and recovery controls for the frozen champion."""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path('/tmp/prism-speed-novelty')
REPO = pathlib.Path(__file__).resolve().parents[1]

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    if sys.argv[1] == 'prism':
        base = pathlib.Path('/tmp/prism-rl-actor/build')
        m = json.loads((base/'manifest.json').read_text())
        assert sha(base/'source.cu') == m['source_sha256']
        assert all(sha(base/'headers'/k) == v for k, v in m['headers_sha256'].items())
        dest = ROOT/'control-v2'
        dest.mkdir(exist_ok=False)
        shutil.copytree(base/'headers', dest/'headers')
        s = (base/'source.cu').read_text()
        changes = {
            'if(rld.enabled && (!classical_lm || !attr_radius || !attr_strict || !numeric_guard ||':
            'if(rld.enabled && (!classical_lm || !attr_radius || !attr_strict || (!numeric_guard && !getenv("OCA_SCHUR_ABLATION")) ||',
            '  double numeric_floor=1e-16;': '''  const int recovery_mode=getenv("OCA_SCHUR_RECOVERY_MODE")?atoi(getenv("OCA_SCHUR_RECOVERY_MODE")):0;
  if(recovery_mode!=0 && recovery_mode!=2)throw std::runtime_error("recovery mode must be 0=Rayleigh or 2=x4 retained");
  double numeric_floor=1e-16;''',
            'const double repaired=std::clamp(4.*std::max((double)lam_cam,(double)lam_cam-nc_pAp/nc_pp),1e-14,1e16);':
            'const double repaired=recovery_mode==2?std::clamp(4.*(double)lam_cam,1e-14,1e16):std::clamp(4.*std::max((double)lam_cam,(double)lam_cam-nc_pAp/nc_pp),1e-14,1e16);'
        }
        for old, new in changes.items():
            assert s.count(old) == 1
            s = s.replace(old, new)
        (dest/'source.cu').write_text(s)
        cmd = ['nvcc', '-O3', '-DNDEBUG', '-std=c++17', '-arch=sm_89', '-I/usr/include/eigen3',
               '-I'+str(dest/'headers'), str(dest/'source.cu'), '-o', str(dest/'prism-tr'), '-lcublas', '-lcusolver']
        with (dest/'build.log').open('w') as f:
            subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=True)
        (dest/'manifest.json').write_text(json.dumps(dict(parent=m['binary_sha256'],command=cmd,
            binary_sha256=sha(dest/'prism-tr'),source_sha256=sha(dest/'source.cu'),headers_sha256=m['headers_sha256']),indent=2)+'\n')
    else:
        dest = ROOT/'ceres'
        dest.mkdir(exist_ok=False)
        s = (REPO/'bench/ceres/ceres_bal.cc').read_text()
        changes = {
            '#include <ceres/ceres.h>': '#include <ceres/ceres.h>\n#include <cstdlib>\n#include <cstdint>',
            '  std::vector<Item> rows;': '  std::vector<Item> rows;\n  double target=std::getenv("CERES_TARGET_COST")?std::atof(std::getenv("CERES_TARGET_COST")):0;',
            '    return ceres::SOLVER_CONTINUE;': '    return target>0 && s.cost<=target ? ceres::SOLVER_TERMINATE_SUCCESSFULLY : ceres::SOLVER_CONTINUE;',
            ' Trace trace;options.callbacks.push_back(&trace);': ''' Trace trace;options.callbacks.push_back(&trace);
 options.update_state_every_iteration=true;
 if(std::getenv("CERES_MAX_SECONDS"))options.max_solver_time_in_seconds=std::atof(std::getenv("CERES_MAX_SECONDS"));''',
            ' std::printf("CERES %s\\n",summary.FullReport().c_str());': ''' std::printf("CERES %s\\n",summary.FullReport().c_str());
 if(const char* path=std::getenv("CERES_STATE_OUT")) {
   std::ofstream out(path,std::ios::binary);
   out.write("PRISMS01",8);
   uint64_t dims[3]={(uint64_t)nc,(uint64_t)np,(uint64_t)no};out.write((char*)dims,sizeof(dims));
   std::vector<double> rotations(9*nc),translations(3*nc),intr(3*nc,0.);
   for(int i=0;i<nc;++i){
     ceres::AngleAxisToRotationMatrix(cams.data()+8*i,ceres::RowMajorAdapter3x3(rotations.data()+9*i));
     for(int j=0;j<3;++j)translations[3*i+j]=cams[8*i+3+j];
     intr[i]=cams[8*i+6];intr[nc+i]=cams[8*i+7];
   }
   for(const auto* v:{&rotations,&translations,&pts,&intr})out.write((const char*)v->data(),v->size()*sizeof(double));
   if(!out)return 3;
 }'''
        }
        for old, new in changes.items():
            assert s.count(old) == 1, old
            s = s.replace(old, new)
        (dest/'ceres_bal.cc').write_text(s)
        shutil.copyfile(REPO/'bench/ceres/CMakeLists.txt', dest/'CMakeLists.txt')
        with (dest/'build.log').open('w') as f:
            subprocess.run(['cmake','-S',str(dest),'-B',str(dest/'build'),'-DCMAKE_BUILD_TYPE=Release'],stdout=f,stderr=subprocess.STDOUT,check=True)
            subprocess.run(['cmake','--build',str(dest/'build'),'-j2'],stdout=f,stderr=subprocess.STDOUT,check=True)
        (dest/'manifest.json').write_text(json.dumps(dict(source_sha256=sha(dest/'ceres_bal.cc'),
            binary_sha256=sha(dest/'build/ceres_bal'),parent_source_sha256=sha(REPO/'bench/ceres/ceres_bal.cc'),
            changes='target callback, native time cap, state export; Ceres algorithms and defaults unchanged'),indent=2)+'\n')
    print('BUILT', dest, flush=True)

if __name__ == '__main__':
    main()
