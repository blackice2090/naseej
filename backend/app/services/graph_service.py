"""Graph analysis stub. Real implementation in Phase 3."""

from __future__ import annotations

from typing import Any

from ..core.schemas import PatternIn


def analyze(payload: PatternIn) -> dict[str, Any]:
    """Return a placeholder graph summary for a list of transactions."""
    txs = payload.transactions
    accounts: set[str] = set()
    for t in txs:
        accounts.add(t.from_account)
        accounts.add(t.to_account)
    total_amount = sum(t.amount for t in txs)
    return {
        "tx_count": len(txs),
        "unique_accounts": len(accounts),
        "total_amount": total_amount,
        "note": "Phase 3 will replace this with networkx-based features.",
    }
