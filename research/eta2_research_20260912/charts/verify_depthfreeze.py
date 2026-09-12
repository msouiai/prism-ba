#!/usr/bin/env python3
"""Verify constraint math and unchanged default controls before witness trials."""
from pathlib import Path
import hashlib,json,subprocess,sys,types
import numpy as np
import reference
from verify_reference import fixture,relative_error
from run_depthfreeze import freeze_rule,OUT


def main():
    OUT.mkdir(exist_ok=True);baseline=reference.verify_frozen_baseline()
    root=Path(__file__).resolve().parents[3]
    refpath='research/eta2_research_20260912/charts/reference.py'
    revision='f8d25e36ea3bb59d3e316a0422ed166bdd5788c4'
    source=subprocess.check_output(['git','show',revision+':'+refpath],cwd=root).decode()
    old=types.ModuleType('old_chart_reference');old.__file__=str(Path(reference.__file__))
    sys.modules[old.__name__]=old;exec(compile(source,old.__file__,'exec'),old.__dict__)
    rng,c,X,ci,pi,uv,dc=fixture();co=old.CameraState(c.R,c.t,c.intrinsics)
    defaults={}
    for kind in ('euclidean','homogeneous','inverse_depth'):
        before=old.evaluate_chart_step(co,X,ci,pi,uv,dc,.1,chart=kind,chunk_size=7)
        after=reference.evaluate_chart_step(c,X,ci,pi,uv,dc,.1,chart=kind,chunk_size=7)
        for key in ('delta','H_candidate','point_normal','point_damping','euclidean_displacement'):
            assert np.array_equal(before[key],after[key]),(kind,key)
        for key in ('costs','pred','rho','score_init','linear_relative_residual','fling_count'):
            assert before[key]==after[key],(kind,key)
        defaults[kind]='bit-identical numerical arrays and scores to committed pre-freeze reference'
    nofreeze=reference.evaluate_chart_step(c,X,ci,pi,uv,dc,.1,chart='inverse_depth',freeze_depth=np.zeros(len(X),bool),chunk_size=7)
    for key in ('delta','H_candidate','point_normal','point_damping'):
        assert np.array_equal(nofreeze[key],after[key]),key
    tests=[]
    for mask in (np.arange(len(X))%2==0,np.ones(len(X),bool)):
        ans=reference.evaluate_chart_step(c,X,ci,pi,uv,dc,.1,chart='inverse_depth',freeze_depth=mask,chunk_size=7)
        pc=ans['chart'];r,Jc,Jp,_=reference.observation_jacobians(c,pc.H,pc.T,ci,pi,uv)
        rc=r+np.einsum('nij,nj->ni',Jc,dc[ci]);errs=[]
        for j in range(len(X)):
            dim=2 if mask[j] else 3;sel=pi==j
            A=np.vstack((Jp[sel,:,:dim].reshape(-1,dim),np.diag(np.sqrt(ans['point_damping'][j,:dim]))))
            b=np.r_[-rc[sel].ravel(),np.zeros(dim)]
            expect=np.linalg.lstsq(A,b,rcond=None)[0]
            errs.append(relative_error(expect,ans['delta'][j,:dim]))
        assert max(errs)<1e-11
        assert np.all(ans['delta'][mask,2]==0.)
        assert np.array_equal(ans['H_candidate'][mask,3],pc.H[mask,3])
        assert ans['linear_relative_residual']<1e-12
        assert ans['constraint_reaction_norm']>0.
        tests.append(dict(frozen=int(mask.sum()),augmented_lstsq_max_relative_error=max(errs),
                          active_residual=ans['linear_relative_residual'],constraint_reaction_norm=ans['constraint_reaction_norm']))
    counts=np.array([0,1,2,2,2,2,3,4,2]);angles=np.array([np.nan,np.nan,.999,1,1,1,0.999,1,np.nan])
    eig=np.tile([1.,2.,3.],(len(counts),1));eig[3]=[1,1,1e8];eig[4]=[0,1,3];eig[8]=[-1,1,3]
    mask,_=freeze_rule(counts,angles,eig)
    expected=np.array([1,1,1,1,1,0,1,0,1],bool)
    assert np.array_equal(mask,expected)
    for bad in (np.ones(len(X)),np.zeros(len(X)+1,bool)):
        try:reference.conditional_point_solve(c,X,ci,pi,uv,dc,.1,chart='inverse_depth',freeze_depth=bad)
        except ValueError:pass
        else:raise AssertionError('invalid mask accepted')
    # One actual witness control checks the same unchanged path in cancellation-
    # prone geometry; it is a parity check, not a new chart outcome or tuning run.
    from audit_capture import load_capture_state,map_f64
    base=Path(__file__).resolve().parents[1]
    capture=base/'evidence/collect/venice-52-capture-0'
    realc,realX,meta=load_capture_state(capture)
    rci,rpi,ruv,dims=reference.load_observations(Path('/workspace/bal/venice-52.txt'))
    realdc=map_f64(capture/'eta2-0.step',(9*dims[0]+3*dims[1],))[:9*dims[0]].reshape(dims[0],9)
    oldc=old.CameraState(realc.R,realc.t,realc.intrinsics)
    before=old.conditional_point_solve(oldc,realX,rci,rpi,ruv,realdc,meta['lambda'],chart='inverse_depth')
    after=reference.conditional_point_solve(realc,realX,rci,rpi,ruv,realdc,meta['lambda'],chart='inverse_depth')
    assert np.array_equal(before['delta'],after['delta']) and np.array_equal(before['H_candidate'],after['H_candidate'])
    out=dict(status='all checks passed',baseline=baseline,old_revision=revision,old_reference_sha256=hashlib.sha256(source.encode()).hexdigest(),
             new_reference_sha256=hashlib.sha256(Path(reference.__file__).read_bytes()).hexdigest(),default_control_invariance=defaults,
             all_false_inverse_depth_mask_bit_identical=True,venice0_default_control_bit_identical=True,
             constraints=tests,threshold_boundary_rule_verified=True)
    path=OUT/'verification.json';path.write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(status=out['status'],constraints=tests,output=str(path)),indent=2))


if __name__=='__main__':main()
