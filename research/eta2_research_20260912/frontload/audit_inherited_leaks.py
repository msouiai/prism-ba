#!/usr/bin/env python3
"""Preserve the additional full-leak audit, including pre-existing CLI leaks."""
import json,os,re,subprocess
from pathlib import Path
from check_gpu import P,F,C,CHAMP,run,sha,write


def main():
    subprocess.run(['python3',str(F/'build.py'),'--check-only'],check=True)
    results=[]
    for arm in ('original','on'):
        folder=P/'results'/f'toy-{arm}-leak';folder.mkdir(parents=True,exist_ok=True)
        binary=Path('/tmp/prism-rl-actor/build/prism-tr') if arm=='original' else P/'build/prism-frontload'
        expected=CHAMP['binary_sha256'] if arm=='original' else json.loads((P/'build_manifest.json').read_text())['binary_sha256'];assert sha(binary)==expected
        flags=dict(CHAMP['flags'],OCA_MAX_SECONDS='60')
        if arm=='on':flags.update(OCA_FRONTLOAD='1',OCA_STCG_ATTEMPTS=str(folder/'attempts.json'))
        env={k:v for k,v in os.environ.items() if not k.startswith(('OCA_','CASPAR_','CERES_','COLMAP_MFREE','MF_DEBUG'))};env.update(flags)
        cli=CHAMP['cli'].copy();cli[cli.index('--max_iter')+1]='8'
        cmd=['/usr/local/cuda/bin/compute-sanitizer','--tool','memcheck','--leak-check','full','--error-exitcode','91',str(binary),'--problem',str(C/'build/toy.txt'),*cli]
        write(folder/'manifest.json',dict(command=cmd,flags=flags,binary_sha256=expected,scope='Additional full-leak comparison; preserve failures'))
        rc,seconds=run(cmd,env,folder);text=(folder/'stdout.log').read_text()+(folder/'stderr.log').read_text()
        leak=re.search(r'LEAK SUMMARY: (\d+) bytes leaked in (\d+) allocations',text);errors=re.search(r'ERROR SUMMARY: (\d+) errors',text)
        result=dict(arm=arm,returncode=rc,process_seconds=seconds,leak_bytes=int(leak[1]) if leak else 0,
                    leak_allocations=int(leak[2]) if leak else 0,error_summary=int(errors[1]) if errors else None,
                    solver_completed='RESULT ' in text,frontload_allocation_in_leak_stack=bool(re.search(r'Leaked[\s\S]*?Host Frame: FrontloadAttempt',text)))
        write(folder/'result.json',result);results.append(result);print('LEAK',result,flush=True)
    original,enabled=results
    report=dict(rows=results,extra_full_leak_test_passed=False,
                matching_inherited_leak_counts=(original['leak_bytes'],original['leak_allocations'],original['error_summary'])==(enabled['leak_bytes'],enabled['leak_allocations'],enabled['error_summary']),
                scope='Equal counts do not excuse inherited leaks; default-off failed audit remains in toy-off-0. Frontload-only kernel test separately requires zero leaks.')
    write(P/'results/inherited-leak-comparison.json',report)
    assert original['solver_completed'] and enabled['solver_completed'] and report['matching_inherited_leak_counts']
    assert not enabled['frontload_allocation_in_leak_stack']

if __name__=='__main__':main()
