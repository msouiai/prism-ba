#!/usr/bin/env python3
"""Synthetic checks for the decomposition and strict certification handling."""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

from audit_capture import audit_direction, geometry, roundoff_compare, source_certification_screen

HERE = Path(__file__).resolve().parent
charts = HERE.parent / "charts"
sys.path.insert(0, str(charts))
spec = importlib.util.spec_from_file_location("chart_verify", charts / "verify_reference.py")
chart_verify = importlib.util.module_from_spec(spec); spec.loader.exec_module(chart_verify)
from reference import homogeneous_from_euclidean, make_chart, observation_jacobians


def main():
    rng, cams, X, ci, pi, uv, dc = chart_verify.fixture()
    dp = rng.normal(size=X.shape) * .01
    step = np.concatenate((dc.ravel(), dp.ravel()))
    geom = geometry(cams, X, ci, pi, pair_block=2)
    pc = make_chart(X, cams, "euclidean")
    r, Jc, Jp, _ = observation_jacobians(cams, pc.H, pc.T, ci, pi, uv)
    yc = np.einsum("nij,nj->ni", Jc, dc[ci]); yp = np.einsum("nij,nj->ni", Jp, dp[pi])
    residuals = {
        "full": chart_verify.independent_residual(cams.retract(dc), homogeneous_from_euclidean(X + dp), ci, pi, uv),
        "camera": chart_verify.independent_residual(cams.retract(dc), homogeneous_from_euclidean(X), ci, pi, uv),
        "point": chart_verify.independent_residual(cams, homogeneous_from_euclidean(X + dp), ci, pi, uv),
    }
    initial = .5 * np.sum(r * r)
    cost = .5 * np.sum(residuals["full"]**2)
    pred = -np.sum(r * (yc + yp)) - .5 * np.sum((yc + yp)**2)
    meta = {"cost": initial, "lambda": .1, "tau": .1}
    native = {"arm": "exact", "rep": 0, "certified": 0, "cost": cost,
              "prediction": pred, "decrease": initial - cost, "rho": (initial-cost)/pred}
    row, arrays = audit_direction(cams, X, ci, pi, uv, step, meta, geom, native, chunk_size=7)
    checks = {}
    for name, jd in (("full", yc + yp), ("camera", yc), ("point", yp)):
        # Direct model cost subtraction, independent of production stable form.
        err_obs = .5 * np.sum(residuals[name]**2 - (r + jd)**2, axis=1)
        expected = np.bincount(pi, weights=err_obs, minlength=len(X))
        difference = float(np.max(abs(expected-arrays["D_"+name])))
        assert difference < 1e-10
        checks[name+"_model_error_max_abs"] = difference
    assert np.max(abs(arrays["D_full"] - arrays["D_camera"] - arrays["D_point"] - arrays["D_cross"])) < 1e-13
    assert not row["eligible_for_solve_model_conclusion"]
    assert row["direction_label"] == "approximate_reference"
    assert all(check["status"] == "within_budget" for check in row["native_agreement"].values())
    bins = row["point_error_bins"]
    for binning in bins.values():
        assert sum(cell["points"] for cell in binning.values()) == len(X)
        assert abs(sum(cell["signed_sum"] for cell in binning.values()) - np.sum(arrays["D_point"])) < 1e-11
        assert abs(sum(cell["absolute_sum"] for cell in binning.values()) - np.sum(abs(arrays["D_point"]))) < 1e-11
    assert abs(row["top200_absolute_point_error"]["fraction_of_absolute_point_error"]-1) < 1e-14
    # Blocked exact parallax equals a dense all-pair calculation.
    centers = cams.centers()
    expected_angle = []
    for j in range(len(X)):
        rays = X[j] - centers[ci[pi == j]]
        rays /= np.linalg.norm(rays,axis=1)[:,None]
        expected_angle.append(np.degrees(np.arccos(np.clip(np.min(rays@rays.T),-1,1))))
    checks["parallax_dense_max_abs_degrees"] = float(np.max(abs(geom["parallax_degrees"] - expected_angle)))
    assert checks["parallax_dense_max_abs_degrees"] < 1e-12
    # Near-zero prediction with large cancelling terms uses the stated budget.
    assert roundoff_compare(1e-12, 2e-12, 1e6)["status"] == "within_budget"
    assert roundoff_compare(1., 2., 1.)["status"] == "mismatch"
    # A falsely labelled source cannot pass the solve-branch screen.
    eta = dict(row, arm="eta2", eligible_for_solve_model_conclusion=True,
               rho={"full": .01}, direction_label="native_inexact")
    ref = dict(row, rho={"full": .9})
    screening = source_certification_screen([eta, ref])
    assert screening["comparisons"][0]["classification"] == "unresolved_uncertified_or_audit_mismatch"
    # Independent explicit point normal equation check with saved diagonal.
    diag = np.zeros((len(X),3)); eq = np.zeros((len(X),3)); rhs = np.zeros_like(eq)
    for j in range(len(X)):
        jac = Jp[pi==j].reshape(-1,3); rr=(r+yc)[pi==j].ravel()
        diag[j] = np.sum(jac*jac,axis=0)
        damp = np.maximum(.1*diag[j], 1e-3*.1*np.sum(diag[j])/3)
        eq[j] = jac.T@(rr+jac@dp[j]) + damp*dp[j]
        rhs[j] = -jac.T@rr
    _, _ = audit_direction(cams,X,ci,pi,uv,step,meta,geom,native,chunk_size=9,Cdiag=diag)
    checks["point_equation_relative_residual_agreement"] = abs(row["point_equation"]["relative_residual_norm"]-float(np.linalg.norm(eq)/np.linalg.norm(rhs)))
    assert checks["point_equation_relative_residual_agreement"] < 1e-12
    report = {"status": "synthetic analysis checks passed", "checks": checks,
              "uncertified_source_screen_rejected": True, "partitioned_bins_conserve_signed_and_absolute_error": True,
              "purpose": "implementation verification only, no BA performance verdict"}
    (HERE / "verification.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
