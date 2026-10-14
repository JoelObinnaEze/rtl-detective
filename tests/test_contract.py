from backend.verification.contract import FifoModel, Transaction


def test_reset_wins_and_clears_output() -> None:
    model = FifoModel(data_width=8, depth=3)
    model.step(Transaction(wr_en=True, din=0xA5))

    result = model.step(Transaction(rst=True, wr_en=True, rd_en=True, din=0x55))

    assert result.count == 0
    assert result.empty is True
    assert result.full is False
    assert result.dout == 0
    assert result.write_accepted is False
    assert result.read_accepted is False


def test_boundary_simultaneous_operations_use_pre_edge_state() -> None:
    model = FifoModel(data_width=8, depth=1)

    at_empty = model.step(Transaction(wr_en=True, rd_en=True, din=7))
    assert (at_empty.write_accepted, at_empty.read_accepted, at_empty.count) == (True, False, 1)

    at_full = model.step(Transaction(wr_en=True, rd_en=True, din=9))
    assert (at_full.write_accepted, at_full.read_accepted, at_full.count) == (False, True, 0)
    assert at_full.dout == 7


def test_partial_simultaneous_operation_preserves_order_and_count() -> None:
    model = FifoModel(data_width=8, depth=3)
    model.step(Transaction(wr_en=True, din=0x11))
    model.step(Transaction(wr_en=True, din=0x22))

    result = model.step(Transaction(wr_en=True, rd_en=True, din=0x33))

    assert (result.write_accepted, result.read_accepted, result.count) == (True, True, 2)
    assert result.dout == 0x11
    assert model.contents == (0x22, 0x33)


def test_rejected_read_holds_dout_and_data_is_width_limited() -> None:
    model = FifoModel(data_width=1, depth=2)
    model.step(Transaction(wr_en=True, din=3))
    read = model.step(Transaction(rd_en=True))

    held = model.step(Transaction(rd_en=True))

    assert read.dout == 1
    assert held.read_accepted is False
    assert held.dout == 1

