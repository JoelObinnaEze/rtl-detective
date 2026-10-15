from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import arbiter, fifo


@dataclass(frozen=True)
class ContractPack:
    id: str
    name: str
    summary: str
    limitation: str
    required_identifiers: tuple[str, ...]
    regression_transactions: Callable[[object], list[object]]
    transaction_from_action: Callable[[object], object]
    parameter_summary: Callable[[object], str]
    render_testbench: Callable[[list[object], object], str]
    parse_observations: Callable[[str], list[object]]
    compare: Callable[[list[object], object, list[object]], list[object]]


_PACKS = {
    "fifo": ContractPack(
        id="fifo",
        name="Synchronous FIFO",
        summary=fifo.SUMMARY,
        limitation=fifo.LIMITATION,
        required_identifiers=fifo.REQUIRED_IDENTIFIERS,
        regression_transactions=fifo.regression_transactions,
        transaction_from_action=fifo.transaction_from_action,
        parameter_summary=fifo.parameter_summary,
        render_testbench=fifo.render_testbench,
        parse_observations=fifo.parse_observations,
        compare=fifo.compare,
    ),
    "arbiter": ContractPack(
        id="arbiter",
        name="Round-robin arbiter",
        summary=arbiter.SUMMARY,
        limitation=arbiter.LIMITATION,
        required_identifiers=arbiter.REQUIRED_IDENTIFIERS,
        regression_transactions=arbiter.regression_transactions,
        transaction_from_action=arbiter.transaction_from_action,
        parameter_summary=arbiter.parameter_summary,
        render_testbench=arbiter.render_testbench,
        parse_observations=arbiter.parse_observations,
        compare=arbiter.compare,
    ),
}


def get_contract_pack(contract_id: str) -> ContractPack:
    try:
        return _PACKS[contract_id]
    except KeyError as error:
        raise ValueError(f"unknown contractId: {contract_id}") from error


def contract_pack_summaries() -> list[dict[str, str]]:
    return [{"id": pack.id, "name": pack.name, "summary": pack.summary} for pack in _PACKS.values()]
