from pathlib import Path

from vcdvcd import VCDVCD


CANONICAL_SIGNALS = (
    "clk",
    "rst",
    "wr_en",
    "rd_en",
    "din",
    "dout",
    "full",
    "empty",
    "count",
    "request",
    "grant",
)


def extract_signal_changes(vcd_path: Path, start_time: int = 0, end_time: int | None = None) -> dict[str, object]:
    vcd = VCDVCD(str(vcd_path), store_tvs=True)
    result: dict[str, object] = {
        "timescale": f"{vcd.timescale['magnitude']} {vcd.timescale['unit']}",
        "signals": {},
    }
    for canonical in CANONICAL_SIGNALS:
        matches = [name for name in vcd.signals if name.rsplit(".", 1)[-1].split("[")[0] == canonical]
        if not matches:
            continue
        name = min(matches, key=len)
        changes = [
            {"time": time, "value": value}
            for time, value in vcd[name].tv
            if time >= start_time and (end_time is None or time <= end_time)
        ]
        result["signals"][canonical] = {"vcd_name": name, "changes": changes}  # type: ignore[index]
    return result

