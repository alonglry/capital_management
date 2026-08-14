"""
Unified Quantity Step Utility and Solver.
"""

import math
from typing import Callable, Tuple


def quantity_to_step_index(quantity: float, increment: float) -> int:
    """
    Converts floating quantity into integer step index based on quantity increment.
    """
    if increment <= 0:
        return 0
    return int(math.floor(round(quantity / increment, 6)))


def step_index_to_quantity(step_index: int, increment: float) -> float:
    """
    Converts integer step index back into exact floating quantity.
    """
    qty = float(step_index * increment)
    if increment >= 1.0:
        return float(int(round(qty)))
    decimals = max(0, -int(math.floor(math.log10(increment))))
    return round(qty, decimals)


def solve_max_executable_quantity(
    risk_fn: Callable[[float], float],
    budget: float,
    min_qty: float,
    max_qty: float,
    qty_inc: float,
) -> Tuple[float, bool]:
    """
    Solves for the maximum executable quantity q (aligned with qty_inc, min_qty <= q <= max_qty)
    such that risk_fn(q) <= budget.

    Returns:
        Tuple[float, bool]: (executable_quantity, is_budget_satisfied)
    """
    if budget <= 0 or min_qty <= 0 or qty_inc <= 0 or max_qty < min_qty:
        return 0.0, False

    N_min = int(math.ceil(round(min_qty / qty_inc, 6)))
    N_max = int(math.floor(round(max_qty / qty_inc, 6)))

    # Initial guess for N based on linear upper bound if risk_fn is non-zero
    r_min = risk_fn(step_index_to_quantity(N_min, qty_inc))
    if r_min > budget + 1e-6:
        return 0.0, False

    r_max = risk_fn(step_index_to_quantity(N_max, qty_inc))
    if r_max <= budget + 1e-6:
        return step_index_to_quantity(N_max, qty_inc), True

    # Binary search over integer step indices [N_min, N_max]
    low = N_min
    high = N_max
    best_N = N_min

    while low <= high:
        mid = (low + high) // 2
        q_mid = step_index_to_quantity(mid, qty_inc)
        r_mid = risk_fn(q_mid)

        if r_mid <= budget + 1e-6:
            best_N = mid
            low = mid + 1
        else:
            high = mid - 1

    return step_index_to_quantity(best_N, qty_inc), True
