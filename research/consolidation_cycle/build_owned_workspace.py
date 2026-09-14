#!/usr/bin/env python3
"""Derive a full active-BAL scratch-ownership candidate from fixed linear edges."""
from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent
BASE=P/"build/fixed-linear-edges.cu"
OUT=P/"build/owned-workspace.cu"
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def patch(s,a,b):
  assert s.count(a)==1,(a[:100],s.count(a));return s.replace(a,b)
def derive():
  s=BASE.read_text()
  s=patch(s,'#include "deterministic_blas.cuh"','#include "owned_workspace.cuh"')
  s=patch(s,'#include "deterministic_cost.cuh"','#include "owned_deterministic_cost.cuh"')
  cost_static='''  static Scalar* d_cost = nullptr;
  if (!d_cost) CUDA_CHECK(cudaMalloc(&d_cost, sizeof(Scalar)));
  CUDA_CHECK(cudaMemset(d_cost, 0, sizeof(Scalar)));'''
  assert s.count(cost_static)==2
  s=s.replace(cost_static,'''  Scalar* d_cost=OwnedWorkspaceCurrent().cost_output;
  CUDA_CHECK(cudaMemset(d_cost,0,sizeof(Scalar)));''',1)
  s=patch(s,'''  static Result* d_result=nullptr;
  if (!d_result) CUDA_CHECK(cudaMalloc(&d_result,sizeof(Result)));''','''  Result* d_result=static_cast<Result*>(OwnedWorkspaceCurrent().bounded_result);''')
  # Two scalar cost helpers have the same static shape after ComputeCost; replace both.
  s=s.replace('''  static Scalar* d_cost = nullptr;
  if (!d_cost) CUDA_CHECK(cudaMalloc(&d_cost, sizeof(Scalar)));''','''  Scalar* d_cost=OwnedWorkspaceCurrent().cost_output;''')
  s=patch(s,'''  static int* d_count = nullptr;
  if (!d_count) CUDA_CHECK(cudaMalloc(&d_count, sizeof(int)));''','''  int* d_count=OwnedWorkspaceCurrent().count_output;''')
  # Block diagnostic paths are mutually exclusive and sequential.
  s=s.replace('''static int* d_nf=nullptr; static bool once=false;
          if(!d_nf) CUDA_CHECK(cudaMalloc((void**)&d_nf,sizeof(int)));''','''int* d_nf=OwnedWorkspaceCurrent().block_diag_output; static thread_local bool once=false;''')
  s=s.replace('''static int* d_nf=nullptr; static bool once_r=false;
          if(!d_nf) CUDA_CHECK(cudaMalloc((void**)&d_nf,sizeof(int)));''','''int* d_nf=OwnedWorkspaceCurrent().block_diag_output; static thread_local bool once_r=false;''')
  # CLI binding: maximum active vector is full state dimension.
  s=patch(s,'''  DeviceProblem p; p.ncam = ncam; p.npt = npt; p.nobs = nobs; p.n = n;''','''  OwnedBalWorkspace owned_workspace(9*ncam+3*npt,GridSize(nobs));OwnedWorkspaceBinding owned_binding(owned_workspace);
  DeviceProblem p; p.ncam = ncam; p.npt = npt; p.nobs = nobs; p.n = n;''')
  # Public BAL binding and device restoration. Declaration order makes device guard die last.
  s=patch(s,'''  try {
    if (opt.gpu_index >= 0) CUDA_CHECK(cudaSetDevice(opt.gpu_index));

    DeviceArena arena;''','''  try {
    OwnedScopedCudaDevice owned_device_guard;
    if(opt.gpu_index>=0)CUDA_CHECK(cudaSetDevice(opt.gpu_index));
    OwnedBalWorkspace owned_workspace(9*ncam+3*npt,GridSize(nobs));
    OwnedWorkspaceBinding owned_binding(owned_workspace);
    DeviceArena arena;''')
  # Host globals are per-thread for independent library callers. CLI behavior is unchanged.
  for old,new in (
    ('static size_t g_mem_base = 0;','static thread_local size_t g_mem_base = 0;'),
    ('static LearnPolicy g_lp;','static thread_local LearnPolicy g_lp;'),
    ('  static bool done=false; if(done) return; done=true;','  static thread_local bool done=false; if(done) return; done=true;'),
    ('      static bool sc_once=false;','      static thread_local bool sc_once=false;'),
    ('static std::string g_dump_prefix; static std::vector<int> g_dump_iters;','static thread_local std::string g_dump_prefix; static thread_local std::vector<int> g_dump_iters;'),
    ('static std::string g_csv_problem;','static thread_local std::string g_csv_problem;'),
    ('static std::string g_csv_path; static FILE* g_csv = nullptr;','static thread_local std::string g_csv_path; static thread_local FILE* g_csv = nullptr;'),
    ('static std::chrono::steady_clock::time_point g_csv_t0;','static thread_local std::chrono::steady_clock::time_point g_csv_t0;'),
    ('static const BalData* g_bal_ptr = nullptr;','static thread_local const BalData* g_bal_ptr = nullptr;')):s=patch(s,old,new)
  return s
def main():
  source=derive();OUT.write_text(source)
  manifest={"base_source":str(BASE),"base_sha256":sha(BASE),"source_sha256":sha(OUT),"builder_sha256":sha(__file__),"workspace_header_sha256":sha(P/"owned_workspace.cuh"),"cost_header_sha256":sha(P/"owned_deterministic_cost.cuh"),"remaining_scope":"rig excluded; full-model buffers remain per-object; configuration-only function statics remain; per-call CUDA allocations and handles are independent but retain the production manual exception cleanup model"}
  (P/"OWNED_WORKSPACE_SOURCE.json").write_text(json.dumps(manifest,indent=2)+"\n")
if __name__=="__main__":main()
