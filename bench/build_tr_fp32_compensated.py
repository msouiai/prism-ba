#!/usr/bin/env python3
"""Float FMA product compensation: keep Krylov model accuracy without double multiply."""
import pathlib,shutil,json,subprocess
from build_tr_candidate import sha
ROOT=pathlib.Path('/workspace/prism-tr-fp32-products/compensated')
def main():
 base=ROOT.parent/'reliable';m=json.loads((base/'stop-manifest.json').read_text());assert sha(base/'source.cu')==m['source_sha256'];assert all(sha(base/'headers'/k)==v for k,v in m['headers_sha256'].items());ROOT.mkdir();shutil.copytree(base/'headers',ROOT/'headers');s=(base/'source.cu').read_text()
 start=s.index('template <int CD, class HT>\n__global__ void MFPass1Products32');end=s.index('__global__ void MFBackSub',start);body=s[start:end]
 body=body.replace('float q=0;', 'double q=0;')
 body=body.replace('Gp[(size_t)(3*i+j)*nobs+k]*(float)vc[i]', 'MFCompensatedProduct(Gp[(size_t)(3*i+j)*nobs+k],vc[i])')
 body=body.replace('float up[3]={(float)u[3*p],(float)u[3*p+1],(float)u[3*p+2]}','double up[3]={u[3*p],u[3*p+1],u[3*p+2]}')
 body=body.replace('Gc[(size_t)(3*i+j)*nobs+gk]*up[j]', 'MFCompensatedProduct(Gc[(size_t)(3*i+j)*nobs+gk],up[j])')
 helper='''// a is stored float; b = hi + lo + O(u_float^2*b).
// FMA recovers the rounded high product's error (absent under/overflow).
// The low correction gives roughly double-float product accuracy.
__device__ __forceinline__ double MFCompensatedProduct(float a,double b){
 float hi=(float)b,lo=(float)(b-(double)hi);
 float p=__fmul_rn(a,hi);
 float correction=__fmaf_rn(a,hi,-p)+__fmul_rn(a,lo);
 if(!isfinite(p)||!isfinite(correction))return (double)a*b;
 return (double)p+(double)correction;
}
'''
 s=s[:start]+helper+body+s[end:];p=ROOT/'source.cu';p.write_text(s)
 cmd=['/usr/local/cuda/bin/nvcc','-O3','-DNDEBUG','-std=c++17','-arch=sm_89','-I/usr/include/eigen3','-I'+str(ROOT/'headers'),str(p),'-o',str(ROOT/'prism-tr'),'-lcublas','-lcusolver']
 with (ROOT/'build.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 (ROOT/'stop-manifest.json').write_text(json.dumps(dict(command=cmd,source_sha256=sha(p),binary_sha256=sha(ROOT/'prism-tr'),base_source_sha256=m['source_sha256'],headers_sha256={p.name:sha(p) for p in (ROOT/'headers').iterdir()},precision='FP32 high/low product with FMA error correction, FP64 summation, factors, state, reference residual/model checks and acceptance. Nonfinite intermediate uses FP64 product.',residual_policy=m['residual_policy']),indent=2));print(ROOT/'prism-tr')
if __name__=='__main__':main()
