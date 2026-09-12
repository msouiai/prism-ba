#!/usr/bin/env python3
"""Deterministic field-scaled BAL perturbations and independent residuals."""
from dataclasses import dataclass
from pathlib import Path
import argparse
import hashlib
import json
import math

import numpy as np


@dataclass
class BalProblem:
    ncam: int
    npt: int
    nobs: int
    camera_index: np.ndarray
    point_index: np.ndarray
    observations: np.ndarray
    cameras: np.ndarray
    points: np.ndarray
    state_offset: int
    path: Path


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_bal(path):
    path = Path(path)
    with path.open("rb") as stream:
        first = stream.readline()
        ncam, npt, nobs = map(int, first.split())
        values = np.fromfile(stream, sep=" ", dtype=np.float64)
    with path.open("rb") as stream:
        stream.readline()
        for _ in range(nobs):
            if not stream.readline():
                raise ValueError("truncated observation table")
        state_offset = stream.tell()
    obs = values[:4*nobs]
    expected = 9 * ncam + 3 * npt
    state = values[4*nobs:]
    if obs.size != 4*nobs or state.size != expected:
        raise ValueError(("BAL value counts", obs.size, state.size, 4*nobs, expected))
    obs = obs.reshape(nobs, 4)
    return BalProblem(ncam, npt, nobs, obs[:, 0].astype(np.int32),
                      obs[:, 1].astype(np.int32), obs[:, 2:4].copy(),
                      state[:9*ncam].reshape(ncam, 9).copy(),
                      state[9*ncam:].reshape(npt, 3).copy(), state_offset, path)


def _normalised(rng, shape):
    values = rng.standard_normal(shape)
    rms = math.sqrt(float(np.mean(values * values)))
    return values / rms


def field_scales(problem):
    centred = problem.points - np.median(problem.points, axis=0)
    geometry = float(np.median(np.linalg.norm(centred, axis=1)))
    focal = float(np.median(np.abs(problem.cameras[:, 6])))
    radial = float(np.median(np.abs(problem.cameras[:, 7])))
    return {
        "rotation_radians": 1.0,
        "geometry": max(geometry, np.finfo(float).tiny),
        "focal": max(focal, 1.0),
        "k1": max(radial, 1e-3),
    }


def perturb(problem, seed, epsilon):
    rng = np.random.Generator(np.random.PCG64(seed))
    scales = field_scales(problem)
    cameras, points = problem.cameras.copy(), problem.points.copy()
    # At 1e-12--1e-10, additive angle-axis coordinates are the tangent chart
    # to first order.  Normalising each field fixes the registered RMS dose.
    cameras[:, :3] += epsilon * _normalised(rng, (problem.ncam, 3))
    cameras[:, 3:6] += epsilon * scales["geometry"] * _normalised(rng, (problem.ncam, 3))
    cameras[:, 6] += epsilon * scales["focal"] * _normalised(rng, problem.ncam)
    cameras[:, 7] += epsilon * scales["k1"] * _normalised(rng, problem.ncam)
    cameras[:, 8] = 0.0
    points += epsilon * scales["geometry"] * _normalised(rng, (problem.npt, 3))
    return cameras, points, scales


def write_state(problem, path, cameras, points):
    path = Path(path)
    with problem.path.open("rb") as source, path.open("wb") as target:
        remaining = problem.state_offset
        while remaining:
            block = source.read(min(8 << 20, remaining))
            if not block:
                raise ValueError("truncated observation prefix")
            target.write(block)
            remaining -= len(block)
        for value in np.concatenate((cameras.ravel(), points.ravel())):
            target.write((format(float(value), ".17g") + "\n").encode("ascii"))


def angle_axis_matrices(vectors):
    vectors = np.asarray(vectors, dtype=np.float64)
    theta = np.linalg.norm(vectors, axis=1)
    matrices = np.repeat(np.eye(3)[None, :, :], len(vectors), axis=0)
    nz = theta > 1e-15
    if not np.any(nz):
        return matrices
    axis = vectors[nz] / theta[nz, None]
    x, y, z = axis.T
    zero = np.zeros_like(x)
    skew = np.stack((zero, -z, y, z, zero, -x, -y, x, zero), axis=1).reshape(-1, 3, 3)
    sine, cosine = np.sin(theta[nz]), np.cos(theta[nz])
    matrices[nz] += sine[:, None, None] * skew + (1-cosine)[:, None, None] * (skew @ skew)
    return matrices


def state_from_bal(problem, cameras=None, points=None):
    cameras = problem.cameras if cameras is None else cameras
    points = problem.points if points is None else points
    return {
        "R": angle_axis_matrices(cameras[:, :3]),
        "t": cameras[:, 3:6],
        "X": points,
        "f": cameras[:, 6],
        "k1": cameras[:, 7],
        "k2": np.zeros(problem.ncam),
    }


def read_prism_state(path):
    with open(path, "rb") as stream:
        if stream.read(8) != b"PRISMS01":
            raise ValueError("bad Prism state magic")
        dims = np.fromfile(stream, dtype=np.uint64, count=3)
        ncam, npt, nobs = map(int, dims)
        R = np.fromfile(stream, dtype=np.float64, count=9*ncam).reshape(ncam, 3, 3)
        t = np.fromfile(stream, dtype=np.float64, count=3*ncam).reshape(ncam, 3)
        X = np.fromfile(stream, dtype=np.float64, count=3*npt).reshape(npt, 3)
        intr = np.fromfile(stream, dtype=np.float64, count=3*ncam)
        if intr.size != 3*ncam or stream.read(1):
            raise ValueError("bad Prism state length")
    return {"dims": (ncam, npt, nobs), "R": R, "t": t, "X": X,
            "f": intr[:ncam], "k1": intr[ncam:2*ncam], "k2": intr[2*ncam:]}


def residual_distance(problem, left, right, chunk=250_000):
    total = 0.0
    for start in range(0, problem.nobs, chunk):
        stop = min(problem.nobs, start + chunk)
        ci, pi = problem.camera_index[start:stop], problem.point_index[start:stop]
        values = []
        for state in (left, right):
            Y = np.einsum("nij,nj->ni", state["R"][ci], state["X"][pi]) + state["t"][ci]
            q = -Y[:, :2] / Y[:, 2, None]
            r2 = np.einsum("ij,ij->i", q, q)
            distortion = 1 + state["k1"][ci] * r2 + state["k2"][ci] * r2 * r2
            values.append(state["f"][ci, None] * distortion[:, None] * q
                          - problem.observations[start:stop])
        delta = values[1] - values[0]
        total += float(np.einsum("ij,ij->", delta, delta))
    return math.sqrt(total)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--epsilon", type=float, required=True)
    parser.add_argument("--manifest")
    args = parser.parse_args()
    problem = load_bal(args.input)
    cameras, points, scales = perturb(problem, args.seed, args.epsilon)
    write_state(problem, args.output, cameras, points)
    initial_distance = residual_distance(problem, state_from_bal(problem),
                                         state_from_bal(problem, cameras, points))
    result = {"input": str(Path(args.input).resolve()), "input_sha256": sha256(args.input),
              "output": str(Path(args.output).resolve()), "output_sha256": sha256(args.output),
              "seed": args.seed, "epsilon": args.epsilon, "field_scales": scales,
              "initial_residual_distance": initial_distance}
    if args.manifest:
        Path(args.manifest).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
