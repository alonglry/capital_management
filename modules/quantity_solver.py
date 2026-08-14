"""
Unified Quantity Step Utility and Solver with Exact Lattice Mathematics.
"""

import math
from typing import Callable, Tuple


def quantity_to_step_index(quantity: float, increment: float) -> int:
    """
    Converts floating quantity into integer step index based on quantity increment.
    """
    if increment <= 0:
        return 0
    return int(math.floor(round(quantity / increment, 8)))


def step_index_to_quantity(step_index: int, increment: float) -> float:
    """
    Converts integer step index back into exact floating quantity for zero-aligned lattice q(N) = N * increment.
    """
    qty = float(step_index * increment)
    if increment >= 1.0:
        return float(int(round(qty)))
    decimals = max(0, -int(math.floor(math.log10(increment)))) + 4
    return round(qty, decimals)


def offset_step_to_quantity(min_qty: float, step_index: int, increment: float) -> float:
    """
    Converts step index into exact floating quantity for offset-aligned lattice q(N) = min_qty + N * increment.
    """
    qty = min_qty + float(step_index * increment)
    if increment >= 1.0:
        return float(round(qty))
    decimals = max(0, -int(math.floor(math.log10(increment)))) + 4
    return round(qty, decimals)


def solve_max_executable_quantity(
    risk_fn: Callable[[float], float],
    budget: float,
    min_qty: float,
    max_qty: float,
    qty_inc: float,
    monetary_tolerance: float = 1e-4,
) -> Tuple[float, bool]:
    """
    Solves for the maximum executable quantity q (aligned with broker quantity lattice, min_qty <= q <= max_qty)
    such that risk_fn(q) <= budget.

    Broker Quantity Lattice Support:
    - Zero-aligned: q(N) = N * qty_inc (for N_min <= N <= N_max) when min_qty is a multiple of qty_inc.
    - Offset-aligned: q(N) = min_qty + N * qty_inc (for 0 <= N <= N_max) when min_qty is not a multiple of qty_inc.

    Returns:
        Tuple[float, bool]: (executable_quantity, is_budget_satisfied)
    """
    if budget <= 0 or min_qty <= 0 or qty_inc <= 0 or max_qty < min_qty - 1e-6:
        return 0.0, False

    # Check lattice alignment
    min_rem = abs(min_qty / qty_inc - round(min_qty / qty_inc))
    is_zero_aligned = min_rem < 1e-4

    if is_zero_aligned:
        N_min = int(round(min_qty / qty_inc))
        N_max = int(math.floor(round(max_qty / qty_inc, 8)))
        q_at_N = lambda n: step_index_to_quantity(n, qty_inc)
    else:
        N_min = 0
        N_max = int(math.floor(round((max_qty - min_qty) / qty_inc, 8)))
        q_at_N = lambda n: offset_step_to_quantity(min_qty, n, qty_inc)

    if N_max < N_min:
        return 0.0, False

    q_min = q_at_N(N_min)
    q_max = q_at_N(N_max)

    r_min = risk_fn(q_min)
    if not math.isfinite(r_min) or r_min < 0:
        return 0.0, False
    if r_min > budget + monetary_tolerance:
        return 0.0, False

    r_max = risk_fn(q_max)
    if math.isfinite(r_max) and r_max <= budget + monetary_tolerance:
        return q_max, True

    # Check monotonicity across domain points
    N_mid = (N_min + N_max) // 2
    q_mid = q_at_N(N_mid)
    r_mid = risk_fn(q_mid)

    if not math.isfinite(r_mid) or r_mid < r_min - monetary_tolerance or (math.isfinite(r_max) and r_max < r_mid - monetary_tolerance):
        # Fallback to linear step-down if monotonicity is violated
        for n in range(N_max, N_min - 1, -1):
            q_candidate = q_at_N(n)
            if risk_fn(q_candidate) <= budget + monetary_tolerance:
                return q_candidate, True
        return 0.0, False

    # Binary search over integer step indices [N_min, N_max]
    low = N_min
    high = N_max
    best_N = N_min

    while low <= high:
        mid = (low + high) // 2
        q_test = q_at_N(mid)
        r_test = risk_fn(q_test)

        if math.isfinite(r_test) and r_test <= budget + monetary_tolerance:
            best_N = mid
            low = mid + 1
        else:
            high = mid - 1

    best_q = q_at_N(best_N)

    # Post-solution verification
    r_best = risk_fn(best_q)
    if not math.isfinite(r_best) or r_best > budget + monetary_tolerance:
        return 0.0, False

    # Verify that best_q + qty_inc exceeds budget (or best_q is max_qty)
    if best_N < N_max:
        next_q = q_at_N(best_N + 1)
        r_next = risk_fn(next_q)
        if math.isfinite(r_next) and r_next <= budget + monetary_tolerance:
            return next_q, True

    return best_q, True
