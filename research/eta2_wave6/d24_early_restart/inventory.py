#!/usr/bin/env python3
"""Freeze held-out D21 files by hash without parsing their contents."""
from __future__ import annotations
import hashlib, json, pathlib

HERE = pathlib.Path(__file__).resolve().parent
W6 = HERE.parent


def sha(path: pathlib.Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


ledger = W6 / "d21-results.json"
episodes = json.loads(ledger.read_text())
rows = []
for index in range(len(episodes)):
    folder = W6 / "evidence/d21-restart-portfolio" / f"episode-{index:03d}-attempt-1"
    files = {name: sha(folder / name) for name in ("stdout.log", "curve.csv", "result.json")}
    rows.append({"episode": index, "folder": str(folder.relative_to(W6)), "files": files})
record = {"ledger": str(ledger), "ledger_sha256": sha(ledger),
          "episodes": len(rows), "rows": rows,
          "policy": "hash-only inventory; feature parser not imported"}
out = W6 / "d24-heldout-inventory.json"
out.write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))

