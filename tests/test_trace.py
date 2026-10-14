from pathlib import Path

from backend.verification.trace import extract_signal_changes


def test_vcd_parser_extracts_bounded_canonical_changes(tmp_path: Path) -> None:
    trace = tmp_path / "trace.vcd"
    trace.write_text(
        """$timescale 1ns $end
$scope module tb $end
$var wire 1 ! clk $end
$var wire 1 \" rst $end
$var wire 2 # count [1:0] $end
$upscope $end
$enddefinitions $end
#0
0!
1\"
b00 #
#5
1!
#10
0!
0\"
b01 #
""",
        encoding="ascii",
    )

    window = extract_signal_changes(trace, start_time=5, end_time=10)

    assert "1 ns" in window["timescale"]
    assert window["signals"]["clk"]["changes"] == [
        {"time": 5, "value": "1"},
        {"time": 10, "value": "0"},
    ]
    assert window["signals"]["count"]["changes"] == [{"time": 10, "value": "01"}]

