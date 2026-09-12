#!/usr/bin/env python3
"""Score a supplementary CPU-completed direction with the shared witness evaluator."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--metadata', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise FileExistsError(a.output)
    provenance = json.loads(a.metadata.read_text())
    path = Path(__file__).resolve().parents[1]/'analysis/audit_capture.py'
    spec = importlib.util.spec_from_file_location('brief0_supplement_evaluator', path)
    audit = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = audit
    spec.loader.exec_module(audit)
    capture, bal = Path(provenance['capture']), Path(provenance['bal'])
    camera, X, meta = audit.load_capture_state(capture)
    ci, pi, uv, dims = audit.CHART.load_observations(bal)
    step_path = Path(provenance['refined_step']['path'])
    if audit.file_sha256(step_path) != provenance['refined_step']['sha256']:
        raise ValueError('Refined step provenance mismatch')
    step = audit.map_f64(step_path, (9*dims[0]+3*dims[1],))
    geom = audit.geometry(camera, X, ci, pi)
    native = dict(arm='cpu_completed_reference', rep=0, certified=0)
    row, _ = audit.audit_direction(camera, X, ci, pi, uv, step, meta, geom, native,
                                  Cdiag=audit.map_f64(capture/'Cdiag.f64',(dims[1],3)))
    selected = ('costs','predictions','true_decreases','rho','model_error','point_error_bins',
                'top200_absolute_point_error','flings','cheirality_flip_observations',
                'behind_camera_observations','invalid_projection_observations','point_equation')
    result = dict(kind='supplementary CPU point-completed witness direction',
                  scored_with_unmodified_shared_audit_direction=True,
                  evaluator_sha256=audit.file_sha256(path),
                  metadata_sha256=audit.file_sha256(a.metadata),
                  refined_step=provenance['refined_step'],
                  camera_state_and_direction_unchanged=True,
                  objective='all original observations, SIMPLE_RADIAL, unshared intrinsics, k2=0; plain squared error',
                  results={key:row[key] for key in selected},
                  limitation='This supplements but never replaces the original registered source-reference row; no native rollout or speed claim.')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(audit.sanitize(result),indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(output=str(a.output),cost=row['costs']['full'],
                          decrease=row['true_decreases']['full'],prediction=row['predictions']['full'],
                          rho=row['rho']['full'])))


if __name__ == '__main__':
    main()
