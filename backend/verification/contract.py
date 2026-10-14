from dataclasses import dataclass
from math import ceil, log2


def count_width(depth: int) -> int:
    if depth < 1:
        raise ValueError("DEPTH must be at least 1")
    return max(1, ceil(log2(depth + 1)))


@dataclass(frozen=True)
class Transaction:
    rst: bool = False
    wr_en: bool = False
    rd_en: bool = False
    din: int = 0


@dataclass(frozen=True)
class Snapshot:
    cycle: int
    transaction: Transaction
    write_accepted: bool
    read_accepted: bool
    count: int
    full: bool
    empty: bool
    dout: int


class FifoModel:
    """Executable oracle for the selected registered-output FIFO contract."""

    def __init__(self, data_width: int, depth: int) -> None:
        if data_width < 1:
            raise ValueError("DATA_WIDTH must be at least 1")
        count_width(depth)
        self.data_width = data_width
        self.depth = depth
        self._mask = (1 << data_width) - 1
        self._queue: list[int] = []
        self._dout = 0
        self._cycle = -1

    @property
    def contents(self) -> tuple[int, ...]:
        return tuple(self._queue)

    def step(self, transaction: Transaction) -> Snapshot:
        self._cycle += 1
        was_empty = not self._queue
        was_full = len(self._queue) == self.depth
        write_accepted = not transaction.rst and transaction.wr_en and not was_full
        read_accepted = not transaction.rst and transaction.rd_en and not was_empty

        if transaction.rst:
            self._queue.clear()
            self._dout = 0
        else:
            if read_accepted:
                self._dout = self._queue.pop(0)
            if write_accepted:
                self._queue.append(transaction.din & self._mask)

        count = len(self._queue)
        return Snapshot(
            cycle=self._cycle,
            transaction=transaction,
            write_accepted=write_accepted,
            read_accepted=read_accepted,
            count=count,
            full=count == self.depth,
            empty=count == 0,
            dout=self._dout,
        )

