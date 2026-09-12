"""Numerical follow-up: only the O1 inner preconditioner changes."""
from pathlib import Path
import importlib.util,json,os,subprocess
import build_o1 as B
P=B.P
def main():
 subprocess.run(['python3',str(B.F/'build.py'),'--check-only'],check=True)
 original=(P/'o1.cuh').read_text()
 kernel=r'''
__global__ void schurDiagonal(DeviceProblem p,const double* W,const double* vi,double* diag){
 int o=blockIdx.x*blockDim.x+threadIdx.x;if(o>=p.nobs)return;int c=p.cam_idx[o],j=p.pt_idx[o];
 for(int k=0;k<3;++k)for(int l=0;l<3;++l){double x=0;for(int a=0;a<3;++a)for(int b=0;b<3;++b)x+=W[9*o+3*k+a]*vi[9*j+3*a+b]*W[9*o+3*l+b];atomicAdd(diag+9*c+3*k+l,-x);}
}
'''
 anchor='struct Solver {';assert original.count(anchor)==1;h=original.replace(anchor,kernel+'\n'+anchor)
 a='inverse<<<grid(p.ncam),256>>>(p.ncam,U.p,ui.p,bad);inverse<<<grid(p.npt),256>>>(p.npt,V.p,vi.p,bad);checkBad();'
 b='''inverse<<<grid(p.npt),256>>>(p.npt,V.p,vi.p,bad);checkBad();
  {Buf diag(9*p.ncam);copy(diag.p,U.p,9*p.ncam);schurDiagonal<<<grid(p.nobs),256>>>(p,W.p,vi.p,diag.p);inverse<<<grid(p.ncam),256>>>(p.ncam,diag.p,ui.p,bad);checkBad();}
'''
 assert h.count(a)==1;h=h.replace(a,b)
 a='  act.clear();groups.clear();tc.zero();xc.zero();'
 b='''  {std::vector<std::pair<int,int>> edges;edges.reserve(p.nobs);for(int o=0;o<p.nobs;++o)edges.emplace_back(pi[o],ci[o]);std::sort(edges.begin(),edges.end());if(std::adjacent_find(edges.begin(),edges.end())!=edges.end())throw std::runtime_error("duplicate_camera_point_edge");}
'''+a
 assert h.count(a)==1;h=h.replace(a,b)
 header=P/'o1_schur.cuh';header.write_text(h)
 src,n=B.derive();a=str(P/'o1.cuh');assert src.count(a)==1;src=src.replace(a,str(header));dest=P/'build/o1-schur.cu';dest.write_text(src)
 parent=json.loads((P/'o1_build_manifest.json').read_text());cmd=parent['command'].copy();cmd[cmd.index(str(P/'build/o1.cu'))]=str(dest);cmd[cmd.index('-o')+1]=str(P/'build/prism-o1-schur')
 with (P/'build/o1-schur-build.log').open('w') as f:subprocess.run(cmd,env=dict(os.environ,TMPDIR='/dev/shm'),stdout=f,stderr=subprocess.STDOUT,check=True)
 result=dict(parent,binary_sha256=B.sha(P/'build/prism-o1-schur'),source_sha256=B.sha(dest),command=cmd,sources={**parent['sources'],str(header):B.sha(header),str(P/'build_o1_schur.py'):B.sha(P/'build_o1_schur.py')},protocol_sha256=B.sha(P/'O1_SCHUR_DIAGNOSTIC.md'),numerical_change='base Schur diagonal preconditioner; unchanged QP')
 (P/'o1-schur-build-manifest.json').write_text(json.dumps(result,indent=2)+'\n');print('BUILT O1 SCHUR',result['binary_sha256'],flush=True)
if __name__=='__main__':main()
