from __future__ import annotations

import os
import re
import shutil
import subprocess
from hashlib import sha256
from pathlib import Path, PurePosixPath

from .packs import get_contract_pack

MAX_SOURCE_BYTES = 256 * 1024
MAX_DIFF_BYTES = 128 * 1024
FORBIDDEN_SOURCE = re.compile(
    r'\b(?:import|export)\s+["\']DPI|'
    r'\$(?:system|fopen|(?:f?display|f?write|strobe|f?monitor)(?:[boh])?|finish|fatal|stop|readmemh|readmemb)\b',
    re.IGNORECASE,
)
FORBIDDEN_PATCH = re.compile(r'verilator\s+lint_off|translate_off|\$(?:finish|fatal)\b|`ifdef\s+VERILATOR', re.IGNORECASE)
MODULE_HEADER = re.compile(r"\bmodule\s+\w+\b.*?\)\s*;", re.DOTALL)
LOCKED_ASSETS = (
    "backend/verification/contract.py",
    "backend/verification/cases.py",
    "backend/verification/fifo.py",
    "backend/verification/arbiter.py",
    "backend/verification/packs.py",
    "backend/verification/runner.py",
    "backend/verification/security.py",
)


class PatchRejected(ValueError):
    pass


def validate_source(source: str, contract_id: str = "fifo") -> None:
    encoded = source.encode("utf-8")
    if len(encoded) > MAX_SOURCE_BYTES:
        raise ValueError("source exceeds the 256 KiB limit")
    if "\0" in source:
        raise ValueError("source contains a NUL byte")
    if FORBIDDEN_SOURCE.search(source):
        raise ValueError("foreign-code, simulation I/O or control features are not supported")
    pack = get_contract_pack(contract_id)
    module_name = pack.required_identifiers[0]
    if not re.search(rf"\bmodule\s+{re.escape(module_name)}\b", source):
        raise ValueError(f"source must declare module {module_name}")
    for identifier in pack.required_identifiers[1:]:
        if not re.search(rf"\b{re.escape(identifier)}\b", source):
            raise ValueError(f"missing canonical identifier: {identifier}")


def _validate_diff(diff: str) -> None:
    if len(diff.encode("utf-8")) > MAX_DIFF_BYTES:
        raise PatchRejected("diff exceeds the 128 KiB limit")
    if "GIT binary patch" in diff or "\0" in diff:
        raise PatchRejected("binary patches are not supported")

    paths = []
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) != 4:
                raise PatchRejected("malformed diff header")
            paths.extend(parts[2:])
        elif line.startswith(("--- ", "+++ ")):
            paths.append(line.split(maxsplit=1)[1].split("\t", 1)[0])
        elif line.startswith("+") and not line.startswith("+++") and FORBIDDEN_PATCH.search(line[1:]):
            raise PatchRejected("patch may not disable checks or terminate the testbench")

    if not paths:
        raise PatchRejected("diff has no file headers")
    for raw_path in paths:
        path = PurePosixPath(raw_path.removeprefix("a/").removeprefix("b/"))
        if path.is_absolute() or ".." in path.parts or path.as_posix() != "dut.sv":
            raise PatchRejected("patch may only modify dut.sv")


def _module_header(source: str) -> str:
    match = MODULE_HEADER.search(source)
    if not match:
        raise PatchRejected("source has no complete module header")
    return match.group(0)


def apply_candidate_patch(original: Path, diff: str, workspace: Path, contract_id: str = "fifo") -> Path:
    _validate_diff(diff)
    original_source = original.read_text(encoding="utf-8")
    workspace.mkdir(parents=True, exist_ok=True)
    candidate = workspace / "dut.sv"
    shutil.copyfile(original, candidate)
    patch_file = workspace / "candidate.diff"
    patch_file.write_text(diff, encoding="utf-8", newline="\n")
    apply_env = os.environ.copy()
    apply_env["GIT_CEILING_DIRECTORIES"] = str(workspace.resolve().parent)

    check = subprocess.run(
        ["git", "apply", "--check", "candidate.diff"],
        cwd=workspace,
        env=apply_env,
        capture_output=True,
        text=True,
        check=False,
    )
    if check.returncode != 0:
        raise PatchRejected(f"patch does not apply cleanly: {check.stderr.strip()}")
    applied = subprocess.run(
        ["git", "apply", "candidate.diff"],
        cwd=workspace,
        env=apply_env,
        capture_output=True,
        text=True,
        check=False,
    )
    if applied.returncode != 0:
        raise PatchRejected(f"patch failed: {applied.stderr.strip()}")
    candidate_source = candidate.read_text(encoding="utf-8")
    if _module_header(candidate_source) != _module_header(original_source):
        raise PatchRejected("patch may not modify the module header")
    validate_source(candidate_source, contract_id)
    return candidate


def hash_locked_assets(root: Path) -> dict[str, str]:
    return {
        relative: sha256((root / relative).read_bytes()).hexdigest()
        for relative in LOCKED_ASSETS
    }

