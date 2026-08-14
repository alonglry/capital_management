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
    Converts integer step index back into exact floating quantity.
    """
    qty = float(step_index * increment)
    if increment >= 1.0:
        return float(int(round(qty)))
    decimals = max(0, -int(math.floor(math.log10(increment)))) + 4
    return round(qty, decimals)


def solve_max_executable_quantity(
    risk_fn: Callable[[float], float],
    budget: float,
    min_qty: float,
    max_qty: float,
    qty_inc: float,
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
        offset = 0
    else:
        N_min = 0
        N_max = int(math.floor(round((max_qty - min_qty) / qty_inc, 8)))
        offset = quantity_to_step_index(min_qty, qty_inc)

    if N_max < N_min:
        return 0.0, False

    q_min = step_index_to_quantity(N_min + offset, qty_inc)
    q_max = step_index_to_quantity(N_max + offset, qty_inc)

    r_min = risk_fn(q_min)
    if not math.isfinite(r_min) or r_min < 0:
        return 0.0, False
    if r_min > budget + 1e-4:
        return 0.0, False

    r_max = risk_fn(q_max)
    if math.isfinite(r_max) and r_max <= budget + 1e-4:
        return q_max, True

    # Check monotonicity at midpoint
    N_mid = (N_min + N_max) // 2
    q_mid = step_index_to_quantity(N_mid + offset, qty_inc)
    r_mid = risk_fn(q_mid)

    if not math.isfinite(r_mid) or r_mid < r_min - 1e-4 or (math.isfinite(r_max) and r_max < r_mid - 1e-4):
        # Fallback to linear step-down if monotonicity is violated
        for n in range(N_max, N_min - 1, -1):
            q_candidate = step_index_to_quantity(n + offset, qty_inc)
            if risk_fn(q_candidate) <= budget + 1e-4:
                return q_candidate, True
        return 0.0, False

    # Binary search over integer step indices [N_min, N_max]
    low = N_min
    high = N_max
    best_N = N_min

    while low <= high:
        mid = (low + high) // 2
        q_test = step_index_to_quantity(mid + offset, qty_inc)
        r_test = risk_fn(q_test)

        if math.isfinite(r_test) and r_test <= budget + 1e-4:
            best_N = mid
            low = mid + 1
        else:
            high = mid - 1

    best_q = step_index_to_quantity(best_N + offset, qty_inc)

    # Post-solution verification
    r_best = risk_fn(best_q)
    if not math.isfinite(r_best) or r_best > budget + 1e-4:
        return 0.0, False

    # Verify that best_q + qty_inc exceeds budget (or best_q is max_qty)
    if best_N < N_max:
        next_q = step_index_to_quantity(best_N + 1 + offset, qty_inc)
        r_next = risk_fn(next_q)
        if math.isfinite(r_next) and r_next <= budget + 1e-4:
            # If next step also satisfies budget, advance to next step
            return next_q, True

    return best_q, True
