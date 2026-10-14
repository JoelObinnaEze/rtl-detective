from random import Random

from .contract import Transaction


def directed_transactions(depth: int) -> list[Transaction]:
    if depth < 1:
        raise ValueError("DEPTH must be at least 1")

    items = [Transaction(rst=True), Transaction()]
    items.extend(Transaction(wr_en=True, din=index + 1) for index in range(depth))
    items.append(Transaction(wr_en=True, din=0xA5))
    items.append(Transaction(wr_en=True, rd_en=True, din=0xB6))
    items.append(Transaction(wr_en=True, rd_en=True, din=0xC7))
    items.extend(Transaction(rd_en=True) for _ in range(depth))
    items.append(Transaction(wr_en=True, rd_en=True, din=0xD8))
    items.append(Transaction())
    items.append(Transaction(rst=True, wr_en=True, rd_en=True, din=0xE9))

    for index in range(depth * 3):
        items.append(Transaction(wr_en=True, din=0x30 + index))
        items.append(Transaction(rd_en=True))
    return items


def random_transactions(cycles: int, data_width: int, seed: int) -> list[Transaction]:
    if cycles < 1:
        raise ValueError("cycles must be at least 1")
    if data_width < 1:
        raise ValueError("DATA_WIDTH must be at least 1")

    random = Random(seed)
    items = [Transaction(rst=True)]
    for _ in range(cycles - 1):
        items.append(
            Transaction(
                rst=random.random() < 0.03,
                wr_en=bool(random.getrandbits(1)),
                rd_en=bool(random.getrandbits(1)),
                din=random.getrandbits(data_width),
            )
        )
    return items

