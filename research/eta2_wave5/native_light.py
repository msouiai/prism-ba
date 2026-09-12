"""Native runner that audits a temporary endpoint without retaining large states."""
from pathlib import Path
import csv, fcntl, hashlib, json, os, re, socket, subprocess, tempfile, time

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parent / "eta2_champion"
import sys
sys.path.insert(0, str(FROZEN / "bench"))
from audit_prism_state import observations, audit

CHAMPION = json.loads((FROZEN / "champion.json").read_text())
OBSERVATIONS = {}


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def run(folder, cell, arm, rep, binary, flags, protocol, build_manifest):
    """Run one cell; preserve all scalar evidence and only the state hash."""
    folder = Path(folder)
    result_path = folder / "result.json"
    if result_path.exists():
        row = json.loads(result_path.read_text())
        if row["valid"]:
            return row
    folder.mkdir(parents=True, exist_ok=True)
    binary, problem = Path(binary), Path(cell["path"])
    assert sha(problem) == cell["input_sha256"]
    fd, name = tempfile.mkstemp(prefix="eta2-wave5-", suffix=".state", dir="/dev/shm")
    os.close(fd)
    state = Path(name)
    clean = {k: v for k, v in os.environ.items()
             if not k.startswith(("OCA_", "CASPAR_", "CERES_", "COLMAP_MFREE", "MF_DEBUG"))}
    config = dict(CHAMPION["flags"], **flags,
                  OCA_MAX_SECONDS=str(cell["cap"]),
                  OCA_TARGET_COST=str(cell["target"]),
                  OCA_WAVE_TRACE=str(folder / "wave.json"),
                  OCA_STCG_ATTEMPTS=str(folder / "attempts.json"))
    clean.update(config)
    cmd = [str(binary), "--problem", str(problem), *CHAMPION["cli"],
           "--csv", str(folder / "curve.csv"), "--state_out", str(state)]
    manifest = {
        "command": cmd, "flags": config, "binary_sha256": sha(binary),
        "input_sha256": sha(problem), "champion_sha256": sha(FROZEN / "champion.json"),
        "protocol_sha256": sha(protocol), "host": socket.gethostname(),
        "scene": cell["scene"], "arm": arm, "rep": rep,
        "target": cell["target"], "cap": cell["cap"],
        "build_manifest": build_manifest,
        "endpoint_policy": "Independent FP64 audit in /dev/shm; retain exact SHA256 and byte count, then remove temporary state",
    }
    write(folder / "manifest.json", manifest)
    print("RUN", folder.parent.name, cell["scene"], arm, rep, flush=True)
    started = time.monotonic()
    row = {"scene": cell["scene"], "cell": cell.get("cell", cell["scene"]),
           "arm": arm, "rep": rep, "target": cell["target"], "cap": cell["cap"],
           "valid": False, "source": str(folder.relative_to(HERE))}
    try:
        with open("/tmp/prism_gpu.lock", "w") as lock, \
             (folder / "stdout.log").open("w") as out, \
             (folder / "stderr.log").open("w") as err:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                rc = subprocess.run(cmd, env=clean, stdout=out, stderr=err,
                                    timeout=max(180, 3 * cell["cap"])).returncode
            except subprocess.TimeoutExpired:
                rc = 124
        process_seconds = time.monotonic() - started
        text = (folder / "stdout.log").read_text()
        native = re.search(r"RESULT .*?iters=(\d+) final_cost=(\S+) solve_seconds=(\S+)", text)
        count = re.search(r"MFCG: accepts=(\d+) rejects=(\d+) total_matvecs=(\d+).*?negcurv=(\d+)", text)
        assert rc == 0 and native and count, (rc, bool(native), bool(count))
        key = str(problem)
        if key not in OBSERVATIONS:
            OBSERVATIONS[key] = observations(problem)
        score = float(audit(state, *OBSERVATIONS[key]))
        native_cost = float(native[2])
        relative = abs(score - native_cost) / max(1.0, score)
        assert relative < 1e-6, relative
        curves = list(csv.DictReader(x for x in (folder / "curve.csv").read_text().splitlines()
                                     if not x.startswith("#")))
        crossings = [float(x["wall_s"]) for x in curves
                     if float(x["cost"]) <= cell["target"]]
        hit = bool(crossings and score <= cell["target"] and crossings[0] <= cell["cap"])
        attempts_path, wave_path = folder / "attempts.json", folder / "wave.json"
        attempts = (json.loads(attempts_path.read_text()) if attempts_path.exists()
                    else {"totals": {"matvecs": int(count[3]),
                                      "instrumentation_available": False}})
        wave = json.loads(wave_path.read_text()) if wave_path.exists() else []
        assert attempts["totals"]["matvecs"] == int(count[3])
        row.update({
            "returncode": rc, "process_seconds": process_seconds, "valid": True,
            "cost": score, "native_cost": native_cost, "audit_relative_error": relative,
            "native_seconds": float(native[3]), "outers": int(native[1]),
            "accepts": int(count[1]), "rejects": int(count[2]),
            "matvecs": int(count[3]), "negcurv": int(count[4]),
            "score_init": float(curves[0]["cost"]), "hit": hit,
            "target_seconds": crossings[0] if hit else None,
            "cap_hit": "MAX_SECONDS" in text or int(native[1]) >= 600,
            "stop_ftol": "converged (OCA_FTOL:" in text,
            "state_sha256": sha(state), "state_bytes": state.stat().st_size,
            "endpoint_retained": False, "attempts": attempts["totals"],
            "max_raw_radius_ratio": max(
                (x["raw_radius_ratio"] for x in wave if x.get("raw_radius_ratio") is not None),
                default=None),
        })
    except Exception as error:
        row.update({"error": repr(error), "process_seconds": time.monotonic() - started})
    finally:
        state.unlink(missing_ok=True)
    write(result_path, row)
    print("DONE", cell["scene"], arm, rep, "valid", row["valid"],
          "cost", row.get("cost"), "s", row.get("native_seconds"),
          "hit", row.get("hit"), flush=True)
    assert row["valid"], row
    return row
