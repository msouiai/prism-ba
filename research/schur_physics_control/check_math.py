#!/usr/bin/env python3
"""Small deterministic algebra checks. These are NOT BA speed benchmarks."""
import json
from pathlib import Path
import numpy as np

rng = np.random.default_rng(20260910)
nc, npnt, cd = 6, 20, 9
n, p = nc * cd, npnt * 3
J = np.zeros((npnt * 6, n + p))
for point in range(npnt):
    for k, cam in enumerate(rng.choice(nc, 3, replace=False)):
        row = point * 6 + 2 * k
        J[row:row+2, cam*cd:(cam+1)*cd] = rng.normal(size=(2, cd))
        J[row:row+2, n+point*3:n+(point+1)*3] = rng.normal(size=(2, 3))
H = J.T @ J
g = J.T @ rng.normal(size=J.shape[0])
B, W, C = H[:n, :n], H[:n, n:], H[n:, n:]
dc, dp = np.maximum(np.diag(B), 1e-9), np.maximum(np.diag(C), 1e-9)
bc, bp = -g[:n], -g[n:]

def reduced(lam):
    Cp = C + lam * np.diag(dp)
    Bl = B + lam * np.diag(dc)
    return Bl - W @ np.linalg.solve(Cp, W.T), bc - W @ np.linalg.solve(Cp, bp)

def rel(a, b):
    return float(np.linalg.norm(a-b) / max(1., np.linalg.norm(b)))

out = {"seed": 20260910, "scope": "synthetic algebra only; no measured solver speedup"}
lam = .1
S, b = reduced(lam)
d = np.linalg.solve(H + lam*np.diag(np.r_[dc, dp]), -g)
out["schur_joint_solution_relative_error"] = rel(np.linalg.solve(S,b), d[:n])

L = np.linalg.cholesky(B + lam*np.diag(dc))
Linv = np.linalg.solve(L, np.eye(n))
G = Linv @ W @ np.linalg.solve(C+lam*np.diag(dp), W.T) @ Linv.T
G = (G+G.T)/2
Omega = rng.normal(size=(n, 8))
Y = G @ Omega
Ghat = Y @ np.linalg.pinv(Omega.T @ Y) @ Y.T
Ghat = (Ghat+Ghat.T)/2
w, U = np.linalg.eigh(Ghat)
Pinv = np.eye(n) + (U * (w/(1-w))) @ U.T
out["normalized_schur_identity_error"] = rel(Linv @ S @ Linv.T, np.eye(n)-G)
out["G_eigenvalue_range"] = [float(x) for x in np.linalg.eigvalsh(G)[[0,-1]]]
out["nystrom_underestimate_min_eigenvalue"] = float(np.linalg.eigvalsh(G-Ghat)[0])
out["nystrom_inverse_identity_error"] = rel(Pinv @ (np.eye(n)-Ghat), np.eye(n))

# Balanced two-level inverse, with an arbitrary (not necessarily accurate) basis.
Z, _ = np.linalg.qr(rng.normal(size=(n, 8)))
K = Z.T @ S @ Z
Q = Z @ np.linalg.solve(K, Z.T)
M_inv = np.linalg.inv(B+lam*np.diag(dc))
P_inv = Q + (np.eye(n)-Q@S) @ M_inv @ (np.eye(n)-S@Q)
out["balanced_symmetry_error"] = rel(P_inv, P_inv.T)
out["balanced_min_eigenvalue"] = float(np.linalg.eigvalsh(P_inv)[0])
out["balanced_exact_coarse_action_error"] = rel(P_inv @ S @ Z, Z)

# Per-point generalized eigensystems give the EXACT projected coupled family.
factors = []
for point in range(npnt):
    sl = slice(point*3, (point+1)*3)
    t = np.diag(1/np.sqrt(dp[sl]))
    ev, V = np.linalg.eigh(t @ C[sl,sl] @ t)
    F = t @ V
    factors.append((sl, ev, F))
menu_errors = []
for l in [.01, .03, .1, .3, 1.]:
    T = Z.T @ (B+l*np.diag(dc)) @ Z
    h = Z.T @ bc
    for sl, ev, F in factors:
        A = F.T @ W[:,sl].T @ Z
        v = F.T @ bp[sl]
        T -= A.T @ ((1/(ev+l))[:,None]*A)
        h -= A.T @ (v/(ev+l))
    Sl, bl = reduced(l)
    menu_errors.append(max(rel(T,Z.T@Sl@Z), rel(h,Z.T@bl)))
out["rational_projected_family_max_error"] = max(menu_errors)
S1, b1 = reduced(.1)
S2, b2 = reduced(1.)
out["nonshift_term_relative_to_operator_change"] = float(np.linalg.norm(S2-S1-.9*np.diag(dc))/np.linalg.norm(S2-S1))
out["rhs_change_relative"] = rel(b2,b1)

# LM = one linearly implicit gradient-flow step using GN tangent stiffness.
h = 1/lam
M = np.diag(np.r_[dc,dp])
implicit = np.linalg.solve(M+h*H,-h*g)
out["implicit_flow_lm_identity_error"] = rel(implicit,d)

# Linear residual energy identity and a valid damping lower bound.
trial = np.linalg.solve(S,b) + .01*rng.normal(size=n)
e = S @ trial-b
opt = np.linalg.solve(S,b)
gap = .5*(trial-opt) @ S @ (trial-opt)
out["linear_error_energy_identity_error"] = rel(np.array([gap]), np.array([.5*e@np.linalg.solve(S,e)]))
normalized_S = S / np.sqrt(dc[:,None]*dc[None,:])
out["normalized_schur_min_eigenvalue"] = float(np.linalg.eigvalsh(normalized_S)[0])
out["certified_damping_lower_bound"] = lam

# Vanishing progress under high damping does not establish stationarity.
delta = 1/(1+1e12)
out["false_stationarity_example"] = {
    "objective": "0.5*(x-1)^2", "x": 0., "lambda": 1e12,
    "gradient_magnitude": 1., "step": delta,
    "relative_objective_decrease": 1-(1-delta)**2,
}
for key, val in out.items():
    if key.endswith("error"):
        assert val < 1e-10, (key,val)
assert out["nystrom_underestimate_min_eigenvalue"] > -1e-10
assert out["balanced_min_eigenvalue"] > 0
assert out["normalized_schur_min_eigenvalue"] >= lam-1e-10
assert out["G_eigenvalue_range"][1] < 1
assert out["nonshift_term_relative_to_operator_change"] > .01
assert out["rhs_change_relative"] > .01
path = Path(__file__).with_name("math_checks.json")
path.write_text(json.dumps(out,indent=2)+"\n")
print(path.read_text())
