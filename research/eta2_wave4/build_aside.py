"""Reversible acceptance-only overlay on the verified wave-3 derived source."""
from pathlib import Path
import hashlib, importlib.util, json, os, subprocess

P = Path(__file__).resolve().parent
W = P.parent / 'eta2_wave3'
F = P.parent / 'eta2_champion'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def derive():
    spec = importlib.util.spec_from_file_location('wave4_parent', W / 'build.py')
    parent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parent)
    original, n = parent.derive()
    s = original
    patches = []

    def patch(a, b, count=1):
        nonlocal s
        assert s.count(a) == count, (a[:100], s.count(a), count)
        s = s.replace(a, b)
        patches.append((a, b, count))

    anchor = '  Scalar cost=ComputeCost(p,s,rk,rk_a2);'
    patch(anchor, anchor + r'''
  const double w4_rho_min=getenv("OCA_W4_RHO_MIN")?atof(getenv("OCA_W4_RHO_MIN")):.1;
  const int w4_window=getenv("OCA_W4_NONMONOTONE")?atoi(getenv("OCA_W4_NONMONOTONE")):0;
  if(!std::isfinite(w4_rho_min)||w4_rho_min<0||w4_rho_min>.1||
     (w4_window!=0&&w4_window!=5))throw std::runtime_error("Invalid W4 acceptance configuration");
  if((w4_rho_min!=.1||w4_window)&&(!classical_lm||!attr_radius||L!=1||rk!=0))
    throw std::runtime_error("W4 acceptance requires frozen single-shift L2 radius path");
  std::vector<double> w4_history;
  DeviceState w4_best_state{};
  double w4_best_cost=cost;long w4_uphill=0,w4_relaxed=0;
  if(w4_window){w4_history.push_back(cost);AllocState(w4_best_state,ncam,npt,CD==9);CopyState(w4_best_state,s,ncam,npt);}
''')
    anchor = '    Scalar best_cost=cost; int best_sh=-1,best_ck=-1; bool have=false;'
    patch(anchor, '''    const double w4_reference=w4_window?*std::max_element(w4_history.begin(),w4_history.end()):(double)cost;
    Scalar best_cost=w4_reference; int best_sh=-1,best_ck=-1; bool have=false;''')
    anchor = '      have=have&&std::isfinite(lm_rho)&&lm_prediction>0&&lm_rho>(attr_strict?.1:0);'
    patch(anchor, r'''
      const double w4_test_rho=have&&lm_prediction>0?(w4_reference-best_cost)/lm_prediction:-1;
      const bool w4_original_accept=have&&std::isfinite(lm_rho)&&lm_prediction>0&&lm_rho>(attr_strict?.1:0);
      have=have&&std::isfinite(w4_test_rho)&&lm_prediction>0&&w4_test_rho>(attr_strict?w4_rho_min:0);
      if(have&&!w4_original_accept)++w4_relaxed;
      if(w4_rho_min!=.1||w4_window)std::printf("W4_ACCEPT o=%d current=%.17g reference=%.17g candidate=%.17g prediction=%.17g current_rho=%.17g test_rho=%.17g original_accept=%d pre_radius_accept=%d\n",k,(double)cost,w4_reference,(double)best_cost,lm_prediction,lm_rho,w4_test_rho,(int)w4_original_accept,(int)have);
''')
    anchor = '''    if(have && best_cost<cost){
      // OCA_DOOMED accounting:'''
    patch(anchor, '''    if(have && best_cost<w4_reference){
      // OCA_DOOMED accounting:''')
    anchor = '''      DoRetract(d_best,s_new); CopyState(s,s_new,ncam,npt);
      cost=best_cost;'''
    patch(anchor, anchor + r'''
      if(w4_window){
        if(cost>cost_pre_accept)++w4_uphill;
        w4_history.push_back(cost);
        if(w4_history.size()>(size_t)w4_window)w4_history.erase(w4_history.begin());
        if(cost<w4_best_cost){w4_best_cost=cost;CopyState(w4_best_state,s,ncam,npt);}
      }
''')
    anchor = '  int cheir1=CountCheiralityViolations(p,s);'
    patch(anchor, r'''
  if(w4_window){
    std::printf("W4_FINAL current=%.17g best=%.17g uphill=%ld relaxed=%ld\n",(double)cost,w4_best_cost,w4_uphill,w4_relaxed);
    if(cost!=w4_best_cost){CopyState(s,w4_best_state,ncam,npt);cost=w4_best_cost;
      log.costs.back()=cost;CsvRow(log.iters.back(),(double)cost);}
    cudaFree(w4_best_state.R);cudaFree(w4_best_state.t);cudaFree(w4_best_state.X);cudaFree(w4_best_state.intr);
  }
  if(w4_rho_min!=.1)std::printf("W4_SUMMARY rho_min=%.17g window=%d relaxed=%ld uphill=%ld\n",w4_rho_min,w4_window,w4_relaxed,w4_uphill);
''' + anchor)
    restored = s
    for a, b, count in reversed(patches):
        assert restored.count(b) == count
        restored = restored.replace(b, a)
    assert restored == original
    return s, n + len(patches)


def main():
    subprocess.run(['python3', str(F / 'build.py'), '--check-only'], check=True)
    s, n = derive()
    folder = P / 'build'
    folder.mkdir(exist_ok=True)
    src = folder / 'aside.cu'
    src.write_text(s)
    parent = json.loads((W / 'build_manifest.json').read_text())
    cmd = parent['command'].copy()
    cmd[cmd.index(str(W / 'build/prism_wave3.cu'))] = str(src)
    cmd[cmd.index('-o') + 1] = str(folder / 'prism-aside')
    env = dict(os.environ, TMPDIR='/dev/shm')
    with (folder / 'aside-build.log').open('w') as f:
        subprocess.run(cmd, env=env, stdout=f, stderr=subprocess.STDOUT, check=True)
    record = dict(command=cmd, source_sha256=sha(src), binary_sha256=sha(folder / 'prism-aside'),
                  frozen_source_sha256=sha(F / 'source/prism_eta2.cu'),
                  champion_sha256=sha(F / 'champion.json'), reversible_patch_count=n,
                  sources={**parent['sources'], str(P / 'build_aside.py'): sha(P / 'build_aside.py')})
    (P / 'aside_build_manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print('BUILT', record['binary_sha256'], flush=True)


if __name__ == '__main__':
    main()
