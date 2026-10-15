from pathlib import Path

import pytest

from backend.verification.security import (
    PatchRejected,
    apply_candidate_patch,
    hash_locked_assets,
    validate_source,
)


ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "benchmark/designs/buggy/simultaneous_count.sv"


def test_source_requires_exact_canonical_fifo_interface() -> None:
    with pytest.raises(ValueError, match="canonical identifier"):
        validate_source("module fifo(input logic clk); endmodule")


def test_source_rejects_foreign_code_and_oversized_input() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="foreign-code"):
        validate_source(source + '\nimport "DPI-C" function void escape();')
    with pytest.raises(ValueError, match="256 KiB"):
        validate_source(source + (" " * (256 * 1024)))


@pytest.mark.parametrize(
    "system_task",
    ['$display("RTLDET|0|0|1|0|0");', '$displayh("RTLDET|00010");', "$finish;"],
)
def test_source_rejects_output_spoofing_and_simulation_control(system_task: str) -> None:
    source = SOURCE.read_text(encoding="utf-8").replace(
        "endmodule", f"initial {system_task}\nendmodule", 1
    )

    with pytest.raises(ValueError, match="simulation I/O or control"):
        validate_source(source)


def test_patch_can_only_modify_candidate_dut(tmp_path: Path) -> None:
    diff = """diff --git a/tb.sv b/tb.sv
--- a/tb.sv
+++ b/tb.sv
@@ -1 +1 @@
-old
+new
"""

    with pytest.raises(PatchRejected, match="dut.sv"):
        apply_candidate_patch(SOURCE, diff, tmp_path)


def test_patch_rejects_attempt_to_disable_checks(tmp_path: Path) -> None:
    diff = """diff --git a/dut.sv b/dut.sv
--- a/dut.sv
+++ b/dut.sv
@@ -1,3 +1,4 @@
 module fifo #(
+  // verilator lint_off WIDTH
   parameter int DATA_WIDTH = 8,
   parameter int DEPTH = 4,
"""

    with pytest.raises(PatchRejected, match="disable"):
        apply_candidate_patch(SOURCE, diff, tmp_path)


def test_locked_asset_hashes_are_stable_and_include_oracle() -> None:
    first = hash_locked_assets(ROOT)
    second = hash_locked_assets(ROOT)

    assert first == second
    assert "backend/verification/contract.py" in first
    assert all(len(digest) == 64 for digest in first.values())

