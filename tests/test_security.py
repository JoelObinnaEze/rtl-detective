import difflib
from pathlib import Path

import pytest

from backend.verification.security import (
    PatchRejected,
    apply_candidate_patch,
    hash_locked_assets,
    restore_module_header,
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


def test_direct_patch_rejects_module_header_changes(tmp_path: Path) -> None:
    diff = """diff --git a/dut.sv b/dut.sv
--- a/dut.sv
+++ b/dut.sv
@@ -1,6 +1,6 @@
 module fifo #(
   parameter int DATA_WIDTH = 8,
-  parameter int DEPTH = 4,
+  parameter int DEPTH = 3,
   localparam int PTR_WIDTH = (DEPTH <= 1) ? 1 : $clog2(DEPTH),
   localparam int COUNT_WIDTH = (DEPTH <= 1) ? 1 : $clog2(DEPTH + 1)
 ) (
"""

    with pytest.raises(PatchRejected, match="module header"):
        apply_candidate_patch(SOURCE, diff, tmp_path)


def test_host_restores_the_original_header_before_building_a_diff() -> None:
    original = SOURCE.read_text(encoding="utf-8")
    proposed = original.replace("parameter int DEPTH = 4", "parameter int DEPTH = 3").replace(
        "count <= count + 1'b1;",
        "count <= count + 2'b01;",
        1,
    )

    restored = restore_module_header(original, proposed)

    assert "parameter int DEPTH = 4" in restored
    assert "parameter int DEPTH = 3" not in restored
    assert "count <= count + 2'b01;" in restored


def test_patch_applies_to_candidate_inside_parent_repository(tmp_path: Path) -> None:
    source = SOURCE.read_text(encoding="utf-8")
    fixed = source.replace("count <= count + 1'b1;", "count <= count + 2'b01;", 1)
    diff = "".join(
        difflib.unified_diff(
            source.splitlines(keepends=True),
            fixed.splitlines(keepends=True),
            fromfile="a/dut.sv",
            tofile="b/dut.sv",
        )
    )

    candidate = apply_candidate_patch(SOURCE, diff, tmp_path)

    assert "count <= count + 2'b01;" in candidate.read_text(encoding="utf-8")


def test_locked_asset_hashes_are_stable_and_include_oracle() -> None:
    first = hash_locked_assets(ROOT)
    second = hash_locked_assets(ROOT)

    assert first == second
    assert "backend/verification/contract.py" in first
    assert all(len(digest) == 64 for digest in first.values())

