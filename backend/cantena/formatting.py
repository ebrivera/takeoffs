"""Formatting helpers for cost estimate output.

Provides human-readable formatting for currency amounts, cost ranges,
and per-SF costs — matching how construction PMs communicate numbers
(e.g., '$12.4M' instead of '$12,437,892.34').
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cantena.models.estimate import CostRange


def format_currency(amount: float) -> str:
    """Format a currency amount as a human-readable string.

    - Amounts >= $10,000: no cents, with comma separators (e.g., '$1,234,567')
    - Amounts < $10,000: with cents (e.g., '$9,876.54')
    """
    if amount >= 10_000:
        return f"${amount:,.0f}"
    return f"${amount:,.2f}"


def format_cost_range(cr: CostRange) -> str:
    """Format a CostRange as a human-readable string.

    - Millions (>= $1M): '$X.XM - $X.XM'
    - Below $1M: '$XXX,XXX - $XXX,XXX'
    """
    if cr.high >= 1_000_000:
        return f"${cr.low / 1_000_000:.1f}M - ${cr.high / 1_000_000:.1f}M"
    return f"${cr.low:,.0f} - ${cr.high:,.0f}"


def format_sf_cost(cr: CostRange) -> str:
    """Format a per-SF CostRange as '$XXX - $XXX / SF'."""
    return f"${cr.low:,.0f} - ${cr.high:,.0f} / SF"
